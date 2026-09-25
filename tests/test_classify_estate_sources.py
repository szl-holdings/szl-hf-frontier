from __future__ import annotations

import base64
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path

from tools.classify_estate_sources import (
    Reader, SameOriginRedirect, SourceUnavailable, capture, classify, github_claims, load_observation,
    observation_path, production_claims, public_items, write_json,
)

SHA = "a" * 40
CHECKED = "2026-09-24T12:00:00Z"


def item(kind: str = "models", **inventory):
    name = "szl-holdings/example" if kind == "github" else "SZLHOLDINGS/example"
    surface = "github" if kind == "github" else {"models": "huggingface-model", "spaces": "huggingface-space", "datasets": "huggingface-dataset"}[kind]
    return {"id": f"{surface}/{name.casefold()}", "kind": kind, "name": name,
            "url": ("https://github.com/" if kind == "github" else "https://huggingface.co/" + ("" if kind == "models" else f"{kind}/")) + name,
            "inventory": {"private": False, "sha": SHA, **inventory}}


def observed(card: str, **kwargs):
    return {"observed_at": CHECKED, "observed_revision": SHA, "card": card,
            "evidence": [{"kind": "source_card", "revision": SHA}], "errors": [], **kwargs}


class FakeReader:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def json(self, url, **kwargs):
        self.calls.append(url)
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response

    def read(self, url, **kwargs):
        return self.json(url, **kwargs)


class ClassificationTests(unittest.TestCase):
    def test_missing_visibility_is_not_public_and_private_identity_is_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for kind in ("models", "spaces", "datasets"):
                write_json(root / f"huggingface_{kind}.json", [])
            write_json(root / "github_repositories.json", [
                {"full_name": "owner/public", "private": False},
                {"full_name": "owner/private", "private": True},
                {"full_name": "owner/unknown"},
                {"full_name": "owner/string", "private": "false"},
            ])
            self.assertEqual(["owner/public"], [row["name"] for row in public_items(root)])

    def test_missing_snapshot_refuses_partial_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Required inventory"):
                public_items(Path(temp))

    def test_ambiguous_sources_do_not_guess_mapping(self):
        review = classify(item(), observed("Source: https://github.com/szl-holdings/one and https://github.com/szl-holdings/two"), {"szl-holdings/one", "szl-holdings/two"})
        self.assertEqual("NEEDS_CANONICAL_MAPPING", review["audit"]["status"])
        self.assertNotIn("github", review["links"])
        self.assertEqual("none", review["canonical"]["role"])

    def test_public_census_verification_prevents_private_route_guess(self):
        review = classify(item(), observed("Canonical source: https://github.com/szl-holdings/secret"), set())
        self.assertEqual("NEEDS_CANONICAL_MAPPING", review["audit"]["status"])
        self.assertFalse(review["source_claims"][0]["verified_public_repository"])
        self.assertNotIn("github", review["links"])

    def test_reference_link_is_not_automatically_a_source(self):
        review = classify(item(), observed("Thanks to https://github.com/szl-holdings/one"), {"szl-holdings/one"})
        self.assertEqual("NEEDS_CANONICAL_MAPPING", review["audit"]["status"])

    def test_source_heading_and_exact_subpath_preserved_without_ownership_collision(self):
        url = f"https://github.com/szl-holdings/szl-forge/tree/{SHA}/khipu"
        review = classify(item(), observed(f"# Canonical source\n\n[{url}]({url})"), {"szl-holdings/szl-forge"})
        self.assertEqual(url, review["links"]["github"])
        self.assertEqual(item()["url"], review["canonical"]["url"])
        self.assertEqual("mirror_distribution", review["classification"])
        self.assertEqual("EXPERIMENTAL", review["status"])
        self.assertEqual("UNREVIEWED", review["audit"]["status"])

    def test_weights_presence_never_qualifies_model(self):
        review = classify(item(), observed("# Model\nSource: https://github.com/szl-holdings/example", files=["model.safetensors"]), {"szl-holdings/example"})
        self.assertEqual("EXPERIMENTAL", review["status"])
        self.assertNotIn("ALIGNED", review["audit"]["status"])

    def test_explicit_software_status_has_no_checkpoint_inference(self):
        review = classify(item(), observed("This is a Python kernel, not a trained model."), set())
        self.assertEqual(("kernel", "SOFTWARE"), (review["artifact_class"], review["status"]))

    def test_space_runtime_role_never_implies_operational_health(self):
        review = classify(item("spaces"), observed("Source: https://github.com/szl-holdings/example"), {"szl-holdings/example"})
        self.assertEqual("operational_runtime_surface", review["classification"])
        self.assertEqual("UNREVIEWED", review["audit"]["status"])
        self.assertTrue(any("no health" in note for note in review["audit"]["notes"]))

    def test_archive_owns_provenance_url_not_successor(self):
        review = classify(item("github", archived=True), observed("Successor: https://github.com/szl-holdings/new"), {"szl-holdings/new"})
        self.assertEqual("archived_provenance", review["classification"])
        self.assertEqual("record", review["canonical"]["role"])
        self.assertEqual(item("github")["url"], review["canonical"]["url"])
        self.assertEqual("https://github.com/szl-holdings/new", review["links"]["successor"])

    def test_declared_quarantine_is_retained(self):
        review = classify(item(), observed("Status: QUARANTINED\nNo promotion."), set())
        self.assertEqual("BLOCKED", review["status"])
        self.assertEqual("experimental_blocked", review["classification"])

    def test_empty_card_cannot_support_source(self):
        review = classify(item("github"), observed("", evidence=[], errors=["HTTP_404"]), set())
        self.assertEqual("UNAVAILABLE_WITH_REASON", review["audit"]["status"])
        self.assertNotEqual("SOURCE_BACKED", review["status"])

    def test_support_repository_is_not_qualified_product(self):
        review = classify(item("github"), observed("# Tracker\nThis is an execution tracker."), set())
        self.assertEqual(("support_artifact", "REFERENCE"), (review["classification"], review["status"]))

    def test_runtime_claim_negation_is_bounded_by_clauses(self):
        card = "Not production-ready. Fully operational.\nNo live endpoint is offered.\nNot qualified but production-grade service.\n```\nfully operational\n```\nProduction-ready is not a supported claim."
        claims = production_claims(card)
        self.assertEqual(["Fully operational", "production-grade"], [claim["claim"] for claim in claims])

    def test_runtime_claims_need_review(self):
        review = classify(item("github"), observed("A fully operational service."), set())
        self.assertEqual("NEEDS_STATUS_CORRECTION", review["audit"]["status"])
        self.assertEqual("verify_or_bound_public_runtime_claims", review["candidate_recommendations"][0]["action"])

    def test_live_deployment_remains_unknown_is_not_affirmative(self):
        self.assertEqual([], production_claims("live deployment state remains **UNKNOWN** on this candidate:"))

    def test_table_header_is_not_an_affirmative_endpoint_claim(self):
        self.assertEqual([], production_claims("| Organ | Proven formula (round9) | Live endpoint read |\n|---|---|---|\n| BRAIN | Test | Example |"))
        self.assertEqual(1, len(production_claims("| Service | Status |\n|---|---|\n| API | Fully operational |")))

    def test_negations_continue_across_bounded_wrapped_lines(self):
        for card in ("**Every identity is a synthetic test fixture, not a qualified model,\nhardware profile, or live endpoint.**", "This card does not promote\n> the model, its later SKUs, or any live endpoint."):
            with self.subTest(card=card):
                self.assertEqual([], production_claims(card))

    def test_previous_sentence_negation_does_not_hide_new_positive_claim(self):
        self.assertEqual(1, len(production_claims("Not qualified.\nFully operational.")))
        self.assertEqual(1, len(production_claims("Not qualified\nyet. Fully operational.")))

    def test_false_blocked_and_demoted_values_are_not_production_claims(self):
        for card in ("Production-ready: false.**", "| Promoted or production-ready status | **BLOCKED** | Metadata only. |", "| Promoted or production-ready status | **DEMOTED** | Historical. |", "Runtime state still\nrequires a separate live deployment receipt and provider readback;"):
            with self.subTest(card=card):
                self.assertEqual([], production_claims(card))

    def test_provider_deprecation_cannot_be_reactivated_by_source_card(self):
        review = classify(item("github", description="DEPRECATED. Canonical: https://github.com/szl-holdings/new", archived=False), observed("# Working implementation\nSource code and tests."), set())
        self.assertEqual("DEPRECATED", review["status"])
        self.assertEqual("successor_deprecated", review["classification"])
        self.assertEqual("record", review["canonical"]["role"])


class CaptureTests(unittest.TestCase):
    def test_bearer_header_cannot_redirect_to_other_provider(self):
        redirect = SameOriginRedirect()
        request = urllib.request.Request("https://api.github.com/repos/public/source", headers={"Authorization": "Bearer test-secret"})
        for target in ("https://huggingface.co/steal", "https://untrusted.invalid/steal", "http://api.github.com/steal", "https://api.github.com:443/steal", "https://user:pass@api.github.com/steal"):
            with self.subTest(target=target), self.assertRaises(SourceUnavailable):
                redirect.redirect_request(request, None, 302, "Found", {}, target)

    def test_same_origin_hf_cache_redirect_is_allowed(self):
        request = urllib.request.Request("https://huggingface.co/public/source/resolve/revision/README.md", headers={"Authorization": "Bearer test-secret"})
        result = SameOriginRedirect().redirect_request(request, None, 302, "Found", {}, "https://huggingface.co/api/resolve-cache/models/public/source/revision/README.md")
        self.assertEqual("Bearer test-secret", result.get_header("Authorization"))

    def test_token_origin_validation_precedes_network(self):
        reader = Reader("test-gh", "test-hf")
        for url, github in (("https://huggingface.co/", True), ("https://api.github.com/", False), ("https://api.github.com:8443/", True)):
            with self.subTest(url=url), self.assertRaises(SourceUnavailable):
                reader.read(url, github=github)

    def test_github_revision_is_pinned_and_retained_bytes_are_verified(self):
        artifact = item("github", source_revision=SHA)
        url = f"https://api.github.com/repos/szl-holdings/example/readme?ref={SHA}"
        api = "https://api.github.com/repos/szl-holdings/example"
        reader = FakeReader({api: {"full_name": "szl-holdings/example", "private": False}, url: {"encoding": "base64", "content": base64.b64encode(b"# Source\n").decode(), "path": "README.md"}})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            observation = capture(artifact, root, reader)
            self.assertEqual([api, url], reader.calls)
            self.assertEqual(SHA, observation["observed_revision"])
            self.assertIn(SHA, observation["evidence"][0]["url"])
            write_json(observation_path(root, artifact), observation)
            self.assertEqual(observation, load_observation(root, artifact))
            (root.parent.parent / observation["evidence"][0]["path"]).write_text("tampered")
            with self.assertRaisesRegex(ValueError, "content hash mismatch"):
                load_observation(root, artifact)

    def test_repository_relative_evidence_loads_outside_repository_cwd(self):
        artifact = item("github")
        url = f"https://api.github.com/repos/szl-holdings/example/readme?ref={SHA}"
        reader = FakeReader({"https://api.github.com/repos/szl-holdings/example": {"full_name": "szl-holdings/example", "private": False}, url: {"encoding": "base64", "content": base64.b64encode(b"# Source\n").decode(), "path": "README.md"}})
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as elsewhere:
            directory = Path(temp) / "data" / "source-evidence"
            observation = capture(artifact, directory, reader)
            self.assertTrue(observation["evidence"][0]["path"].startswith("data/source-evidence/"))
            write_json(observation_path(directory, artifact), observation)
            original = Path.cwd()
            try:
                os.chdir(elsewhere)
                self.assertEqual(observation, load_observation(directory, artifact))
            finally:
                os.chdir(original)

    def test_absolute_and_escaping_evidence_paths_are_rejected(self):
        artifact = item("github")
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "data" / "source-evidence"
            for path in (str(Path(temp) / "private.txt"), "../private.txt", "data/private.txt", "C:/private.txt", "data\\source-evidence\\private.txt"):
                observation = observed("content")
                observation["id"] = artifact["id"]
                observation["evidence"][0]["path"] = path
                write_json(observation_path(directory, artifact), observation)
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Unsafe evidence path"):
                    load_observation(directory, artifact)

    def test_hf_tree_and_card_share_exact_revision(self):
        metadata = f"https://huggingface.co/api/models/SZLHOLDINGS/example/revision/{SHA}"
        card = f"https://huggingface.co/SZLHOLDINGS/example/resolve/{SHA}/README.md"
        reader = FakeReader({metadata: {"sha": SHA, "private": False, "siblings": [{"rfilename": "README.md"}, {"rfilename": "model.safetensors"}]}, card: b"# Research\n"})
        with tempfile.TemporaryDirectory() as temp:
            observation = capture(item(), Path(temp), reader)
            self.assertEqual([metadata, card], reader.calls)
            self.assertEqual([], observation["errors"])
            self.assertEqual({SHA}, {entry["revision"] for entry in observation["evidence"]})
            self.assertEqual(["README.md", "model.safetensors"], observation["files"])

    def test_revision_mismatch_stops_before_card_fetch(self):
        metadata = f"https://huggingface.co/api/models/SZLHOLDINGS/example/revision/{SHA}"
        reader = FakeReader({metadata: {"sha": "b" * 40, "private": False}})
        with tempfile.TemporaryDirectory() as temp:
            observation = capture(item(), Path(temp), reader)
            self.assertEqual(["REVISION_MISMATCH"], observation["errors"])
            self.assertEqual([], observation["evidence"])
            self.assertEqual([metadata], reader.calls)

    def test_changed_private_visibility_stops_before_contents(self):
        metadata = f"https://huggingface.co/api/models/SZLHOLDINGS/example/revision/{SHA}"
        reader = FakeReader({metadata: {"sha": SHA, "private": True, "siblings": [{"rfilename": "README.md"}]}})
        with tempfile.TemporaryDirectory() as temp:
            observation = capture(item(), Path(temp), reader)
            self.assertEqual(["PUBLIC_VISIBILITY_NOT_CONFIRMED"], observation["errors"])
            self.assertEqual([], observation["evidence"])

    def test_source_request_failure_is_visible_and_never_promoted(self):
        url = f"https://api.github.com/repos/szl-holdings/example/readme?ref={SHA}"
        reader = FakeReader({"https://api.github.com/repos/szl-holdings/example": {"full_name": "szl-holdings/example", "private": False}, url: SourceUnavailable("HTTP_403")})
        with tempfile.TemporaryDirectory() as temp:
            observation = capture(item("github"), Path(temp), reader)
            review = classify(item("github"), observation, set())
            self.assertEqual("UNAVAILABLE_WITH_REASON", review["audit"]["status"])
            self.assertEqual(["HTTP_403"], observation["errors"])

    def test_github_private_transition_stops_before_readme_fetch(self):
        api = "https://api.github.com/repos/szl-holdings/example"
        reader = FakeReader({api: {"full_name": "szl-holdings/example", "private": True}})
        with tempfile.TemporaryDirectory() as temp:
            observation = capture(item("github"), Path(temp), reader)
            self.assertEqual(["PUBLIC_VISIBILITY_NOT_CONFIRMED"], observation["errors"])
            self.assertEqual([], observation["evidence"])
            self.assertEqual([api], reader.calls)

    def test_github_identity_mismatch_stops_before_readme_fetch(self):
        api = "https://api.github.com/repos/szl-holdings/example"
        reader = FakeReader({api: {"full_name": "szl-holdings/other", "private": False}})
        with tempfile.TemporaryDirectory() as temp:
            observation = capture(item("github"), Path(temp), reader)
            self.assertEqual(["REPOSITORY_IDENTITY_MISMATCH"], observation["errors"])
            self.assertEqual([], observation["evidence"])
            self.assertEqual([api], reader.calls)


if __name__ == "__main__":
    unittest.main()
