# SZL khipu-abstain DPO lane - one paste, administrator PowerShell 5.1, no prior shell state.
# Machine: the RTX 5050 laptop (C:\Users\steph, 8 GB). On a box without CUDA the preflight stops before any training.
# Memory: pipeline 3dee2933 trains in bf16 without autocast (no fp32 logits upcast), releases the CUDA cache every step,
# and steps a sequence-budget ladder 1024 -> 768 -> 640 recording every attempt (runs at 22:24, 23:24 and 23:47 EDT OOMed).
# Changes: creates %USERPROFILE%\szl\{logs, dpo-khipu-r4-challenger-<stamp>, cards-reconcile-<stamp>, bundle-<stamp>} only.
# Does not change: Hub repos, GitHub, the pinned .venv-ra-v2 / .venv-ra-v3 stacks, any token, any card.
# Cards: the three Hub pull requests are already open (khipu-r3 #2, brain-navigator-r2 #2, receiptagent-v3 #3),
# so this run only writes card diffs for the record; nothing here needs a Hugging Face token.
# Output: bundle-<stamp>\receipts\khipu-abstain\<run_id>\ - the immutable evidence bundle to hand back (PR into szl-forge).

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Join-Path $env:USERPROFILE "szl"
New-Item -ItemType Directory -Force -Path $Root | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null
Set-Location -LiteralPath $Root
$Stamp = Get-Date -Format "yyyyMMdd-HHmm"
Start-Transcript -Path (Join-Path $Root ("logs\khipu-dpo-" + $Stamp + ".log")) | Out-Null

function Get-PinnedTool {
    param([string]$Pin, [string]$RelPath, [string]$Want, [string]$OutFile)
    Invoke-WebRequest -UseBasicParsing -Uri ("https://raw.githubusercontent.com/szl-holdings/szl-forge/" + $Pin + "/" + $RelPath) -OutFile $OutFile
    $Got = (Get-FileHash -LiteralPath $OutFile -Algorithm SHA256).Hash.ToLower()
    if ($Got -ne $Want) { throw ($RelPath + " hash mismatch: got " + $Got + " want " + $Want) }
    return $Got
}

try {
    # ---- 1. pinned tools, byte-verified (szl-forge huggingface branch, commit 3dee2933 = PR #469 pure-bf16 lane + PR #447 ingest) ----
    $Pin    = "3dee293331b5ac549a9412c9e7d6862557da2743"
    $Pipe   = Join-Path $Root "szl_omen_pipeline.py"
    $Ingest = Join-Path $Root "ingest_khipu_abstain_receipts.py"
    $GotPipe   = Get-PinnedTool -Pin $Pin -RelPath "tools/szl_omen_pipeline.py" -Want "ef3a9049ca8ebd9f48cfecb1c039792360d220cc101bd638f2e563ed84432da2" -OutFile $Pipe
    $GotIngest = Get-PinnedTool -Pin $Pin -RelPath "tools/ingest_khipu_abstain_receipts.py" -Want "e5a1551fed8a66127ee8170639d0791bfeb65b453c0dc2dc0aec5402df51cd0d" -OutFile $Ingest
    Write-Host ("[1/7] pipeline OK sha256=" + $GotPipe)
    Write-Host ("      ingest   OK sha256=" + $GotIngest)

    # ---- 2. dependencies (no upgrades: the pinned torch/transformers stack stays as installed) ----
    python -m pip install --quiet huggingface_hub transformers peft trl datasets safetensors accelerate
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Write-Host "[2/7] deps present"

    # ---- 3. GPU preflight: fail closed, never CPU ----
    python -c "import sys,torch; ok=torch.cuda.is_available() and torch.cuda.is_bf16_supported(); print('torch',torch.__version__,'cuda',torch.version.cuda,'gpu',torch.cuda.get_device_name(0) if ok else 'NONE'); sys.exit(0 if ok else 2)"
    if ($LASTEXITCODE -ne 0) { throw "CUDA/bf16 unavailable here. Run this on the 5050 laptop; nothing was trained." }
    Write-Host "[3/7] CUDA preflight OK"

    # ---- 4. train the challenger (immutable, timestamped output) ----
    $Chal = Join-Path $Root ("dpo-khipu-r4-challenger-" + $Stamp)
    python $Pipe dpo --out $Chal --epochs 2
    if ($LASTEXITCODE -ne 0) { throw ("dpo stopped; read " + (Join-Path $Chal "dpo_receipt.json")) }
    Write-Host ("[4/7] challenger trained -> " + $Chal)

    # ---- 5. held-out MEASURED counts, baseline (khipu-r3) vs challenger ----
    python $Pipe eval-abstain --challenger $Chal
    if ($LASTEXITCODE -ne 0) { throw ("eval-abstain stopped; read " + (Join-Path $Chal "eval\eval_receipt.json")) }
    Write-Host "[5/7] held-out evaluation recorded"

    # ---- 6. card diffs for the record (dry-run only; Hub PRs already exist) ----
    $Cards = Join-Path $Root ("cards-reconcile-" + $Stamp)
    python $Pipe cards --all --out $Cards
    if ($LASTEXITCODE -ne 0) { throw "cards dry-run failed" }
    Write-Host ("[6/7] card diffs -> " + $Cards)

    # ---- 7. stage the immutable evidence bundle (fail-closed cross-receipt checks; derived STATUS.md) ----
    $Bundle = Join-Path $Root ("bundle-" + $Stamp)
    python $Ingest stage $Chal --cards $Cards --out $Bundle
    if ($LASTEXITCODE -ne 0) { throw "ingest refused the receipts; read the reasons above. Nothing was staged." }
    $BundleDir = Get-ChildItem -LiteralPath (Join-Path $Bundle "receipts\khipu-abstain") -Directory | Select-Object -First 1
    python $Ingest validate $BundleDir.FullName
    if ($LASTEXITCODE -ne 0) { throw "staged bundle failed re-validation" }
    Write-Host ("[7/7] evidence bundle -> " + $BundleDir.FullName)

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
    Write-Host ("RUN COMPLETE - hand back the bundle directory " + $BundleDir.FullName + " (open it as a PR into szl-forge under receipts/khipu-abstain/) plus the transcript in logs\.")
}
finally {
    Stop-Transcript | Out-Null
}
