"""Synthetic/offline failure, identity, CAS, receipt, path and CI-effect fixtures."""
import ast
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


f = module("frontier1", ROOT / "tools/frontier1.py")
wave = module("offline_wave", ROOT / "payload.py")
legacy = module("legacy_hub", ROOT / "tools/cto_hub_honesty_payload.py")


def snapshot():
    return {"schema": f.SCHEMA, "observed_at": "2026-09-30T13:36:24Z",
            "source_commit": "1" * 40, "expected_heads": {}}


def add_repo(doc, kind, name, **extra):
    item = {"repo_type": kind, "repo_id": name, "revision": "a" * 40, "private": False, **extra}
    doc["expected_heads"][f.identity(kind, name)] = item["revision"]
    return item


class PlanTests(unittest.TestCase):
    def test_default_is_closed_complete_nonexecuting_and_no_files(self):
        with tempfile.TemporaryDirectory() as td, patch.object(socket, "create_connection", side_effect=AssertionError), \
                patch.object(subprocess, "run", side_effect=AssertionError), \
                patch.dict(os.environ, {"HF_TOKEN": "fixture-only", "GITHUB_TOKEN": "fixture-only"}), \
                redirect_stdout(io.StringIO()) as out:
            before = list(Path(td).iterdir())
            self.assertEqual(f.main([]), 0)
            result = json.loads(out.getvalue())
            self.assertEqual(before, list(Path(td).iterdir()))
            self.assertEqual(set(result["statuses"]), set(f.WOS))
            self.assertEqual(result["publish_gate"], "CLOSED")
            self.assertEqual(result["statuses"]["WO-3"]["hardware"], "NOT_PROBED")

    def test_handlers_fail_independently_and_gate_cannot_be_opened(self):
        def crash(_):
            raise RuntimeError("PRIVATE_EXCEPTION_MUST_NOT_APPEAR")
        for failing in f.WOS:
            with self.subTest(failing=failing):
                calls = {wo: lambda _: f.outcome("DONE", "synthetic") for wo in f.WOS}
                calls[failing] = crash
                result = f.plan(snapshot(), handlers=calls)
                self.assertEqual(set(result["statuses"]), set(f.WOS))
                self.assertNotIn("PRIVATE_EXCEPTION", json.dumps(result))
                self.assertEqual(result["statuses"]["WO-6"], f.wo6({}))
                if failing != "WO-6":
                    self.assertEqual(result["statuses"][failing]["status"], "FAIL-CLOSED")

    def test_system_exit_and_invalid_handler_are_terminal(self):
        def stop(_):
            raise SystemExit(1)
        calls = {wo: stop for wo in f.WOS}
        calls["WO-1"] = lambda _: {"status": "STAGED"}
        result = f.plan(snapshot(), handlers=calls)
        self.assertTrue(all(r["status"] in f.TERMINAL for r in result["statuses"].values()))
        self.assertEqual(result["statuses"]["WO-7"]["status"], "FAIL-CLOSED")

    def test_cancellation_propagates_without_later_work_or_completion(self):
        for signal in (KeyboardInterrupt, GeneratorExit, BaseException):
            with self.subTest(signal=signal.__name__):
                visited = []

                def stop(_, signal=signal):
                    visited.append("WO-1")
                    raise signal()

                def later(_):
                    visited.append("LATER")
                    return f.outcome("DONE", "synthetic")

                calls = {wo: later for wo in f.WOS}
                calls["WO-1"] = stop
                with self.assertRaises(signal):
                    f.plan(snapshot(), handlers=calls)
                self.assertEqual(visited, ["WO-1"])

    def test_unknown_private_or_confirmation_input_is_rejected(self):
        for extra in ("private_metadata", "owner_confirmed", "token", "publish_gate"):
            doc = snapshot()
            doc[extra] = "DO_NOT_REFLECT"
            result = f.plan(doc)
            self.assertEqual(result["statuses"]["WO-1"]["status"], "FAIL-CLOSED")
            self.assertEqual(result["statuses"]["WO-6"]["status"], "OWNER-PENDING")
            self.assertNotIn("DO_NOT_REFLECT", json.dumps(result))

    def test_bad_and_missing_input_still_print_all_statuses(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "input.json"
            for contents in (None, "{", "null", "[]", '{"private":true}'):
                if contents is not None:
                    path.write_text(contents)
                with redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(f.main(["--observations", str(path)]), 1)
                result = json.loads(out.getvalue())
                self.assertEqual(set(result["statuses"]), set(f.WOS))

    def test_model_inventory_is_not_first_file_or_size_qualification(self):
        doc = snapshot()
        doc["models"] = [add_repo(doc, "model", "SZLHOLDINGS/khipu-r3", files=[
            {"path": "adapter_model.safetensors", "bytes": 25_000_000},
            {"path": "model.safetensors", "bytes": 3_000_000_000}])]
        result = f.wo1(doc)
        item = next(i for i in result["items"] if i["identity"].endswith("/khipu-r3"))
        self.assertEqual(item["status"], "OWNER-PENDING")
        self.assertEqual(item["qualification"], "NOT_ESTABLISHED")
        self.assertEqual(item["checkpoint_candidates"][0]["path"], "model.safetensors")

    def test_model_subdirectory_identity_is_preserved(self):
        doc = snapshot()
        doc["models"] = [add_repo(doc, "model", "SZLHOLDINGS/" + f.MODELS[0], files=[
            {"path": "salvaged-merge/model.safetensors", "bytes": 3_000_000_000}])]
        item = f.wo1(doc)["items"][0]
        self.assertEqual(item["checkpoint_candidates"][0]["path"], "salvaged-merge/model.safetensors")

    def test_adapter_only_fails_but_all_eight_items_remain(self):
        doc = snapshot()
        doc["models"] = [add_repo(doc, "model", "SZLHOLDINGS/" + f.MODELS[0], files=[
            {"path": "adapter_model.safetensors", "bytes": 400_000_000}])]
        result = f.wo1(doc)
        self.assertEqual(len(result["items"]), 8)
        self.assertEqual(result["items"][0]["status"], "FAIL-CLOSED")
        self.assertEqual(result["items"][1]["status"], "OWNER-PENDING")

    def test_same_id_different_types_are_not_overwritten(self):
        doc = snapshot()
        doc["profiles"] = [add_repo(doc, kind, name, files=[{"path": "README.md", "bytes": 12}],
                                    purpose="INFORMATIONAL_METADATA") for kind, name in f.PROFILES]
        results = f.wo2(doc)["items"]
        self.assertEqual(len({r["identity"] for r in results}), 3)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r["status"] == "OWNER-PENDING" for r in results))

    def test_unknown_large_private_duplicate_and_stale_items_fail(self):
        doc = snapshot()
        item = add_repo(doc, "model", "SZLHOLDINGS/SZLHOLDINGS", purpose="HISTORICAL_PROFILE",
                        files=[{"path": "README.md", "bytes": 1}])
        mutations = [lambda i: i["files"][0].update(bytes=None),
                     lambda i: i["files"][0].update(bytes=50_000_001),
                     lambda i: i.update(private=True), lambda i: i.update(revision="b" * 40)]
        for mutate in mutations:
            changed = copy.deepcopy(item)
            mutate(changed)
            doc["profiles"] = [changed]
            self.assertEqual(f.wo2(doc)["items"][0]["status"], "FAIL-CLOSED")
        doc["profiles"] = [item, item]
        self.assertEqual(f.plan(doc)["statuses"]["WO-2"]["status"], "FAIL-CLOSED")

    def test_revision_binding_rejects_short_missing_and_stale(self):
        for expected, observed in ((None, "a" * 40), ("a" * 7, "a" * 40), ("a" * 40, "b" * 40)):
            with self.assertRaises(f.Refused):
                f.bind_revision(expected, observed)

    def test_pointer_markdown_multiple_urls_and_trailing_prose(self):
        description = "Canonical: [one](https://github.com/szl-holdings/platform) + https://github.com/szl-holdings/szl-ouroboros. Preserved."
        targets = f.canonical_targets(description)
        self.assertEqual(targets, ["szl-holdings/platform", "szl-holdings/szl-ouroboros"])
        doc = snapshot()
        doc["pointers"] = {"complete": True, "repository_count": 3, "archived_count": 1,
                           "source_count": 1, "edge_count": 2,
                           "sources": [{"repo_id": "szl-holdings/old", "archived": True,
                                        "description": description, "targets": {
                                            t: {"exists": True, "archived": False, "disabled": False} for t in targets}}]}
        self.assertEqual(f.wo4(doc)["status"], "DONE")
        doc["pointers"]["sources"][0]["targets"][targets[0]]["archived"] = True
        self.assertEqual(f.wo4(doc)["status"], "FAIL-CLOSED")
        self.assertEqual(f.wo4(doc)["issues_created"], 0)

    def test_incomplete_pointer_census_is_not_done(self):
        doc = snapshot()
        doc["pointers"] = {"complete": True, "repository_count": 130, "archived_count": 28,
                           "source_count": 22, "edge_count": 23, "sources": []}
        self.assertEqual(f.plan(doc)["statuses"]["WO-4"]["status"], "FAIL-CLOSED")

    def test_banner_requires_frontmatter_and_specific_target(self):
        for text, expected in (("---\nlicense: apache-2.0\n---\n> DEPRECATED; canonical: https://github.com/szl-holdings/szl-energy-attest\n", "DONE"),
                               ("> DEPRECATED\n---\nlicense: apache-2.0\n---\n", "FAIL-CLOSED"),
                               ("---\nlicense: apache-2.0\n---\n> DEPRECATED unrelated library\n", "FAIL-CLOSED")):
            doc = snapshot()
            doc["deprecation"] = add_repo(doc, "model", "SZLHOLDINGS/governed-inference-meter",
                                          readme=text, readme_sha256=f.digest(text.encode()))
            self.assertEqual(f.plan(doc)["statuses"]["WO-7"]["status"], expected)
            self.assertEqual(doc["deprecation"]["readme"], text)

    def test_unexpected_or_malformed_item_preserves_declared_outcomes(self):
        for raw in ([None], [{"repo_type": "model", "repo_id": "PRIVATE/value"}], "invalid"):
            doc = snapshot()
            doc["models"] = raw
            result = f.wo1(doc)
            self.assertEqual(len(result["items"]), 8)
            self.assertEqual(result["status"], "FAIL-CLOSED")
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_public_fixture_has_exact_declared_outcomes_and_no_actions(self):
        doc = json.loads((ROOT / "payloads/evidence/frontier1-public-20260930.json").read_text())
        result = f.plan(doc)
        self.assertEqual({wo: r["status"] for wo, r in result["statuses"].items()},
                         {"WO-1": "OWNER-PENDING", "WO-2": "OWNER-PENDING", "WO-3": "UNAVAILABLE",
                          "WO-4": "DONE", "WO-5": "OWNER-PENDING", "WO-6": "OWNER-PENDING", "WO-7": "DONE"})
        self.assertEqual(len(result["statuses"]["WO-4"]["items"]), 23)
        self.assertEqual(result["remote_mutations"], "NONE")
        doc["pointers"]["sources"].pop()
        self.assertEqual(f.plan(doc)["statuses"]["WO-4"]["status"], "FAIL-CLOSED")

    def test_pointer_unknown_boolean_and_misleading_banner_fail(self):
        doc = json.loads((ROOT / "payloads/evidence/frontier1-public-20260930.json").read_text())
        row = doc["pointers"]["sources"][0]
        row["targets"][next(iter(row["targets"]))]["exists"] = 1
        self.assertEqual(f.plan(doc)["statuses"]["WO-4"]["status"], "FAIL-CLOSED")
        card = doc["deprecation"]
        card["readme"] = "---\nlicense: apache-2.0\n---\n> DEPRECATED canonical: https://github.com/szl-holdings/szl-energy-attest-imposter\n"
        card["readme_sha256"] = f.digest(card["readme"].encode())
        self.assertEqual(f.plan(doc)["statuses"]["WO-7"]["status"], "FAIL-CLOSED")


class ReceiptTests(unittest.TestCase):
    def test_full_digest_atomic_receipts_idempotence_and_local_cas(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "unrelated.json").write_text("retained")
            report = f.plan()
            master = f.record_run(root, "fixture-1", report, "0" * 64)
            run = root / "fixture-1"
            before = {p.name: p.read_bytes() for p in run.iterdir()}
            sha = f.digest(before["master.json"])
            self.assertEqual(f.verify_run(run), master)
            self.assertTrue(all(len(v) == 64 for v in master["artifact_sha256"].values()))
            self.assertNotIn("master.json", master["artifact_sha256"])
            self.assertEqual(f.record_run(root, "fixture-1", report, "0" * 64, expected_master_sha256=sha), master)
            self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir()})
            for kwargs in ({"input_sha256": "1" * 64},
                           {"input_sha256": "0" * 64, "expected_master_sha256": "f" * 64}):
                with self.assertRaises(f.Refused):
                    f.record_run(root, "fixture-1", report, **kwargs)
            self.assertEqual((root / "unrelated.json").read_text(), "retained")

    def test_failure_before_finalization_retains_pending_but_no_final(self):
        with tempfile.TemporaryDirectory() as td:
            original = f.write_new
            count = 0
            def failing(path, data):
                nonlocal count
                count += 1
                if count == 4:
                    raise OSError("synthetic write failure")
                return original(path, data)
            with patch.object(f, "write_new", side_effect=failing), self.assertRaises(OSError):
                f.record_run(Path(td), "fail", f.plan(), "0" * 64)
            self.assertFalse((Path(td) / "fail").exists())
            self.assertEqual(len(list(Path(td).glob("*.pending"))), 1)
            self.assertFalse((Path(td) / ".fail.lock").exists())

    def test_rename_failure_is_not_published(self):
        with tempfile.TemporaryDirectory() as td, patch.object(f.os, "rename", side_effect=OSError), self.assertRaises(OSError):
            f.record_run(Path(td), "fail", f.plan(), "0" * 64)
        # No successful return/master claim on failed atomic publication.

    def test_tampering_extra_files_and_untrusted_gate_fail_readback(self):
        for mode in ("changed", "extra", "publish_gate", "autonomy_eligible", "owner_evidence", "input_sha256"):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                f.record_run(root, "run", f.plan(), "0" * 64)
                run = root / "run"
                if mode == "changed":
                    (run / "wo1.json").write_text("{}")
                elif mode == "extra":
                    (run / "old-master.json").write_text("{}")
                else:
                    master = json.loads((run / "master.json").read_text())
                    master[mode] = {"publish_gate": "OPEN", "autonomy_eligible": True,
                                    "owner_evidence": "CONFIRMED", "input_sha256": "short"}[mode]
                    data = f.encode(master)
                    (run / "master.json").write_bytes(data)
                    (run / "master.sha256").write_text(f.digest(data) + "  master.json\n")
                with self.assertRaises(f.Refused):
                    f.verify_run(run)

    def test_traversal_reserved_names_and_lock_contention(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("../escape", "a/b", "a\\b", "a:b", "CON", "con", ".", "..", "nul", "com1", "end."):
                with self.subTest(name=name), self.assertRaises(f.Refused):
                    f.record_run(root, name, f.plan(), "0" * 64)
            (root / ".busy.lock").mkdir()
            with self.assertRaises(f.Refused):
                f.record_run(root, "busy", f.plan(), "0" * 64)
            self.assertFalse((root / "busy").exists())

    def test_symlink_output_and_input_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "real").mkdir()
            try:
                (root / "link").symlink_to(root / "real", target_is_directory=True)
            except OSError:
                self.skipTest("host does not permit symlink fixture; reparse fixture covers guard")
            with self.assertRaises(f.Refused):
                f.record_run(root / "link", "run", f.plan(), "0" * 64)
            with self.assertRaises(f.Refused):
                f.read_small(root / "link" / "absent.json")

    def test_windows_reparse_guard_without_host_privileges(self):
        class Info:
            st_mode = 0
            st_file_attributes = 0x400
        with patch.object(Path, "lstat", return_value=Info()), self.assertRaises(f.Refused):
            f.no_links(Path("fixture"))

    def test_file_paths_cannot_escape_or_duplicate(self):
        for name in ("../x", "/x", "C:/x", "a\\x", "a//x", "a/./x", "a\nx"):
            with self.assertRaises(f.Refused):
                f.inventory([{"path": name, "bytes": 0}])
        with self.assertRaises(f.Refused):
            f.inventory([{"path": "x", "bytes": 0}] * 2)

    def test_marker_does_not_clear_gate_or_enter_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "wo6_owner_action.md").write_text("OWNER CONFIRMED <SYNTHETIC NON-AUTHORITATIVE FIXTURE>\n")
            master = f.record_run(root, "run", f.plan(), "0" * 64)
            self.assertEqual(master["statuses"]["WO-6"]["status"], "OWNER-PENDING")
            self.assertEqual(master["publish_gate"], "CLOSED")
            self.assertNotIn("wo6_owner_action.md", master["artifact_sha256"])

    def test_record_cli_reports_all_statuses_on_filesystem_failure(self):
        with patch.object(f, "record_run", side_effect=OSError("PRIVATE_PATH")), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(f.main(["--record", "--output-root", "fixture", "--run-id", "run"]), 2)
        result = json.loads(out.getvalue())
        self.assertEqual(set(result["statuses"]), set(f.WOS))
        self.assertNotIn("PRIVATE_PATH", out.getvalue())


class CIEffectsTests(unittest.TestCase):
    def test_retained_public_run_integrity_and_input_binding(self):
        fixture = ROOT / "payloads/evidence/frontier1-public-20260930.json"
        run = ROOT / "payloads/evidence/frontier1-runs/public-observation-20260930"
        master = f.verify_run(run)
        # Historic evidence stays byte-identical and bound to its original
        # executor, even when a successor changes the current source file.
        self.assertEqual(f.digest((run / "master.json").read_bytes()),
                         "de53c9f4f5ae07f133f6fe51d9256c14103e6b9a513b13382156c85bcb7005a5")
        self.assertEqual(master["executor_sha256"],
                         "d4b9826b2d4f6c20517896168661ebd9866c973605621acd4668f93a0941520f")
        self.assertEqual(master["input_sha256"], f.digest(fixture.read_bytes()))
        self.assertEqual(master["statuses"], f.plan(json.loads(fixture.read_bytes()))["statuses"])

    def test_wave_never_reads_credentials_launches_helper_or_probes_gpu(self):
        with patch.object(os.environ, "get", side_effect=AssertionError("environment read")), \
                patch.object(subprocess, "run", side_effect=AssertionError("helper launch")):
            self.assertEqual(wave.wave_hub(), "DISABLED_OFFLINE_NO_OWNER_AUTHORIZATION")
            self.assertEqual(wave.wave_metal(), "NOT_PROBED_OFFLINE")

    def test_legacy_ci_guard_precedes_credential_access(self):
        for key in ("CI", "GITHUB_ACTIONS"):
            with patch.dict(os.environ, {key: "true"}, clear=True), \
                    patch.object(legacy, "_token", side_effect=AssertionError("token read")), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(legacy.main(), 2)

    def test_planner_has_no_provider_compute_or_subprocess_imports(self):
        tree = ast.parse((ROOT / "tools/frontier1.py").read_text())
        imports = {a.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names}
        imports |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertFalse(imports & {"requests", "urllib", "socket", "subprocess", "torch", "huggingface_hub", "datasets"})

    def test_workflow_keeps_existing_checks_and_explicit_offline_execution(self):
        workflow = (ROOT / ".github/workflows/payload.yml").read_text()
        for command in ("payload.py --offline", "tests.test_frontier1", "unittest discover -v",
                        "tools/verify_estate_evidence.py", "tools/reconcile_estate.py",
                        "tools/verify_model_reconciliation.py", "szl_estate_operational.py --selftest",
                        "compose.waves", "SZL_HF_FRONTIER_INVESTOR.py --selftest", "sha256sum --check"):
            self.assertIn(command, workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("secrets.", workflow)


if __name__ == "__main__":
    unittest.main()
