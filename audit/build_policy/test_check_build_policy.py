"""Tests for check_build_policy: fail-closed, offline, no sleeps.

Tag-only refs fail, digest refs pass, secret-bearing contexts
fail, clean contexts pass. Lazy imports, ambient credentials
explicitly dropped.
"""

import pytest


def _mod():
    import check_build_policy as mod

    return mod


def pinned_ref():
    return "ghcr.io/szl-holdings/a7@sha256:" + "ab" * 32


def f5_receipt():
    return {
        "kind": "f5_rotation_attestation",
        "revoked": True,
        "receipt_sha256": "cd" * 32,
    }


def test_digest_ref_passes():
    mod = _mod()
    assert mod.check_image_ref(pinned_ref()) is True


def test_tag_only_ref_fails():
    mod = _mod()
    with pytest.raises(mod.ValidationError):
        mod.check_image_ref("ghcr.io/szl-holdings/a7:latest")


def test_uppercase_hex_digest_fails():
    mod = _mod()
    ref = "ghcr.io/szl-holdings/a7@sha256:" + "AB" * 32
    with pytest.raises(mod.ValidationError):
        mod.check_image_ref(ref)


def test_short_digest_fails():
    mod = _mod()
    ref = "ghcr.io/szl-holdings/a7@sha256:" + "ab" * 31
    with pytest.raises(mod.ValidationError):
        mod.check_image_ref(ref)


def test_empty_ref_fails():
    mod = _mod()
    with pytest.raises(mod.ValidationError):
        mod.check_image_ref("")


def test_non_string_ref_fails():
    mod = _mod()
    with pytest.raises(mod.ValidationError):
        mod.check_image_ref(None)


def test_hf_token_value_detected():
    mod = _mod()
    text = "export TOKEN=hf_" + "x" * 30
    hits = mod.scan_text_for_secrets(text)
    assert hits[0][0] == "hf_token_value"
    assert len(hits) == 1


def test_hf_token_mention_detected():
    mod = _mod()
    hits = mod.scan_text_for_secrets("the HF_TOKEN is baked")
    assert hits


def test_ghp_token_detected():
    mod = _mod()
    text = "token=ghp_" + "1" * 36
    assert mod.scan_text_for_secrets(text)


def test_clean_text_no_hits():
    mod = _mod()
    assert mod.scan_text_for_secrets("safe content, no secrets") == []


def test_clean_build_context_passes(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    mod = _mod()
    files = {"Dockerfile": "FROM python:3.12-slim", "build.sh": "make"}
    assert mod.check_build_context(files) is True


def test_dummy_secret_build_fails():
    mod = _mod()
    files = {
        "Dockerfile": "FROM python:3.12-slim",
        "env.sh": "export HF_TOKEN=hf_" + "y" * 30,
    }
    with pytest.raises(mod.ValidationError):
        mod.check_build_context(files)


def test_ghp_secret_build_fails():
    mod = _mod()
    files = {"ci.env": "GITHUB_TOKEN=ghp_" + "z" * 40}
    with pytest.raises(mod.ValidationError):
        mod.check_build_context(files)


def test_empty_context_fails():
    mod = _mod()
    with pytest.raises(mod.ValidationError):
        mod.check_build_context({})


def test_manifest_pins_pass():
    mod = _mod()
    manifest = {"moe-a": pinned_ref(), "moe-b": pinned_ref()}
    assert mod.check_manifest_pins(manifest) is True


def test_manifest_tag_fails_with_service_named():
    mod = _mod()
    manifest = {"moe-a": pinned_ref(), "moe-b": "image:v1"}
    with pytest.raises(mod.ValidationError) as excinfo:
        mod.check_manifest_pins(manifest)
    assert "moe-b" in str(excinfo.value)


def test_valid_f5_receipt_passes():
    mod = _mod()
    assert mod.require_f5_rotation_receipt(f5_receipt()) is True


def test_f5_receipt_not_revoked_fails():
    mod = _mod()
    receipt = f5_receipt()
    receipt["revoked"] = False
    with pytest.raises(mod.ValidationError):
        mod.require_f5_rotation_receipt(receipt)


def test_f5_receipt_wrong_kind_fails():
    mod = _mod()
    receipt = f5_receipt()
    receipt["kind"] = "something_else"
    with pytest.raises(mod.ValidationError):
        mod.require_f5_rotation_receipt(receipt)


def test_f5_receipt_missing_sha_fails():
    mod = _mod()
    receipt = f5_receipt()
    del receipt["receipt_sha256"]
    with pytest.raises(mod.ValidationError):
        mod.require_f5_rotation_receipt(receipt)
