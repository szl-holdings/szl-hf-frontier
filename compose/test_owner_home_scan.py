from pathlib import Path
import json
import runpy

ROOT = Path(__file__).resolve().parents[1]


def test_owner_home_scan_closes_live_rows() -> None:
    ns = runpy.run_path(str(ROOT / "compose" / "owner_home_scan.py"))
    assert ns["main"]() == 0
    data = json.loads((ROOT / "data" / "owner_home_leaks.json").read_text(encoding="utf-8"))
    assert data["winner"] is None
    live = [row for row in data["findings"] if row["class"] == "LIVE"]
    assert live
    assert all(row["state"] == "CLOSED" for row in live)
