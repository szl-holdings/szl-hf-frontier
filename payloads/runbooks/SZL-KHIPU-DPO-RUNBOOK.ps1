# SZL khipu-abstain DPO lane - one paste, administrator PowerShell 5.1, no prior shell state.
# Machine: the RTX 5050 laptop (C:\Users\steph). On a box without CUDA the preflight stops before any training.
# Changes: creates %USERPROFILE%\szl\{logs, dpo-khipu-r4-challenger-<stamp>, cards-reconcile-<stamp>} only.
# Does not change: Hub repos, GitHub, the pinned .venv-ra-v2 / .venv-ra-v3 stacks, any token, any card
# (unless you deliberately set $ApplyCards = $true AFTER revoking the two exposed tokens and saving a fresh one locally).

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ApplyCards = $false   # owner gate for WO1 Hub PRs. Leave $false until WO6 (token revocation) is done.

$Root = Join-Path $env:USERPROFILE "szl"
New-Item -ItemType Directory -Force -Path $Root | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null
Set-Location -LiteralPath $Root
$Stamp = Get-Date -Format "yyyyMMdd-HHmm"
Start-Transcript -Path (Join-Path $Root ("logs\khipu-dpo-" + $Stamp + ".log")) | Out-Null

try {
    # ---- 1. pinned pipeline, byte-verified (szl-forge PR #440, commit c6e60fee) ----
    $Pin  = "c6e60feef44c1591bf3b3dd680166abdfeff49a4"
    $Want = "6a4b893b8d5141e73e2d1e91b0cc4f84c1ceb0bef5ea9230cc4f4288a1440a15"
    $Pipe = Join-Path $Root "szl_omen_pipeline.py"
    Invoke-WebRequest -UseBasicParsing -Uri ("https://raw.githubusercontent.com/szl-holdings/szl-forge/" + $Pin + "/tools/szl_omen_pipeline.py") -OutFile $Pipe
    $Got = (Get-FileHash -LiteralPath $Pipe -Algorithm SHA256).Hash.ToLower()
    if ($Got -ne $Want) { throw ("pipeline hash mismatch: got " + $Got + " want " + $Want) }
    Write-Host ("[1/6] pipeline OK  sha256=" + $Got)

    # ---- 2. dependencies (no upgrades: the pinned torch/transformers stack stays as installed) ----
    python -m pip install --quiet huggingface_hub transformers peft trl datasets safetensors accelerate
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Write-Host "[2/6] deps present"

    # ---- 3. GPU preflight: fail closed, never CPU ----
    python -c "import sys,torch; ok=torch.cuda.is_available() and torch.cuda.is_bf16_supported(); print('torch',torch.__version__,'cuda',torch.version.cuda,'gpu',torch.cuda.get_device_name(0) if ok else 'NONE'); sys.exit(0 if ok else 2)"
    if ($LASTEXITCODE -ne 0) { throw "CUDA/bf16 unavailable here. Run this on the 5050 laptop; nothing was trained." }
    Write-Host "[3/6] CUDA preflight OK"

    # ---- 4. train the challenger (immutable, timestamped output) ----
    $Chal = Join-Path $Root ("dpo-khipu-r4-challenger-" + $Stamp)
    python $Pipe dpo --out $Chal --epochs 2
    if ($LASTEXITCODE -ne 0) { throw ("dpo stopped; read " + (Join-Path $Chal "dpo_receipt.json")) }
    Write-Host ("[4/6] challenger trained -> " + $Chal)

    # ---- 5. held-out MEASURED counts, baseline (khipu-r3) vs challenger ----
    python $Pipe eval-abstain --challenger $Chal
    if ($LASTEXITCODE -ne 0) { throw ("eval-abstain stopped; read " + (Join-Path $Chal "eval\eval_receipt.json")) }
    Write-Host "[5/6] held-out evaluation recorded"

    # ---- 6. WO1 card reconciliation: dry-run always; PRs only behind the owner gate ----
    $Cards = Join-Path $Root ("cards-reconcile-" + $Stamp)
    python $Pipe cards --out $Cards
    if ($LASTEXITCODE -ne 0) { throw "cards dry-run failed" }
    if ($ApplyCards) {
        python $Pipe cards --apply --owner-confirmed-wo6 --out $Cards
        if ($LASTEXITCODE -ne 0) { throw "cards --apply refused (owner gate or token); nothing was written" }
    }
    Write-Host ("[6/6] card diffs -> " + $Cards + "  (apply=" + $ApplyCards + ")")

    # ---- evidence: print the receipts that establish completion ----
    $Show = @'
import json, pathlib, sys
chal = pathlib.Path(sys.argv[1]); cards = pathlib.Path(sys.argv[2])
d = json.loads((chal / "dpo_receipt.json").read_text(encoding="utf-8"))
e = json.loads((chal / "eval" / "eval_receipt.json").read_text(encoding="utf-8"))
c = json.loads((cards / "cards_receipt.json").read_text(encoding="utf-8"))
print("=== DPO RECEIPT ===")
print("status", d["status"], "| pairs_used", d["pairs_used"], "| pair_classes", d["pair_classes"])
print("train_loss", round(d["train_loss"], 4), "(" + d["train_loss_label"] + ")", "| gpu", d["hardware"]["gpu"])
print("policy", d["policy"]["adapter"], "@", d["policy"]["adapter_revision"][:10], "| data @", d["data"]["revision"][:10])
print("adapter_sha256", d["adapter_sha256"])
print("=== HELD-OUT RECEIPT (MEASURED) ===")
for f, r in e["results"].items():
    b, ch = r["baseline"], r["challenger"]
    print(f, "| baseline", str(b["correct"]) + "/" + str(b["total"]), "| challenger", str(ch["correct"]) + "/" + str(ch["total"]),
          "| parse_fail b/c", b["parse_failures"], ch["parse_failures"], "| invented b/c", b["invented_handle_rows"], ch["invented_handle_rows"])
print("advisory_challenger_improves", e["advisory_challenger_improves"], "| promotion", e["promotion"], "| publication_eligible", e["publication_eligible"])
print("=== CARDS ===", c["status"], "|", sum(1 for i in c["items"] if i["changes"] and not i["changes"][0].startswith(("SKIP", "NOOP"))), "repos with diffs")
print("receipts:", chal / "dpo_receipt.json", "|", chal / "eval" / "eval_receipt.json", "|", cards / "cards_receipt.json")
'@
    $Show | python - $Chal $Cards
    if ($LASTEXITCODE -ne 0) { throw "receipt summary failed; open the JSON files directly" }
    Write-Host "RUN COMPLETE - attach the transcript in logs\ and the three receipts."
}
finally {
    Stop-Transcript | Out-Null
}
