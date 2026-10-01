# SZL khipu-abstain DPO lane - one paste, administrator PowerShell 5.1, no prior shell state.
# Machine: the RTX 5050 laptop (C:\Users\steph, 8 GB). On a box without CUDA the preflight stops before any training.
# Lane: WSL-first. The estate's qualified Unsloth environment lives in WSL (szl-forge audit/HF_MODEL_TRAINING_2026-09-12.md:
# /home/rosie/.venvs/szl-unsloth, Torch 2.10.0 / TRL 0.24.0 / Transformers 5.5.0 / PEFT 0.19.1, locked - nothing is installed
# into it). There TRL still has use_logits_to_keep and Linux can use expandable segments, so the 248k-vocab logits that
# OOMed the Windows-native lane three times (22:24, 23:24, 23:47 EDT) are never materialised in full. If that venv is
# absent the lane falls back to Windows python and the receipt's platform field says so.
# Changes: creates %USERPROFILE%\szl\{logs, dpo-khipu-r4-challenger-<stamp>, cards-reconcile-<stamp>, bundle-<stamp>} only.
# Does not change: Hub repos, GitHub, the pinned .venv-ra-v2 / .venv-ra-v3 stacks, the WSL szl-unsloth venv, any token, any card.
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

function ConvertTo-WslPath([string]$WinPath) {
    $full = [IO.Path]::GetFullPath($WinPath)
    $drive = $full.Substring(0, 1).ToLower()
    return ("/mnt/" + $drive + ($full.Substring(2) -replace "\\", "/"))
}
function Find-WslLane {
    # Returns the distro that carries the qualified venv, or $null. Read-only probe.
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return $null }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = (& wsl.exe -l -q 2>$null) -join "`n"
        $names = @($raw -replace "\0", "" -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
        foreach ($d in $names) {
            $probe = & wsl.exe -d $d -u rosie -- bash -lc "test -x /home/rosie/.venvs/szl-unsloth/bin/python && test -x /usr/lib/wsl/lib/nvidia-smi && echo SZL_LANE_OK" 2>$null
            if (($probe -join "") -match "SZL_LANE_OK") { return $d }
        }
        return $null
    } catch { return $null }
    finally { $ErrorActionPreference = $prev }
}
$Distro = Find-WslLane
$WslPy = "/home/rosie/.venvs/szl-unsloth/bin/python"
function Invoke-Lane {
    # Runs python with the given arguments in the WSL qualified venv (paths translated) or in Windows python.
    param([string[]]$PyArgs)
    if ($Distro) {
        $tx = @()
        foreach ($a in $PyArgs) { if ($a -match "^[A-Za-z]:\\") { $tx += (ConvertTo-WslPath $a) } else { $tx += $a } }
        & wsl.exe -d $Distro -u rosie -- env HF_HUB_DISABLE_PROGRESS_BARS=1 PYTHONUNBUFFERED=1 PYTORCH_ALLOC_CONF=expandable_segments:True $WslPy @tx
    } else {
        & python @PyArgs
    }
}

try {
    # ---- 1. pinned tools, byte-verified (szl-forge huggingface branch, commit c8b746bb = PR #474 knob probe + PR #473 C3 profile + PR #476 ingest registry) ----
    $Pin    = "c8b746bb8fae329f280c65ee810cf807a333fd78"
    $Pipe   = Join-Path $Root "szl_omen_pipeline.py"
    $Ingest = Join-Path $Root "ingest_khipu_abstain_receipts.py"
    $GotPipe   = Get-PinnedTool -Pin $Pin -RelPath "tools/szl_omen_pipeline.py" -Want "0093753bd18510ee79f1d99f20a143951e44fa90b117c674b1d85c4d7acd491d" -OutFile $Pipe
    $GotIngest = Get-PinnedTool -Pin $Pin -RelPath "tools/ingest_khipu_abstain_receipts.py" -Want "2755dc2db2bb9c2a0db4933f03176b1994ca057af9e8e7a4cdf2db5b05201d30" -OutFile $Ingest
    Write-Host ("[1/7] pipeline OK sha256=" + $GotPipe)
    Write-Host ("      ingest   OK sha256=" + $GotIngest)

    # ---- 2. dependencies: WSL lane = locked venv, import-checked only; Windows lane = quiet install, no upgrades ----
    if ($Distro) {
        $DepsPy = Join-Path $Root "lane_deps.py"
        Set-Content -LiteralPath $DepsPy -Encoding Ascii -Value "import torch, transformers, trl, peft, datasets, accelerate, safetensors, huggingface_hub`nprint('wsl venv ok: torch', torch.__version__, 'trl', trl.__version__, 'transformers', transformers.__version__, 'peft', peft.__version__)"
        Invoke-Lane @($DepsPy)
        if ($LASTEXITCODE -ne 0) { throw "the WSL szl-unsloth venv is missing a required package; nothing was installed into it" }
        Write-Host ("[2/7] deps present (WSL lane: distro " + $Distro + ", venv szl-unsloth, locked)")
    } else {
        python -m pip install --quiet huggingface_hub transformers peft trl datasets safetensors accelerate
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
        Write-Host "[2/7] deps present (Windows lane; no WSL venv found)"
    }

    # ---- 3. GPU preflight: fail closed, never CPU ----
    $CudaPy = Join-Path $Root "lane_cuda.py"
    Set-Content -LiteralPath $CudaPy -Encoding Ascii -Value "import sys, torch`nok = torch.cuda.is_available() and torch.cuda.is_bf16_supported()`nprint('torch', torch.__version__, 'cuda', torch.version.cuda, 'gpu', torch.cuda.get_device_name(0) if ok else 'NONE')`nsys.exit(0 if ok else 2)"
    Invoke-Lane @($CudaPy)
    if ($LASTEXITCODE -ne 0) { throw "CUDA/bf16 unavailable here. Run this on the 5050 laptop; nothing was trained." }
    Write-Host "[3/7] CUDA preflight OK"

    # ---- 4. train the challenger (profile C3: NLL-anchored, lr 1e-5, beta 0.3, one epoch; C2 collapsed on 2026-10-01) ----
    $Chal = Join-Path $Root ("dpo-khipu-r4-challenger-" + $Stamp)
    Invoke-Lane @($Pipe, "dpo", "--out", $Chal, "--profile", "C3")
    if ($LASTEXITCODE -ne 0) { throw ("dpo stopped; read " + (Join-Path $Chal "dpo_receipt.json")) }
    Write-Host ("[4/7] challenger trained -> " + $Chal)

    # ---- 5. held-out MEASURED counts, baseline (khipu-r3) vs challenger ----
    Invoke-Lane @($Pipe, "eval-abstain", "--challenger", $Chal)
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
