import json
import os
import unittest
from email.message import Message
from unittest import mock

import szl_estate_operational as estate


HF_START = "https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100"
HF_PAGE_2 = (
    "https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100&cursor=page-2"
)
GH_START = "https://api.github.com/orgs/szl-holdings/repos?per_page=100&type=public"
GH_PAGE_2 = GH_START + "&page=2"


def response_map(rows):
    def fake_fetch(url):
        return rows[url]

    return fake_fetch


class PaginationTests(unittest.TestCase):
    def test_collects_multiple_pages_and_private_rows(self):
        responses = {
            HF_START: (
                200,
                json.dumps(
                    [
                        {"id": "SZLHOLDINGS/public", "private": False},
                        {"id": "SZLHOLDINGS/private", "private": True},
                    ]
                ),
                {"link": f'<{HF_PAGE_2}>; rel="next"'},
            ),
            HF_PAGE_2: (
                200,
                json.dumps([{"id": "SZLHOLDINGS/third"}]),
                {},
            ),
        }
        with mock.patch.object(
            estate,
            "fetch_response",
            side_effect=response_map(responses),
        ):
            result = estate.collect_paginated_inventory(
                HF_START,
                scope="TOKEN_VISIBLE",
            )

        self.assertEqual(result.completion, "COMPLETE")
        self.assertEqual(result.count, 3)
        self.assertEqual(result.pages_fetched, 2)
        self.assertEqual(result.private_items_seen, 1)
        self.assertTrue(estate.threshold_result(result, minimum=3))

    def test_github_count_over_one_hundred_is_not_truncated(self):
        first_page = [{"id": row} for row in range(1, 101)]
        second_page = [{"id": row} for row in range(101, 124)]
        responses = {
            GH_START: (
                200,
                json.dumps(first_page),
                {"link": f'<{GH_PAGE_2}>; rel="next"'},
            ),
            GH_PAGE_2: (200, json.dumps(second_page), {}),
        }
        with mock.patch.object(
            estate,
            "fetch_response",
            side_effect=response_map(responses),
        ):
            result = estate.collect_paginated_inventory(
                GH_START,
                scope="PUBLIC_ONLY",
            )

        self.assertEqual(result.completion, "COMPLETE")
        self.assertEqual(result.count, 123)
        self.assertTrue(estate.threshold_result(result, minimum=80))

    def test_full_page_without_link_cannot_be_called_complete(self):
        with mock.patch.object(
            estate,
            "fetch_response",
            return_value=(
                200,
                json.dumps([{"id": row} for row in range(1, 101)]),
                {},
            ),
        ):
            result = estate.collect_paginated_inventory(
                GH_START,
                scope="PUBLIC_ONLY",
            )

        self.assertEqual(result.completion, "INCOMPLETE")
        self.assertEqual(result.failure, "MISSING_PAGINATION_LINK")
        self.assertIsNone(estate.threshold_result(result, minimum=80))

    def test_unrelated_link_does_not_certify_full_page(self):
        for relation in ("canonical", "alternate", "stylesheet", "nexxt"):
            with (
                self.subTest(relation=relation),
                mock.patch.object(
                    estate,
                    "fetch_response",
                    return_value=(
                        200,
                        json.dumps([{"id": row} for row in range(1, 101)]),
                        {"link": f'<{GH_START}>; rel="{relation}"'},
                    ),
                ),
            ):
                result = estate.collect_paginated_inventory(
                    GH_START, scope="PUBLIC_ONLY"
                )
            self.assertEqual(result.failure, "MISSING_PAGINATION_LINK")
            self.assertIsNone(result.count)
            self.assertIsNone(estate.threshold_result(result, 80))

    def test_full_final_page_with_pagination_header_is_complete(self):
        previous = GH_START + "&page=1"
        with mock.patch.object(
            estate,
            "fetch_response",
            return_value=(
                200,
                json.dumps([{"id": row} for row in range(1, 101)]),
                {"link": f'<{previous}>; rel="prev"'},
            ),
        ):
            result = estate.collect_paginated_inventory(
                GH_START,
                scope="PUBLIC_ONLY",
            )

        self.assertEqual(result.completion, "COMPLETE")
        self.assertEqual(result.count, 100)

    def test_last_link_beyond_current_page_cannot_certify_completion(self):
        headers = (
            f'<{GH_PAGE_2}>; rel="last"',
            f'<{GH_START}>; rel="first", <{GH_PAGE_2}>; rel="last"',
        )
        for header in headers:
            with (
                self.subTest(header=header),
                mock.patch.object(
                    estate,
                    "fetch_response",
                    return_value=(
                        200,
                        json.dumps([{"id": row} for row in range(1, 101)]),
                        {"link": header},
                    ),
                ) as fetch,
            ):
                result = estate.collect_paginated_inventory(
                    GH_START,
                    scope="PUBLIC_ONLY",
                )

            self.assertEqual(result.completion, "INCOMPLETE")
            self.assertEqual(result.failure, "NONTERMINAL_LAST_LINK")
            self.assertIsNone(result.count)
            self.assertIsNone(estate.threshold_result(result, minimum=80))
            self.assertEqual(fetch.call_count, 1)

    def test_last_link_to_current_page_can_certify_completion(self):
        with mock.patch.object(
            estate,
            "fetch_response",
            return_value=(
                200,
                json.dumps([{"id": row} for row in range(1, 101)]),
                {"link": f'<{GH_START}>; rel="last"'},
            ),
        ):
            result = estate.collect_paginated_inventory(
                GH_START,
                scope="PUBLIC_ONLY",
            )

        self.assertEqual(result.completion, "COMPLETE")
        self.assertEqual(result.count, 100)

    def test_malformed_and_ambiguous_links_do_not_certify_completion(self):
        headers = (
            "not-a-link",
            f'<{HF_PAGE_2}>; rel="next',
            f'<{HF_PAGE_2}>; rel="next",',
            f'<{HF_PAGE_2}>; rel="next"; rel="prev"',
            f'<{HF_PAGE_2}>; rel="next", <{HF_PAGE_2}>; rel="next"',
            f"<{HF_PAGE_2}>",
        )
        for header in headers:
            with (
                self.subTest(header=header),
                mock.patch.object(
                    estate,
                    "fetch_response",
                    return_value=(200, json.dumps([{"id": "first"}]), {"link": header}),
                ) as fetch,
            ):
                result = estate.collect_paginated_inventory(
                    HF_START, scope="PUBLIC_ONLY"
                )
            self.assertEqual(result.completion, "INCOMPLETE")
            self.assertIsNone(result.count)
            self.assertIsNone(estate.threshold_result(result, 1))
            self.assertEqual(fetch.call_count, 1)

    def test_link_parser_preserves_quoted_commas_and_uri_semicolons(self):
        uri = HF_PAGE_2 + ";opaque,part"
        links = estate._pagination_links(f'<{uri}>; rel="next"; title="a,b;c"')
        self.assertEqual(links, [(uri, ["next"])])

    def test_added_filter_and_duplicate_cursor_fail_closed(self):
        for extra in ("&search=hidden", "&cursor=another", "&author=OTHER"):
            with (
                self.subTest(extra=extra),
                mock.patch.object(
                    estate,
                    "fetch_response",
                    return_value=(
                        200,
                        json.dumps([{"id": "first"}]),
                        {"link": f'<{HF_PAGE_2}{extra}>; rel="next"'},
                    ),
                ) as fetch,
            ):
                result = estate.collect_paginated_inventory(
                    HF_START, scope="PUBLIC_ONLY"
                )
            self.assertEqual(result.completion, "INCOMPLETE")
            self.assertIsNone(result.count)
            self.assertEqual(fetch.call_count, 1)

    def test_unsafe_final_page_link_fails_closed(self):
        with mock.patch.object(
            estate,
            "fetch_response",
            return_value=(
                200,
                json.dumps([{"id": "first"}]),
                {"link": '<https://example.test/models>; rel="prev"'},
            ),
        ):
            result = estate.collect_paginated_inventory(HF_START, scope="PUBLIC_ONLY")
        self.assertEqual(result.failure, "UNSAFE_NEXT_LINK")
        self.assertIsNone(result.count)

    def test_malformed_pages_withhold_counts(self):
        bodies = ("{", "{}", "[null]", '[{"private": true}]')
        for body in bodies:
            with (
                self.subTest(body=body),
                mock.patch.object(
                    estate, "fetch_response", return_value=(200, body, {})
                ),
            ):
                result = estate.collect_paginated_inventory(
                    HF_START, scope="PUBLIC_ONLY"
                )
            self.assertNotEqual(result.completion, "COMPLETE")
            self.assertIsNone(result.count)

    def test_invalid_provider_ids_cannot_certify_inventory(self):
        invalid_ids = (
            (HF_START, (True, False, 1, -3, 1.5, [], {}, "", "   ")),
            (GH_START, (True, False, 0, -3, 1.5, [], {}, "123", "")),
        )
        for url, values in invalid_ids:
            for value in values:
                with (
                    self.subTest(url=url, value=value),
                    mock.patch.object(
                        estate,
                        "fetch_response",
                        return_value=(200, json.dumps([{"id": value}]), {}),
                    ),
                ):
                    result = estate.collect_paginated_inventory(
                        url, scope="PUBLIC_ONLY"
                    )
                self.assertEqual(result.failure, "INVALID_ITEM_ID")
                self.assertEqual(result.completion, "INCOMPLETE")
                self.assertIsNone(result.count)
                self.assertIsNone(estate.threshold_result(result, 1))

    def test_duplicate_ids_make_inventory_incomplete(self):
        responses = {
            HF_START: (
                200,
                json.dumps([{"id": "SZLHOLDINGS/repeated"}]),
                {"link": f'<{HF_PAGE_2}>; rel="next"'},
            ),
            HF_PAGE_2: (
                200,
                json.dumps([{"id": "SZLHOLDINGS/repeated"}]),
                {},
            ),
        }
        with mock.patch.object(
            estate,
            "fetch_response",
            side_effect=response_map(responses),
        ):
            result = estate.collect_paginated_inventory(
                HF_START,
                scope="PUBLIC_ONLY",
            )

        self.assertEqual(result.completion, "INCOMPLETE")
        self.assertEqual(result.failure, "DUPLICATE_IDS")
        self.assertIsNone(result.count)
        self.assertIsNone(estate.threshold_result(result, minimum=1))
        self.assertEqual(
            result.summary()["duplicate_ids"],
            ["SZLHOLDINGS/repeated"],
        )

    def test_later_page_error_preserves_only_observed_count(self):
        responses = {
            HF_START: (
                200,
                json.dumps([{"id": "SZLHOLDINGS/first"}]),
                {"link": f'<{HF_PAGE_2}>; rel="next"'},
            ),
            HF_PAGE_2: (503, "", {}),
        }
        with mock.patch.object(
            estate,
            "fetch_response",
            side_effect=response_map(responses),
        ):
            result = estate.collect_paginated_inventory(
                HF_START,
                scope="TOKEN_VISIBLE",
            )

        self.assertEqual(result.completion, "INCOMPLETE")
        self.assertEqual(result.failure, "HTTP_503")
        self.assertIsNone(result.count)
        self.assertEqual(
            result.summary()["observed_unique_count"],
            1,
        )

    def test_first_page_error_is_unknown(self):
        with mock.patch.object(
            estate,
            "fetch_response",
            return_value=(401, "", {}),
        ):
            result = estate.collect_paginated_inventory(
                HF_START,
                scope="TOKEN_VISIBLE",
            )

        self.assertEqual(result.completion, "UNKNOWN")
        self.assertEqual(result.failure, "HTTP_401")
        self.assertIsNone(result.count)

    def test_page_ceiling_is_incomplete_not_green(self):
        with mock.patch.object(
            estate,
            "fetch_response",
            return_value=(
                200,
                json.dumps([{"id": "SZLHOLDINGS/first"}]),
                {"link": f'<{HF_PAGE_2}>; rel="next"'},
            ),
        ):
            result = estate.collect_paginated_inventory(
                HF_START,
                scope="TOKEN_VISIBLE",
                max_pages=1,
            )

        self.assertEqual(result.completion, "INCOMPLETE")
        self.assertEqual(result.failure, "PAGE_CEILING")
        self.assertIsNone(result.count)
        self.assertIsNone(estate.threshold_result(result, minimum=1))

    def test_filter_drift_in_next_link_fails_closed(self):
        drifted = (
            "https://huggingface.co/api/models"
            "?author=ANOTHER_ORG&limit=100&cursor=page-2"
        )
        with mock.patch.object(
            estate,
            "fetch_response",
            return_value=(
                200,
                json.dumps([{"id": "SZLHOLDINGS/first"}]),
                {"link": f'<{drifted}>; rel="next"'},
            ),
        ):
            result = estate.collect_paginated_inventory(
                HF_START,
                scope="PUBLIC_ONLY",
            )

        self.assertEqual(result.completion, "INCOMPLETE")
        self.assertEqual(result.failure, "FILTER_DRIFT")
        self.assertIsNone(result.count)

    def test_cross_origin_next_link_fails_closed(self):
        with mock.patch.object(
            estate,
            "fetch_response",
            return_value=(
                200,
                json.dumps([{"id": "SZLHOLDINGS/first"}]),
                {"link": '<https://example.test/api/models>; rel="next"'},
            ),
        ):
            result = estate.collect_paginated_inventory(
                HF_START,
                scope="TOKEN_VISIBLE",
            )

        self.assertEqual(result.completion, "INCOMPLETE")
        self.assertEqual(result.failure, "UNSAFE_NEXT_LINK")

    def test_pagination_cycle_fails_closed(self):
        responses = {
            HF_START: (
                200,
                json.dumps([{"id": "SZLHOLDINGS/first"}]),
                {"link": f'<{HF_PAGE_2}>; rel="next"'},
            ),
            HF_PAGE_2: (
                200,
                json.dumps([{"id": "SZLHOLDINGS/second"}]),
                {"link": f'<{HF_START}>; rel="next"'},
            ),
        }
        with mock.patch.object(
            estate,
            "fetch_response",
            side_effect=response_map(responses),
        ):
            result = estate.collect_paginated_inventory(
                HF_START,
                scope="TOKEN_VISIBLE",
            )

        self.assertEqual(result.completion, "INCOMPLETE")
        self.assertEqual(result.failure, "PAGINATION_CYCLE")

    def test_item_ceiling_fails_closed(self):
        with (
            mock.patch.object(estate, "MAX_INVENTORY_ITEMS", 1),
            mock.patch.object(
                estate,
                "fetch_response",
                return_value=(
                    200,
                    json.dumps(
                        [
                            {"id": "SZLHOLDINGS/first"},
                            {"id": "SZLHOLDINGS/second"},
                        ]
                    ),
                    {},
                ),
            ),
        ):
            result = estate.collect_paginated_inventory(
                HF_START,
                scope="TOKEN_VISIBLE",
            )

        self.assertEqual(result.completion, "INCOMPLETE")
        self.assertEqual(result.failure, "ITEM_CEILING")
        self.assertIsNone(result.count)


class VisibilityTests(unittest.TestCase):
    def test_live_inventory_errors_leave_thresholds_explicitly_unknown(self):
        with (
            mock.patch.object(estate, "head_ok", return_value={"ok": False}),
            mock.patch.object(estate, "fetch", return_value=(503, "")),
            mock.patch.object(
                estate, "fetch_json", side_effect=RuntimeError("offline")
            ),
            mock.patch.object(
                estate,
                "collect_paginated_inventory",
                side_effect=RuntimeError("offline"),
            ),
        ):
            result = estate.live()
        for key in (
            "hf_ok",
            "gh_ok",
            "hf_models",
            "hf_spaces",
            "hf_datasets",
            "gh_repos",
        ):
            self.assertIn(key, result)
            self.assertIsNone(result[key])

    def test_duplicate_link_fields_preserve_all_relations(self):
        headers = Message()
        headers.add_header("Link", f'<{HF_PAGE_2}>; rel="next"')
        headers.add_header("Link", f'<{HF_START}>; rel="prev"')
        normalized = estate._response_headers(headers)
        self.assertEqual(
            estate._pagination_links(normalized["link"]),
            [(HF_PAGE_2, ["next"]), (HF_START, ["prev"])],
        )

    def test_fetch_response_bounds_bytes_and_sanitizes_network_errors(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"12345"
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(
            estate.urllib.request, "build_opener", return_value=opener
        ):
            result = estate.fetch_response(HF_START, max_bytes=4)
        self.assertEqual(result, (0, "RESPONSE_TOO_LARGE", {}))
        response.read.assert_called_once_with(5)
        opener.open.side_effect = RuntimeError("token-sensitive-detail")
        with mock.patch.object(
            estate.urllib.request, "build_opener", return_value=opener
        ):
            result = estate.fetch_response(HF_START)
        self.assertEqual(result, (0, "RuntimeError", {}))

    def test_no_tokens_is_explicitly_public_only(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                estate.inventory_scope("github"),
                "PUBLIC_ONLY",
            )
            self.assertEqual(
                estate.inventory_scope("huggingface"),
                "PUBLIC_ONLY",
            )
            self.assertIn("type=public", estate.github_repos_url())
            self.assertNotIn(
                "Authorization",
                estate.request_headers(
                    "https://api.github.com/orgs/szl-holdings/repos"
                ),
            )
            self.assertNotIn(
                "Authorization",
                estate.request_headers(HF_START),
            )

    def test_tokens_are_not_attached_to_deceptive_or_unrelated_hosts(self):
        with mock.patch.dict(
            os.environ,
            {"GH_TOKEN": "gh-test", "HF_TOKEN": "hf-test"},
            clear=True,
        ):
            self.assertNotIn(
                "Authorization",
                estate.request_headers("https://api.github.com.example.test/repos"),
            )
            self.assertNotIn(
                "Authorization",
                estate.request_headers("https://example.test/api/models"),
            )

    def test_tokens_require_https_default_port_without_userinfo(self):
        with mock.patch.dict(
            os.environ, {"GH_TOKEN": "gh-test", "HF_TOKEN": "hf-test"}, clear=True
        ):
            for host in ("api.github.com", "huggingface.co"):
                for url in (
                    f"http://{host}/api",
                    f"https://{host}:8443/api",
                    f"https://{host}:invalid/api",
                    f"https://user@{host}/api",
                    f"https://user:pass@{host}/api",
                ):
                    with self.subTest(url=url):
                        self.assertNotIn("Authorization", estate.request_headers(url))
                self.assertIn(
                    "Authorization", estate.request_headers(f"https://{host}:443/api")
                )

    def test_redirect_handler_refuses_to_forward_request_headers(self):
        handler = estate._RejectRedirects()
        self.assertIsNone(
            handler.redirect_request(
                None,
                None,
                302,
                "Found",
                {},
                "https://example.test/collect",
            )
        )

    def test_tokens_enable_token_visible_scope_without_output_leak(self):
        secret_gh = "github-secret-for-test"
        secret_hf = "hf-secret-for-test"
        with mock.patch.dict(
            os.environ,
            {"GH_TOKEN": secret_gh, "HF_TOKEN": secret_hf},
            clear=True,
        ):
            self.assertEqual(
                estate.inventory_scope("github"),
                "TOKEN_VISIBLE",
            )
            self.assertEqual(
                estate.inventory_scope("huggingface"),
                "TOKEN_VISIBLE",
            )
            self.assertIn("type=all", estate.github_repos_url())
            self.assertEqual(
                estate.request_headers(
                    "https://api.github.com/orgs/szl-holdings/repos"
                )["Authorization"],
                f"Bearer {secret_gh}",
            )
            self.assertEqual(
                estate.request_headers(HF_START)["Authorization"],
                f"Bearer {secret_hf}",
            )
            summary = estate.PaginatedInventory(
                scope="TOKEN_VISIBLE",
                items=[
                    {
                        "id": "SZLHOLDINGS/private",
                        "private": True,
                    }
                ],
                completion="COMPLETE",
                private_items_seen=1,
            ).summary()

        serialized = json.dumps(summary)
        self.assertNotIn(secret_gh, serialized)
        self.assertNotIn(secret_hf, serialized)
        self.assertEqual(summary["private_items_seen"], 1)


if __name__ == "__main__":
    unittest.main()
