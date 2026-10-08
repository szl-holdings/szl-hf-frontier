"""Offline header-boundary tests for the legacy wire helper.

Load only the HTTP helper definitions: importing the full legacy script would
also initialize its inlined case catalog, which these tests do not need.
"""

import json
import os
from pathlib import Path
import ssl
import unittest
from unittest.mock import patch
import urllib.parse
import urllib.request
from typing import Any


SOURCE = Path(__file__).resolve().parents[1] / "SZL_HF_FRONTIER_WIRE.py"
helper_lines = []
with SOURCE.open(encoding="utf-8") as source:
    for line in source:
        if line.startswith("class _NoRedirect("):
            helper_lines.append(line)
            break
    for line in source:
        if line.startswith("def normalize("):
            break
        helper_lines.append(line)
helper_source = "".join(helper_lines)
scope = {
    "Any": Any,
    "ctx": ssl.create_default_context,
    "json": json,
    "os": os,
    "urllib": urllib,
}
exec(compile(helper_source, str(SOURCE), "exec"), scope)
fetch_json = scope["fetch_json"]
NoRedirect = scope["_NoRedirect"]

GITHUB_URL = "https://api.github.com/orgs/szl-holdings/repos?per_page=100&type=public"


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b"{}"


class WireAuthTests(unittest.TestCase):
    def test_hf_only_never_authenticates_to_github(self):
        with patch.dict(os.environ, {"HF_TOKEN": "hf_synthetic"}, clear=True):
            with patch.object(urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                with patch.object(urllib.request, "build_opener") as build_opener:
                    self.assertEqual(fetch_json(GITHUB_URL), {})
        build_opener.assert_not_called()
        request = urlopen.call_args.args[0]
        self.assertFalse(request.has_header("Authorization"))

    def test_github_token_wins_and_uses_no_redirect_opener(self):
        env = {"GH_TOKEN": "gh_synthetic", "GITHUB_TOKEN": "gh_second", "HF_TOKEN": "hf_synthetic"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(urllib.request, "urlopen") as urlopen:
                with patch.object(urllib.request, "build_opener") as build_opener:
                    build_opener.return_value.open.return_value = FakeResponse()
                    self.assertEqual(fetch_json(GITHUB_URL), {})
        urlopen.assert_not_called()
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer gh_synthetic")
        self.assertTrue(any(isinstance(handler, NoRedirect) for handler in build_opener.call_args.args))

    def test_github_token_fallback(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "github_synthetic"}, clear=True):
            with patch.object(urllib.request, "build_opener") as build_opener:
                build_opener.return_value.open.return_value = FakeResponse()
                self.assertEqual(fetch_json(GITHUB_URL), {})
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer github_synthetic")

    def test_wrong_origins_never_receive_authorization(self):
        urls = [
            "http://api.github.com/orgs/szl-holdings/repos",
            "https://github.com/orgs/szl-holdings/repos",
            "https://raw.githubusercontent.com/szl-holdings/szl-forge/main/receipt.json",
            "https://api.github.com:444/orgs/szl-holdings/repos",
            "https://api.github.com.evil.test/orgs/szl-holdings/repos",
            "https://user:pass@api.github.com/orgs/szl-holdings/repos",
        ]
        with patch.dict(os.environ, {"GH_TOKEN": "gh_synthetic"}, clear=True):
            for url in urls:
                with self.subTest(url=url):
                    with patch.object(urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                        with patch.object(urllib.request, "build_opener") as build_opener:
                            self.assertEqual(fetch_json(url), {})
                    build_opener.assert_not_called()
                    self.assertFalse(urlopen.call_args.args[0].has_header("Authorization"))

    def test_default_https_port_is_allowed(self):
        with patch.dict(os.environ, {"GH_TOKEN": "gh_synthetic"}, clear=True):
            with patch.object(urllib.request, "build_opener") as build_opener:
                build_opener.return_value.open.return_value = FakeResponse()
                self.assertEqual(fetch_json("https://api.github.com:443/repos"), {})
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer gh_synthetic")

    def test_authenticated_redirect_is_rejected(self):
        request = urllib.request.Request(GITHUB_URL, headers={"Authorization": "Bearer synthetic"})
        redirect = NoRedirect().redirect_request(
            request, None, 302, "Found", {"Location": "https://elsewhere.example/"},
            "https://elsewhere.example/",
        )
        self.assertIsNone(redirect)


if __name__ == "__main__":
    unittest.main()
