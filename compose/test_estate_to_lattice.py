from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from compose.evidence_lattice import EvidenceError, assess_snapshot
from tools.estate_to_lattice import _public_http_uri, _write_new, build_snapshot

REVISION = "d" * 40


class EstateToLatticeTests(unittest.TestCase):
    def test_only_expected_public_space_origin_can_be_exported(self) -> None:
        expected = "szlholdings-public-space.hf.space"
        for uri in ("https://127.0.0.1/", "https://10.0.0.1/", "https://169.254.169.254/",
                    "https://[::1]/", "https://[fc00::1]/", "https://localhost/",
                    "https://database.internal/", "https://private-service/",
                    "https://szlholdings-other-space.hf.space/",
                    f"https://{expected}.evil.invalid/", f"http://{expected}/",
                    f"https://{expected}:8443/", f"https://user:password@{expected}/"):
            with self.subTest(uri=uri):
                self.assertIsNone(_public_http_uri(uri, expected))
        self.assertEqual(_public_http_uri(f"https://{expected}:443/path?x=y#z", expected),
                         f"https://{expected}/")
        static = "szlholdings-readme.static.hf.space"
        self.assertEqual(_public_http_uri(f"https://{static}/index.html", static),
                         f"https://{static}/")

    def test_internal_redirect_does_not_relabel_status_as_public_origin(self) -> None:
        candidate = build_snapshot(
            models=[], datasets=[],
            spaces=[{"id": "SZLHOLDINGS/public-space", "private": False, "sha": REVISION}],
            github={"repositories": [], "captured_at_utc": "2026-09-05T16:00:00Z"},
            space_witness=[{
                "id": "SZLHOLDINGS/public-space", "private": False, "sha": REVISION,
                "final_uri": "https://database.internal/secret", "http_status": 200,
                "host": "https://szlholdings-public-space.hf.space/",
                "observed_at": "2026-09-05T16:00:00Z",
            }],
            observed_at="2026-09-05T16:00:00Z", hf_observed_at="2026-09-05T16:00:00Z",
        )
        self.assertNotIn("runtime", candidate["assets"][0]["layers"])
        self.assertNotIn("database.internal", json.dumps(candidate))

    def test_live_runtime_refresh_supersedes_embedded_metadata(self) -> None:
        for live in ({"stage": "RUNNING", "raw": {"sha": "e" * 40}}, None):
            with self.subTest(live=live):
                candidate = build_snapshot(
                    models=[], datasets=[],
                    spaces=[{
                        "id": "SZLHOLDINGS/public-space", "private": False,
                        "sha": REVISION,
                        "runtime": {"stage": "RUNNING", "raw": {"sha": REVISION}},
                        "audit_observed_at": "2026-09-05T16:00:00Z",
                        "audit_live_runtime": live,
                        "audit_live_runtime_observed_at": "2026-09-05T16:01:00Z",
                    }],
                    github={"repositories": [], "captured_at_utc": "2026-09-05T16:00:00Z"},
                    space_witness=[], observed_at="2026-09-05T16:02:00Z",
                    hf_observed_at="2026-09-05T16:00:00Z",
                )
                deployment = candidate["assets"][0]["layers"]["deployment"]
                self.assertEqual(deployment["state"], "FAIL" if live else "UNKNOWN")
                self.assertEqual(deployment["subject_revision"], "e" * 40 if live else None)
                self.assertEqual(deployment["evidence"][0]["observed_at"],
                                 "2026-09-05T16:01:00Z")

    def test_snapshot_publication_cannot_overwrite_a_racing_writer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "snapshot.json"

            def competing_writer(source, target):
                Path(target).write_text('{"competing": true}', encoding="utf-8")
                raise FileExistsError("destination was created concurrently")

            with mock.patch("compose.evidence_lattice.os.link", competing_writer):
                with self.assertRaises(EvidenceError):
                    _write_new(destination, {"our_snapshot": True})
            self.assertEqual(json.loads(destination.read_text()), {"competing": True})
            self.assertEqual(list(Path(directory).iterdir()), [destination])

    def _snapshot(self) -> dict:
        models = [
            {
                "id": "SZLHOLDINGS/public-model",
                "private": False,
                "sha": REVISION,
                "tags": ["text-generation"],
                "siblings": [{"rfilename": "model.safetensors"}],
            },
            {
                "id": "SZLHOLDINGS/private-model-name",
                "private": True,
                "sha": REVISION,
            },
            {
                "id": "SZLHOLDINGS/unknown-visibility-model-name",
                "sha": REVISION,
            },
        ]
        datasets = [
            {
                "id": "SZLHOLDINGS/public-data",
                "private": False,
                "sha": REVISION,
                "siblings": [{"rfilename": "data.jsonl"}],
            }
        ]
        spaces = [
            {
                "id": "SZLHOLDINGS/public-space",
                "private": False,
                "sha": REVISION,
                "runtime": {"stage": "RUNNING"},
            }
        ]
        github = {
            "captured_at_utc": "2026-09-05T16:00:00Z",
            "repositories": [
                {
                    "full_name": "szl-holdings/live",
                    "html_url": "https://github.com/szl-holdings/live",
                    "private": False,
                    "archived": False,
                    "default_branch_head": {
                        "target": {
                            "oid": REVISION,
                            "signature": {"state": "VALID"},
                            "statusCheckRollup": {"state": "SUCCESS"},
                        }
                    },
                },
                {
                    "full_name": "szl-holdings/archive",
                    "html_url": "https://github.com/szl-holdings/archive",
                    "private": False,
                    "archived": True,
                    "default_branch_head": {"target": {"oid": REVISION}},
                },
                {
                    "full_name": "szl-holdings/private-repo-name",
                    "private": True,
                    "archived": False,
                },
                {
                    "full_name": "szl-holdings/unknown-visibility-repo-name",
                    "archived": False,
                },
            ]
        }
        witness = [
            {
                "id": "SZLHOLDINGS/public-space",
                "private": False,
                "sha": REVISION,
                "http_status": 200,
                "observed_at": "2026-09-05T16:00:00Z",
                "final_uri": (
                    "https://szlholdings-public-space.hf.space/?token=must-not-publish#x"
                ),
            }
        ]
        return build_snapshot(
            models=models,
            datasets=datasets,
            spaces=spaces,
            github=github,
            space_witness=witness,
            observed_at="2026-09-05T16:00:00Z",
            hf_observed_at="2026-09-05T16:00:00Z",
        )

    def test_private_asset_names_are_excluded(self) -> None:
        snapshot = self._snapshot()
        ids = {asset["id"] for asset in snapshot["assets"]}
        self.assertNotIn("SZLHOLDINGS/private-model-name", ids)
        self.assertNotIn("SZLHOLDINGS/unknown-visibility-model-name", ids)
        self.assertNotIn("szl-holdings/private-repo-name", ids)
        self.assertNotIn("szl-holdings/unknown-visibility-repo-name", ids)
        self.assertEqual(len(ids), 5)

    def test_space_stage_and_http_are_distinct_layers(self) -> None:
        snapshot = self._snapshot()
        space = next(
            asset for asset in snapshot["assets"] if asset["kind"] == "space"
        )
        self.assertEqual(
            space["layers"]["deployment"]["evidence"][0]["observation"],
            "PROVIDER_OBSERVED",
        )
        self.assertEqual(
            space["layers"]["runtime"]["evidence"][0]["observation"],
            "DIRECT_OBSERVATION",
        )
        self.assertIsNone(
            space["layers"]["runtime"]["evidence"][0]["subject_revision"]
        )
        self.assertIsNone(space["layers"]["runtime"]["subject_revision"])
        self.assertEqual(
            space["layers"]["runtime"]["evidence"][0]["uri"],
            "https://szlholdings-public-space.hf.space/",
        )
        decision = assess_snapshot(
            snapshot, "operate", ["SZLHOLDINGS/public-space"]
        )["decisions"][0]
        self.assertFalse(decision["evidence_complete"])
        self.assertEqual(
            {
                item["layer"]
                for item in decision["blockers"]
                if item["code"] == "REQUIRED_LAYER_MISSING"
            },
            {"source", "provenance", "controller"},
        )
        self.assertIn(
            "NO_REVISION_BOUND_QUALIFYING_EVIDENCE",
            {item["code"] for item in decision["blockers"]},
        )

    def test_weight_filename_is_artifact_not_evaluation(self) -> None:
        snapshot = self._snapshot()
        model = next(
            asset for asset in snapshot["assets"] if asset["kind"] == "model"
        )
        self.assertIn("artifact", model["layers"])
        self.assertEqual(model["layers"]["artifact"]["state"], "UNKNOWN")
        self.assertNotIn("evaluation", model["layers"])
        self.assertFalse(
            assess_snapshot(
                snapshot, "promote", ["SZLHOLDINGS/public-model"]
            )["all_evidence_complete"]
        )

    def test_witness_visibility_must_be_explicit_and_ids_unique(self) -> None:
        unknown_visibility = [
            {
                "id": "SZLHOLDINGS/public-space",
                "sha": REVISION,
                "http_status": 200,
                "final_uri": "https://szlholdings-public-space.hf.space/",
            }
        ]
        snapshot = build_snapshot(
            models=[],
            datasets=[],
            spaces=[
                {
                    "id": "SZLHOLDINGS/public-space",
                    "private": False,
                    "sha": REVISION,
                    "runtime": {
                        "stage": "RUNNING",
                        "raw": {"sha": REVISION},
                    },
                }
            ],
            github={"repositories": [], "captured_at_utc": "2026-09-05T16:00:00Z"},
            space_witness=unknown_visibility,
            observed_at="2026-09-05T16:00:00Z",
            hf_observed_at="2026-09-05T16:00:00Z",
        )
        self.assertNotIn("runtime", snapshot["assets"][0]["layers"])

        duplicate = [
            {**unknown_visibility[0], "private": False},
            {**unknown_visibility[0], "private": False},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate id"):
            build_snapshot(
                models=[],
                datasets=[],
                spaces=[],
                github={"repositories": [], "captured_at_utc": "2026-09-05T16:00:00Z"},
                space_witness=duplicate,
                observed_at="2026-09-05T16:00:00Z",
                hf_observed_at="2026-09-05T16:00:00Z",
            )

    def test_archived_repository_is_historical(self) -> None:
        snapshot = self._snapshot()
        archived = next(
            asset
            for asset in snapshot["assets"]
            if asset["id"] == "szl-holdings/archive"
        )
        self.assertEqual(archived["disposition"], "HISTORICAL")

    def test_green_rollup_is_ci_only(self) -> None:
        snapshot = self._snapshot()
        repo = next(
            asset
            for asset in snapshot["assets"]
            if asset["id"] == "szl-holdings/live"
        )
        self.assertEqual(repo["layers"]["ci"]["state"], "PASS")
        decision = assess_snapshot(
            snapshot, "publish", ["szl-holdings/live"]
        )["decisions"][0]
        self.assertFalse(decision["evidence_complete"])
        self.assertEqual(
            {
                item["layer"]
                for item in decision["blockers"]
                if item["code"] == "REQUIRED_LAYER_MISSING"
            },
            {"provenance", "controller"},
        )


if __name__ == "__main__":
    unittest.main()
