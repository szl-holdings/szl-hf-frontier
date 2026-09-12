"""Offline regressions for the inventory-to-stdout disclosure boundary."""

import contextlib
import io
import json
import os
import unittest
from unittest import mock

import szl_estate_operational as estate


class InventoryPrivacyTests(unittest.TestCase):
    def run_report(self, models=(), spaces=(), datasets=(), repos=()):
        """Exercise the real collector, live(), report(), and CLI serializer."""
        rows_by_url = {
            estate.HF_MODELS: list(models),
            estate.HF_SPACES: list(spaces),
            estate.HF_DATASETS: list(datasets),
        }

        def response(url, **kwargs):
            if url.startswith("https://api.github.com/orgs/"):
                return 200, json.dumps(list(repos)), {}
            if url in rows_by_url:
                return 200, json.dumps(rows_by_url[url]), {}
            return 503, "", {}

        stdout = io.StringIO()
        with (
            mock.patch.dict(os.environ, {"HF_TOKEN": "fixture-only"}, clear=True),
            mock.patch.object(estate, "fetch_response", side_effect=response),
            mock.patch.object(estate, "have_cuda", return_value=False),
            mock.patch.object(estate.sys, "argv", ["estate", "--live"]),
            mock.patch("socket.socket.connect", side_effect=AssertionError("network")),
            contextlib.redirect_stdout(stdout),
        ):
            status = estate.main()
        self.assertEqual(status, 0)
        text = stdout.getvalue()
        return json.loads(text), text

    def test_private_model_names_never_reach_cli_stdout(self):
        private_id = "SZLHOLDINGS/private-model-fixture"
        result, text = self.run_report(
            models=[{"id": private_id, "private": True}]
        )
        self.assertNotIn(private_id, text)
        self.assertEqual(result["live"]["hf_sample"], [])
        self.assertEqual(result["live"]["hf_models"], 1)
        self.assertEqual(
            result["live"]["hf_models_inventory"]["private_items_seen"], 1
        )

    def test_missing_or_non_boolean_visibility_is_not_public(self):
        rows = [{"id": "SZLHOLDINGS/missing-visibility"}]
        rows.extend(
            {"id": f"SZLHOLDINGS/unknown-{i}", "private": value}
            for i, value in enumerate((None, 0, "false", "", [], {}))
        )
        result, text = self.run_report(models=rows)
        self.assertEqual(result["live"]["hf_sample"], [])
        self.assertEqual(result["live"]["hf_models"], len(rows))
        for row in rows:
            self.assertNotIn(row["id"], text)

    def test_public_filter_precedes_eight_item_sample_limit(self):
        rows = [
            {"id": f"SZLHOLDINGS/private-{i}", "private": True}
            for i in range(8)
        ]
        public_ids = [f"SZLHOLDINGS/public-{i}" for i in range(10)]
        rows.extend({"id": name, "private": False} for name in public_ids)
        result, text = self.run_report(models=rows)
        self.assertEqual(result["live"]["hf_sample"], public_ids[:8])
        self.assertEqual(result["live"]["hf_models"], 18)
        self.assertNotIn("SZLHOLDINGS/private-", text)

    def test_public_model_id_alias_is_supported(self):
        name = "SZLHOLDINGS/public-alias"
        result, _ = self.run_report(models=[{"modelId": name, "private": False}])
        self.assertEqual(result["live"]["hf_sample"], [name])

    def test_private_model_id_alias_is_redacted(self):
        name = "SZLHOLDINGS/private-alias"
        result, text = self.run_report(models=[{"modelId": name, "private": True}])
        self.assertEqual(result["live"]["hf_sample"], [])
        self.assertNotIn(name, text)

    def test_duplicate_private_model_ids_are_not_diagnostic_output(self):
        name = "SZLHOLDINGS/duplicate-private-model"
        rows = [{"id": name, "private": True}] * 2
        result, text = self.run_report(models=rows)
        summary = result["live"]["hf_models_inventory"]
        self.assertNotIn(name, text)
        self.assertEqual(summary["duplicate_ids"], [])
        self.assertEqual(summary["duplicate_count"], 1)
        self.assertEqual(summary["duplicate_ids_redacted"], True)
        self.assertEqual(summary["failure"], "DUPLICATE_IDS")
        self.assertEqual(summary["completion"], "INCOMPLETE")
        self.assertIsNone(result["live"]["hf_models"])
        self.assertIsNone(result["live"]["hf_ok"])

    def test_duplicate_private_dataset_ids_are_redacted(self):
        name = "SZLHOLDINGS/duplicate-private-dataset"
        result, text = self.run_report(datasets=[{"id": name, "private": True}] * 2)
        self.assertNotIn(name, text)
        summary = result["live"]["hf_datasets_inventory"]
        self.assertEqual(summary["duplicate_count"], 1)
        self.assertIsNone(summary["count"])

    def test_duplicate_private_space_ids_are_redacted(self):
        name = "SZLHOLDINGS/duplicate-private-space"
        result, text = self.run_report(spaces=[{"id": name, "private": True}] * 2)
        self.assertNotIn(name, text)
        self.assertEqual(result["live"]["hf_spaces_inventory"]["duplicate_count"], 1)

    def test_authenticated_and_unknown_scopes_hide_duplicate_identifiers(self):
        for scope in ("TOKEN_VISIBLE", "UNKNOWN", "unexpected"):
            with self.subTest(scope=scope):
                inventory = estate.PaginatedInventory(
                    scope=scope,
                    items=[{"id": 987654321, "private": True}],
                    duplicate_ids=["987654321"],
                    completion="INCOMPLETE",
                    failure="DUPLICATE_IDS",
                    private_items_seen=1,
                )
                summary = inventory.summary()
                self.assertNotIn("987654321", json.dumps(summary))
                self.assertEqual(summary["duplicate_count"], 1)
                self.assertEqual(inventory.duplicate_ids, ["987654321"])
                self.assertIsNone(estate.threshold_result(inventory, 1))

    def test_anomalous_private_rows_in_public_scope_hide_duplicate_ids(self):
        inventory = estate.PaginatedInventory(
            scope="PUBLIC_ONLY",
            items=[{"id": "private-anomaly", "private": True}],
            duplicate_ids=["private-anomaly"],
            private_items_seen=1,
        )
        self.assertNotIn("private-anomaly", json.dumps(inventory.summary()))

    def test_anonymous_public_duplicate_diagnostics_are_preserved(self):
        inventory = estate.PaginatedInventory(
            scope="PUBLIC_ONLY", duplicate_ids=["public-fixture"]
        )
        summary = inventory.summary()
        self.assertEqual(summary["duplicate_ids"], ["public-fixture"])
        self.assertFalse(summary["duplicate_ids_redacted"])

    def test_known_space_is_not_reported_public_when_private(self):
        result, _ = self.run_report(
            spaces=[{"id": estate.PUBLIC_SPACES[0], "private": True}]
        )
        self.assertEqual(result["live"]["public_spaces_seen"], [])
        self.assertEqual(result["live"]["hf_spaces"], 1)

    def test_space_visibility_requires_explicit_false(self):
        for value in (None, 0, "false", True):
            with self.subTest(value=value):
                result, _ = self.run_report(
                    spaces=[{"id": estate.PUBLIC_SPACES[0], "private": value}]
                )
                self.assertEqual(result["live"]["public_spaces_seen"], [])

    def test_public_space_and_non_product_public_observation_are_preserved(self):
        rows = [
            {"id": estate.PUBLIC_SPACES[0], "private": False},
            {"id": estate.NOT_PUBLIC_PRODUCT[0], "private": False},
        ]
        result, _ = self.run_report(spaces=rows)
        self.assertEqual(result["live"]["public_spaces_seen"], [rows[0]["id"]])
        self.assertEqual(result["live"]["not_public_seen"], [rows[1]["id"]])

    def test_private_non_product_space_is_not_disclosed(self):
        name = estate.NOT_PUBLIC_PRODUCT[0]
        result, _ = self.run_report(spaces=[{"id": name, "private": True}])
        self.assertEqual(result["live"]["not_public_seen"], [])

    def test_incomplete_inventory_does_not_emit_model_samples(self):
        name = "SZLHOLDINGS/repeated-public"
        result, _ = self.run_report(models=[{"id": name, "private": False}] * 2)
        self.assertEqual(result["live"]["hf_sample"], [])
        self.assertIsNone(result["live"]["hf_ok"])

    def test_incomplete_inventory_does_not_assert_space_visibility(self):
        rows = [{"id": estate.PUBLIC_SPACES[0], "private": False}] * 2
        result, _ = self.run_report(spaces=rows)
        self.assertEqual(result["live"]["public_spaces_seen"], [])

    def test_disclosure_filter_does_not_change_operational_authority(self):
        result, _ = self.run_report(models=[{"id": "public", "private": False}])
        self.assertFalse(result["ready"])
        self.assertFalse(result["hub_put"])
        self.assertFalse(result["flagship"])
        self.assertIsNone(result["winner"])
        self.assertEqual(result["live"]["hf_models_inventory"]["scope"], "TOKEN_VISIBLE")
        self.assertEqual(result["selftest"]["gmb"]["n_passed"], 20)


if __name__ == "__main__":
    unittest.main()
