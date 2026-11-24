from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
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


class BoundedProviderRetryTests(unittest.TestCase):
    class Response:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, limit):
            return b'{"ok":true}'[:limit]

    def exercise(self, provider, steps, *, budget_clock=None):
        calls, sleeps = [], []
        clock = [0.0] if budget_clock is None else budget_clock

        class Opener:
            def open(self, request, timeout):
                calls.append((request.full_url, request.get_header("Authorization")))
                code, headers = steps[min(len(calls) - 1, len(steps) - 1)]
                if code != 200:
                    raise urllib.error.HTTPError(request.full_url, code, "provider refused", headers, None)
                return BoundedProviderRetryTests.Response()

        def snooze(seconds):
            sleeps.append(seconds)
            clock[0] += seconds

        url = ("https://huggingface.co/api/models?author=SZLHOLDINGS"
               if provider == "huggingface" else "https://api.github.com/orgs/szl-holdings/repos")
        with mock.patch.object(collector.urllib.request, "build_opener", return_value=Opener()):
            try:
                result = collector.request_json(
                    url, "fake-test-credential", provider=provider,
                    sleep_fn=snooze, monotonic=lambda: clock[0], wall_clock=lambda: 1000.0,
                )
                return result, calls, sleeps, None
            except collector.CollectionError as error:
                return None, calls, sleeps, str(error)

    def test_hf_retry_after_within_budget_succeeds(self):
        result, calls, sleeps, error = self.exercise("huggingface",
            [(429, {"Retry-After": "2"}), (200, {})])
        self.assertIsNone(error)
        self.assertEqual(result[0], {"ok": True})
        self.assertEqual([2.0], sleeps)
        self.assertEqual(2, len(calls))

    def test_hf_ratelimit_reset_outside_budget_halts_without_retry(self):
        result, calls, sleeps, error = self.exercise("huggingface",
            [(429, {"RateLimit": '"api";r=0;t=301'})])
        self.assertIsNone(result)
        self.assertEqual("HTTP_429_RATE_LIMITED", error)
        self.assertEqual(1, len(calls))
        self.assertEqual([], sleeps)

    def test_hf_repeated_429_exhausts_exact_attempt_cap(self):
        result, calls, sleeps, error = self.exercise("huggingface", [(429, {})])
        self.assertEqual("HTTP_429_RATE_LIMITED", error)
        self.assertEqual(3, len(calls))
        self.assertEqual([1.0, 2.0], sleeps)
        self.assertIsNone(result)

    def test_github_permission_403_never_retried(self):
        result, calls, sleeps, error = self.exercise("github", [(403, {})])
        self.assertIsNone(result)
        self.assertEqual("HTTP_403", error)
        self.assertEqual(1, len(calls))
        self.assertEqual([], sleeps)

    def test_github_primary_limit_403_reset_within_budget(self):
        result, calls, sleeps, error = self.exercise("github",
            [(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1002"}), (200, {})])
        self.assertIsNone(error)
        self.assertEqual(result[0], {"ok": True})
        self.assertEqual([2.0], sleeps)
        self.assertEqual(2, len(calls))

    def test_github_reset_far_in_future_does_not_wait(self):
        result, calls, sleeps, error = self.exercise("github",
            [(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "5000"})])
        self.assertEqual("HTTP_403_RATE_LIMITED", error)
        self.assertEqual(1, len(calls))
        self.assertEqual([], sleeps)

    def test_malformed_retry_after_never_causes_negative_sleep(self):
        for bad in ("abc", "-5", "not-a-date"):
            with self.subTest(bad=bad):
                _, calls, sleeps, error = self.exercise("huggingface",
                    [(429, {"Retry-After": bad}), (200, {})])
                self.assertIsNone(error)
                self.assertEqual([1.0], sleeps)
                self.assertEqual(2, len(calls))

    def test_wait_budget_is_cumulative_over_attempts(self):
        result, calls, sleeps, error = self.exercise("huggingface", [
            (429, {"Retry-After": "15"}),
            (429, {"Retry-After": "15"}),
            (200, {}),
        ])
        self.assertIsNone(result)
        self.assertEqual("HTTP_429_RATE_LIMITED", error)
        self.assertEqual([15.0], sleeps)
        self.assertEqual(2, len(calls))

    def test_github_secondary_403_retry_after_retries(self):
        result, calls, sleeps, error = self.exercise("github", [
            (403, {"Retry-After": "2"}), (200, {}),
        ])
        self.assertIsNone(error)
        self.assertEqual(result[0], {"ok": True})
        self.assertEqual([2.0], sleeps)
        self.assertEqual(2, len(calls))

    def test_http_date_header_is_respected(self):
        result, calls, sleeps, error = self.exercise("huggingface", [
            (429, {"Retry-After": "Thu, 01 Jan 1970 00:16:42 GMT"}),
            (200, {}),
        ])
        self.assertIsNone(error)
        self.assertEqual([2.0], sleeps)
        self.assertEqual(2, len(calls))

    def test_trusted_request_only_and_no_secret_in_error(self):
        _, calls, sleeps, error = self.exercise("huggingface", [(429, {"Retry-After": "800"})])
        self.assertEqual("HTTP_429_RATE_LIMITED", error)
        self.assertNotIn("fake-test-credential", error)
        self.assertTrue(all(auth == "Bearer fake-test-credential" for _, auth in calls))
        self.assertEqual([], sleeps)


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
    def test_authenticated_capture_cannot_overwrite_committed_projection(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(collector, "ROOT", Path(temp)):
            public = Path(temp) / "data/snapshots"
            public.mkdir(parents=True)
            marker = public / collector.RECEIPT
            marker.write_text("original-public-receipt")
            for target in (public, public / "nested"):
                with self.subTest(target=target), mock.patch.object(collector, "resolve_credentials") as creds:
                    with self.assertRaisesRegex(collector.CollectionError, "CAPTURE_REQUIRES_LOCAL_OUTPUT"):
                        collector.capture(target)
                    creds.assert_not_called()
            self.assertEqual(marker.read_text(), "original-public-receipt")

    def test_default_capture_is_ignored_local_directory(self):
        with mock.patch.object(collector, "capture", return_value={"complete": True, "scope": "TOKEN_VISIBLE"}) as capture, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(collector.main([]), 0)
        self.assertEqual(capture.call_args.args[0], collector.ROOT / ".estate-private/snapshots")

    def test_private_directory_alias_cannot_redirect_capture_into_tracked_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            private, tracked = root / ".estate-private", root / "tracked"
            original = Path.resolve

            def redirected(path, *args, **kwargs):
                resolved = original(path, *args, **kwargs)
                if resolved.is_relative_to(private):
                    return tracked / resolved.relative_to(private)
                return resolved

            # Simulate a directory junction without requiring Windows link privileges.
            with (mock.patch.object(collector, "ROOT", root),
                  mock.patch.object(Path, "resolve", redirected),
                  mock.patch.object(collector, "resolve_credentials") as credentials):
                with self.assertRaisesRegex(collector.CollectionError, "PRIVATE_OUTPUT"):
                    collector.capture(private / "snapshots")
                credentials.assert_not_called()

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

    def test_snapshot_count_requires_a_json_integer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with successful_capture(root) as receipt:
                filename = collector.FILES["spaces"]
                collector.write_json(root / filename, [])
                record = receipt["files"][filename]
                record.update(sha256=collector.sha256(root / filename), count=0)
                collector.write_json(root / collector.RECEIPT, receipt)
                collector.verify_snapshot_set(root)
                for count in (False, 0.0):
                    with self.subTest(count=count):
                        record["count"] = count
                        collector.write_json(root / collector.RECEIPT, receipt)
                        with self.assertRaisesRegex(collector.CollectionError, "SNAPSHOT_COUNT_MISMATCH"):
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
