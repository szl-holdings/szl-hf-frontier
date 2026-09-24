from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from tools import capture_estate_snapshots as collector


def hf_row(name: str, private: bool = False) -> dict:
    return {"id": "SZLHOLDINGS/" + name, "private": private, "sha": "a" * 40,
            "tags": ["license:apache-2.0"], "runtime": {"stage": "RUNNING"}}


def gh_row(index: int = 1, private: bool = False) -> dict:
    return {"id": index, "full_name": f"szl-holdings/repo-{index}", "private": private,
            "html_url": f"https://github.com/szl-holdings/repo-{index}", "default_branch": "main",
            "license": {"spdx_id": "Apache-2.0"}}


def fake_api(url, token=None, *, provider):
    path = urllib.parse.urlsplit(url).path
    if path == "/user":
        return {"login": "fixture-identity"}, {}
    if path.startswith("/user/memberships/"):
        return {"state": "active", "organization": {"login": "szl-holdings"}}, {}
    if path == "/api/whoami-v2":
        return {"name": "fixture-identity", "orgs": [{"name": "SZLHOLDINGS"}]}, {}
    if "/commits/" in path:
        return {"sha": "b" * 40}, {}
    if path == "/orgs/szl-holdings/repos":
        return [gh_row(), gh_row(2, True)], {}
    return [hf_row("public"), hf_row("private-fixture", True)], {}


@contextlib.contextmanager
def successful_capture(root):
    with (mock.patch.dict(os.environ, {"GH_TOKEN": "secret-gh", "HF_TOKEN": "secret-hf"}, clear=True),
          mock.patch.object(collector, "request_json", side_effect=fake_api),
          mock.patch.object(collector, "source_identity", return_value={"git_sha": "c" * 40})):
        yield collector.capture(root)


class PaginationTests(unittest.TestCase):
    def test_github_numeric_organization_pagination_matches_observed_owner(self):
        start = collector.inventory_url("github", True)
        second = start.replace("/orgs/szl-holdings/", "/organizations/273360816/") + "&page=2"
        first = second.replace("page=2", "page=1")
        owner = {"id": 273360816, "login": "szl-holdings"}
        responses = {start: ([dict(gh_row(i + 1), owner=owner) for i in range(100)],
                             {"link": f'<{second}>; rel="next", <{second}>; rel="last"'}),
                     second: ([dict(gh_row(101), owner=owner)],
                              {"link": f'<{first}>; rel="prev", <{first}>; rel="first"'})}
        with mock.patch.object(collector, "request_json", side_effect=lambda url, *a, **kw: responses[url]):
            result = collector.collect_inventory("github", "fixture", 10)
        self.assertEqual(result.completion, "COMPLETE")
        self.assertEqual(result.count, 101)
        self.assertEqual(result.pages_fetched, 2)

    def test_github_numeric_alias_cannot_change_organization_or_query(self):
        start = collector.inventory_url("github", True)
        alias = start.replace("/orgs/szl-holdings/", "/organizations/273360816/") + "&page=2"
        owner = {"id": 273360816, "login": "szl-holdings"}
        for candidate, rows in (
            (alias.replace("273360816", "999"), [dict(gh_row(), owner=owner)]),
            (alias + "&type=public", [dict(gh_row(), owner=owner)]),
            (alias.replace("api.github.com", "evil.example"), [dict(gh_row(), owner=owner)]),
            (alias, [gh_row()]),
            (alias, [dict(gh_row(), owner={"id": 273360816, "login": "OTHER"})]),
            (alias, [dict(gh_row(), owner=owner), dict(gh_row(2), owner={"id": 999, "login": "szl-holdings"})]),
        ):
            with self.subTest(candidate=candidate, rows=rows), mock.patch.object(collector, "request_json", return_value=(rows, {"link": f'<{candidate}>; rel="next"'})) as fetch:
                result = collector.collect_inventory("github", "fixture", 10)
            self.assertIsNone(result.count)
            self.assertEqual(fetch.call_count, 1)

    def test_hf_multiple_pages_preserve_private_scope_counts(self):
        start = collector.inventory_url("models", True)
        second = start + "&cursor=next"
        responses = {start: ([hf_row(str(i)) for i in range(100)], {"link": f'<{second}>; rel="next"'}),
                     second: ([hf_row("private", True)], {})}
        with mock.patch.object(collector, "request_json", side_effect=lambda url, *a, **kw: responses[url]):
            result = collector.collect_inventory("models", "fixture", 10)
        self.assertEqual(result.completion, "COMPLETE")
        self.assertEqual(result.count, 101)
        self.assertEqual(result.pages_fetched, 2)
        self.assertEqual(result.private_items_seen, 1)

    def test_github_more_than_nineteen_pages_is_not_silently_truncated(self):
        start = collector.inventory_url("github", True)
        def response(url, *args, **kwargs):
            page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("page", ["1"])[0])
            links = {"link": f'<{start}&page={page + 1}>; rel="next"'} if page < 21 else {}
            return [gh_row(page)], links
        with mock.patch.object(collector, "request_json", side_effect=response):
            result = collector.collect_inventory("github", "fixture", 30)
        self.assertEqual(result.count, 21)
        self.assertEqual(result.pages_fetched, 21)

    def test_incomplete_pagination_never_has_final_count(self):
        start = collector.inventory_url("models", True)
        scenarios = [
            ([hf_row(str(i)) for i in range(100)], {}, 10, "MISSING_PAGINATION_LINK"),
            ([hf_row("one")], {"link": f'<{start}&cursor=next>; rel="next"'}, 1, "PAGE_CEILING"),
            ([hf_row("one")], {"link": f'<{start}>; rel="next"'}, 10, "PAGINATION_CYCLE"),
            ([hf_row("same"), hf_row("same")], {}, 10, "DUPLICATE_ITEM_ID"),
        ]
        for rows, headers, pages, failure in scenarios:
            with self.subTest(failure=failure), mock.patch.object(collector, "request_json", return_value=(rows, headers)):
                result = collector.collect_inventory("models", "fixture", pages)
            self.assertIsNone(result.count)
            self.assertEqual(result.failure, failure)

    def test_off_origin_and_filter_drift_links_are_rejected_before_request(self):
        start = collector.inventory_url("models", True)
        for next_url in ("https://evil.example/api/models", start + "&author=OTHER", start + "&search=hidden", "http://huggingface.co/api/models"):
            with self.subTest(url=next_url), mock.patch.object(collector, "request_json", return_value=([hf_row("one")], {"link": f'<{next_url}>; rel="next"'})) as fetch:
                result = collector.collect_inventory("models", "secret", 10)
            self.assertIsNone(result.count)
            self.assertEqual(fetch.call_count, 1)

    def test_later_http_failure_keeps_observed_count_only(self):
        start = collector.inventory_url("models", True)
        with mock.patch.object(collector, "request_json", side_effect=[([hf_row("one")], {"link": f'<{start}&cursor=next>; rel="next"'}), collector.CollectionError("HTTP_503")]):
            result = collector.collect_inventory("models", "fixture", 10)
        self.assertIsNone(result.count)
        self.assertEqual(result.summary()["observed_unique_count"], 1)
        self.assertEqual(result.failure, "HTTP_503")

    def test_wrong_org_and_unknown_visibility_fail_closed(self):
        rows = [dict(hf_row("one"), id="OTHER/one"), dict(hf_row("one"), private="false")]
        for row in rows:
            with self.subTest(row=row), mock.patch.object(collector, "request_json", return_value=([row], {})):
                self.assertIsNone(collector.collect_inventory("models", "fixture", 10).count)


class CredentialAndMetadataTests(unittest.TestCase):
    def test_help_never_resolves_credentials_or_touches_network(self):
        with (mock.patch.object(collector, "resolve_credentials", side_effect=AssertionError("credential read")),
              mock.patch.object(collector, "request_json", side_effect=AssertionError("network")),
              contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result):
            collector.main(["--help"])
        self.assertEqual(result.exception.code, 0)

    def test_missing_authentication_fails_before_network(self):
        with mock.patch.object(collector, "request_json") as request:
            with self.assertRaisesRegex(collector.CollectionError, "AUTHENTICATION_REQUIRED"):
                collector.validate_identities({"github": "", "huggingface": ""}, {})
        request.assert_not_called()

    def test_public_only_does_not_read_cached_credentials(self):
        with mock.patch.object(collector.subprocess, "run", side_effect=AssertionError("cache access")):
            tokens, summaries = collector.resolve_credentials(True)
        self.assertEqual(set(tokens.values()), {""})
        self.assertFalse(summaries["github"]["present"])

    def test_untrusted_origins_never_receive_requests(self):
        for url in ("https://api.github.com.evil.example/x", "http://api.github.com/x", "https://user@api.github.com/x", "https://api.github.com:8443/x"):
            with self.subTest(url=url), mock.patch.object(collector.urllib.request, "build_opener") as opener:
                with self.assertRaisesRegex(collector.CollectionError, "UNSAFE_REQUEST_ORIGIN"):
                    collector.request_json(url, "secret", provider="github")
                opener.assert_not_called()

    def test_network_exceptions_are_redacted(self):
        opener = mock.Mock()
        opener.open.side_effect = RuntimeError("secret-token private-repository")
        with mock.patch.object(collector.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(collector.CollectionError, "^NETWORK_ERROR$"):
                collector.request_json("https://api.github.com/user", "secret-token", provider="github")

    def test_space_revision_license_runtime_are_preserved(self):
        row = hf_row("demo")
        row.pop("runtime")
        detail = dict(row, cardData={"license": "mit"}, runtime={"stage": "RUNNING"})
        with mock.patch.object(collector, "request_json", return_value=(detail, {})):
            normalized = collector.enrich_item("spaces", row, "fixture")
        self.assertEqual(normalized["sha"], "a" * 40)
        self.assertEqual(normalized["license"], "mit")
        self.assertEqual(normalized["runtime"], {"stage": "RUNNING"})

    def test_metadata_visibility_change_fails_capture(self):
        row = hf_row("demo")
        row.pop("runtime")
        with mock.patch.object(collector, "request_json", return_value=(dict(row, private=True), {})):
            with self.assertRaisesRegex(collector.CollectionError, "VISIBILITY_CHANGED"):
                collector.enrich_item("spaces", row, "fixture")


class ReceiptTests(unittest.TestCase):
    def test_complete_capture_has_hashes_times_and_validated_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with successful_capture(root) as receipt:
                self.assertTrue(receipt["complete"])
            verified = collector.verify_snapshot_set(root)
            self.assertEqual(verified["signature_status"], "UNSIGNED")
            self.assertTrue(verified["credentials"]["github"]["identity_validated"])
            self.assertFalse(verified["credentials"]["github"]["all_private_resources_visible"])
            self.assertLessEqual(verified["started_at"], verified["completed_at"])
            self.assertNotIn("secret-gh", json.dumps(verified))
            self.assertNotIn("secret-hf", json.dumps(verified))
            self.assertEqual(len(verified["files"]), 4)

    def test_public_projection_has_no_private_names_counts_or_identities(self):
        with tempfile.TemporaryDirectory() as temp:
            root, public = Path(temp) / "raw", Path(temp) / "public"
            with successful_capture(root):
                receipt = collector.export_public_snapshot(root, public)
            collector.verify_snapshot_set(public)
            text = "".join(path.read_text(encoding="utf-8") for path in public.glob("*.json"))
            for private in ("private-fixture", "repo-2", "fixture-identity", "private_items_seen", "observed_unique_count"):
                self.assertNotIn(private, text)
            self.assertEqual(receipt["scope"], "PUBLIC_PROJECTION_OF_AUTHENTICATED_CENSUS")
            self.assertEqual(receipt["parent_receipt_sha256"], collector.sha256(root / collector.RECEIPT))
            self.assertEqual(receipt["files"]["huggingface_models.json"]["count"], 1)

    def test_failure_invalidates_old_success_and_does_not_publish_partial_arrays(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with successful_capture(root):
                pass
            previous = (root / "huggingface_models.json").read_bytes()
            incomplete = collector.PaginatedInventory(scope="TOKEN_VISIBLE", completion="INCOMPLETE", failure="HTTP_503")
            with (mock.patch.object(collector, "source_identity", return_value={}),
                  mock.patch.object(collector, "resolve_credentials", return_value=({"github": "x", "huggingface": "y"}, {})),
                  mock.patch.object(collector, "validate_identities"),
                  mock.patch.object(collector, "collect_inventory", return_value=incomplete)):
                receipt = collector.capture(root)
            self.assertFalse(receipt["complete"])
            self.assertEqual(previous, (root / "huggingface_models.json").read_bytes())
            with self.assertRaisesRegex(collector.CollectionError, "INCOMPLETE"):
                collector.verify_snapshot_set(root)

    def test_tampered_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with successful_capture(root):
                pass
            (root / "huggingface_models.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(collector.CollectionError, "HASH_MISMATCH"):
                collector.verify_snapshot_set(root)


if __name__ == "__main__":
    unittest.main()
