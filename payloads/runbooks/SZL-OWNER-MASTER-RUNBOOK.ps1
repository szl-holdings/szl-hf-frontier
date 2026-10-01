# SZL owner master runbook - one paste, administrator PowerShell 5.1, no prior shell state.
# Covers every owner-only item left open by the 2026-09-30 wave, in order, each lane independent and fail-closed:
#   1. WO6   - revoke the four Hugging Face tokens exposed in chat on 2026-09-12 (owner attestation; browser)
#   2. BRAND - fine-grained HF token with WRITE on the two marketing Spaces -> HF_TOKEN on szl-brand -> exact projection
#   3. DAVID - fine-grained HF token with READ on SZLHOLDINGS/david-leads-data -> environment secret -> rotation
#   4. EDGE  - scoped Cloudflare user API token -> CLOUDFLARE_API_TOKEN on a11oy/production -> bounded edge repair
#   5. DPO   - khipu-abstain challenger on CUDA (pinned runbook, child process) -> evidence bundle -> szl-forge PR
#   6. MKT   - marketing engine: live labeled factbase, operating plan, first channel drafts (local files only)
#   7. VERIFY- waits for the dispatched runs, reads the Hub back, writes one secret-free master receipt
# Tokens: never typed. You click COPY in the browser, come back, press Enter; the script reads the clipboard,
# validates the shape, uses the token through stdin only, and overwrites the clipboard. Type SKIP to skip a lane.
# Does not change: model weights, cards, DNS, any branch of main; every remote effect goes through an existing
# governed workflow or a pull request, and each lane prints exactly what it did.

param([string[]]$Only = @())   # e.g. -Only dpo  or  -Only brand,david ; empty = every lane

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$ProgressPreference = "SilentlyContinue"

# ---------------------------------------------------------------- pins (byte-verified before use)
$FrontierPin  = "05c405e93c15a0a7a02b5bb933c194bb47d4dd37"                          # szl-hf-frontier main, 2026-10-01 (DPO runbook re-pinned to the memory-ladder pipeline)
$DpoRunbookSha = "4af2caeecb3f3fbd1c2b3d0c15f7adc2f9477753f80a199ecf0726eb8d9b29ec"  # payloads/runbooks/SZL-KHIPU-DPO-RUNBOOK.ps1
$BrandPin     = "4e47b59ff482fbf607e46a65498144a6175a4546"                          # szl-brand main = PR #131 squash

$Root = Join-Path $env:USERPROFILE "szl"
foreach ($d in @("", "logs", "receipts", "marketing-out", "tools")) { New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null }
Set-Location -LiteralPath $Root
$Stamp = Get-Date -Format "yyyyMMdd-HHmm"
$StartedUtc = [DateTime]::UtcNow
$ExitCode = 1
Start-Transcript -Path (Join-Path $Root ("logs\owner-master-" + $Stamp + ".log")) | Out-Null

$Lanes = [ordered]@{}
function Lane-Enabled { param([string]$Name) return ($Only.Count -eq 0 -or ($Only -contains $Name)) }
function Set-Lane { param([string]$Name, [string]$State, [string]$Detail = "")
    $script:Lanes[$Name] = [ordered]@{ state = $State; detail = $Detail; at_utc = [DateTime]::UtcNow.ToString("o") }
    Write-Host ("  [" + $Name + "] " + $State + $(if ($Detail) { " - " + $Detail } else { "" }))
}
function Fail-Lane { param([string]$Name, [System.Management.Automation.ErrorRecord]$Err)
    $msg = [string]$Err.Exception.Message
    if ($msg -match "hf_[A-Za-z0-9]{10,}") { $msg = "(message withheld: it contained a token)" }
    Set-Lane -Name $Name -State "FAILED" -Detail $msg
}
function Read-TokenFromClipboard { param([string]$Label, [string]$Pattern)
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $answer = Read-Host ("   " + $Label + " -> click COPY in the browser, then press Enter here (type nothing), or type SKIP")
        if ($null -ne $answer -and $answer.Trim().ToUpper() -eq "SKIP") { return $null }
        $clip = ""
        try { $clip = [string](Get-Clipboard -Raw) } catch { $clip = "" }
        if ($null -eq $clip) { $clip = "" }
        $clip = $clip.Trim()
        if ($clip -match $Pattern) { Set-Clipboard -Value "cleared"; return $clip }
        Write-Host ("   clipboard does not hold a matching token (" + $clip.Length + " chars). Copy it again - attempt " + $attempt + " of 3, or type SKIP.")
    }
    return $null
}
function Get-PinnedFrontierFile { param([string]$RelPath, [string]$Want, [string]$OutFile)
    $json = & gh api ("repos/szl-holdings/szl-hf-frontier/contents/" + $RelPath + "?ref=" + $FrontierPin) | ConvertFrom-Json
    $b64 = ([string]$json.content) -replace "\s", ""
    $bytes = [Convert]::FromBase64String($b64)
    [IO.File]::WriteAllBytes($OutFile, $bytes)
    $got = (Get-FileHash -LiteralPath $OutFile -Algorithm SHA256).Hash.ToLower()
    if ($got -ne $Want) { throw ($RelPath + " hash mismatch: got " + $got + " want " + $Want) }
    return $OutFile
}
function Get-LatestRun { param([string]$Repo, [string]$Workflow)
    $json = & gh run list --repo $Repo --workflow $Workflow --limit 1 --json databaseId,status,conclusion,url,createdAt,headSha
    if ($LASTEXITCODE -ne 0 -or -not $json) { return $null }
    $runs = @($json | ConvertFrom-Json)
    if ($runs.Count -eq 0) { return $null }
    return $runs[0]
}
function Test-HfFineGrained { param([hashtable]$Headers)
    $who = Invoke-RestMethod -UseBasicParsing -Uri "https://huggingface.co/api/whoami-v2" -Headers $Headers
    $role = [string]$who.auth.accessToken.role
    if (($role -replace "[^a-zA-Z]", "").ToLower() -ne "finegrained") { throw ("token role is '" + $role + "', not fine-grained") }
    return $who
}
function Test-HfScopedWrite { param($Who, [string[]]$Repos)
    $fg = $Who.auth.accessToken.fineGrained
    $scoped = @()
    if ($fg -and $fg.PSObject.Properties["scoped"]) { $scoped = @($fg.scoped) }
    foreach ($r in $Repos) {
        $ok = $false
        foreach ($entry in $scoped) {
            $name = ""
            if ($entry.PSObject.Properties["entity"] -and $entry.entity.PSObject.Properties["name"]) { $name = [string]$entry.entity.name }
            $perms = @()
            if ($entry.PSObject.Properties["permissions"]) { $perms = @($entry.permissions) }
            if (($name -eq $r -or $name -eq "SZLHOLDINGS") -and ($perms -contains "repo.write")) { $ok = $true }
        }
        if (-not $ok) { throw ("token has no repo.write on " + $r) }
    }
}

try {
    # ================================================================ 0. preflight (read-only)
    Write-Host ("== SZL owner master runbook " + $Stamp + " on " + $env:COMPUTERNAME + " as " + $env:USERNAME + " ==")
    if ($PSVersionTable.PSVersion.Major -ne 5) { Write-Host ("   note: PowerShell " + $PSVersionTable.PSVersion + " (written for 5.1; continuing)") }
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) { Write-Host "   note: not elevated; nothing here needs admin, continuing" }
    if (-not (Get-Command gh.exe -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) is required: winget install --id GitHub.cli, open a new window, rerun." }
    & gh auth status --hostname github.com
    if ($LASTEXITCODE -ne 0) { & gh auth login --hostname github.com --web --git-protocol https --scopes "repo,workflow"; if ($LASTEXITCODE -ne 0) { throw "gh login failed" } }
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw "git is required (winget install --id Git.Git)" }
    if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) { throw "python is required on PATH" }
    & python --version
    Set-Lane -Name "preflight" -State "OK" -Detail ("root " + $Root)

    # ================================================================ 1. WO6 token hygiene (owner attestation)
    if (-not (Lane-Enabled "wo6")) { Set-Lane -Name "wo6" -State "NOT_SELECTED" } else {
    Write-Host ""
    Write-Host "1) WO6 - revoke the four tokens exposed in chat on 2026-09-12: hf_hjUJ..., hf_azHb..., hf_nGHC..., hf_rpzm..."
    Write-Host "   The token settings page opens. Delete any of those four that still exist, then come back."
    Start-Process "https://huggingface.co/settings/tokens"
    $a = Read-Host "   type REVOKED when they are gone (or already gone), or SKIP"
    if ($null -ne $a -and $a.Trim().ToUpper() -eq "REVOKED") { Set-Lane -Name "wo6" -State "OWNER_ATTESTED" -Detail "owner states the four 2026-09-12 tokens are revoked (not machine-verifiable)" }
    else { Set-Lane -Name "wo6" -State "SKIPPED" -Detail "publish gates keep recording wo6_status honestly" }
    }

    # ================================================================ 2. BRAND - szl-brand Spaces publisher token
    Write-Host ""
    if (-not (Lane-Enabled "brand")) { Set-Lane -Name "brand" -State "NOT_SELECTED" } else {
    Write-Host "2) BRAND - fine-grained token, name szl-brand-spaces-publisher, WRITE access to contents/settings of:"
    Write-Host "     SZLHOLDINGS/szl-marketing-1.1   and   SZLHOLDINGS/szl-brand-campaign   (nothing else ticked)"
    try {
        Start-Process "https://huggingface.co/settings/tokens/new?tokenType=fineGrained"
        $tok = Read-TokenFromClipboard -Label "brand Spaces token" -Pattern '^hf_[A-Za-z0-9]{20,}$'
        if (-not $tok) { Set-Lane -Name "brand" -State "SKIPPED" -Detail "szl-brand HF_TOKEN still invalid; hf-marketing-spaces keeps failing closed" }
        else {
            $h = @{ Authorization = ("Bearer " + $tok) }
            $who = Test-HfFineGrained -Headers $h
            Test-HfScopedWrite -Who $who -Repos @("SZLHOLDINGS/szl-marketing-1.1", "SZLHOLDINGS/szl-brand-campaign")
            $tok | & gh secret set HF_TOKEN --repo szl-holdings/szl-brand
            if ($LASTEXITCODE -ne 0) { throw "gh secret set HF_TOKEN failed (needs admin on szl-brand)" }
            & gh workflow run hf-marketing-spaces.yml --repo szl-holdings/szl-brand --ref main -f confirmation=PUBLISH-SZL-MARKETING-SPACES -f target=all
            if ($LASTEXITCODE -ne 0) { throw "workflow dispatch failed" }
            Set-Lane -Name "brand" -State "DISPATCHED" -Detail ("identity " + $who.name + "; HF_TOKEN stored; hf-marketing-spaces dispatched")
        }
    } catch { Fail-Lane -Name "brand" -Err $_ }
    finally { $tok = $null; $h = $null; $who = $null }
    }

    # ================================================================ 3. DAVID - dataset reader token
    Write-Host ""
    if (-not (Lane-Enabled "david")) { Set-Lane -Name "david" -State "NOT_SELECTED" } else {
    Write-Host "3) DAVID - fine-grained token, name david-dataset-reader, READ access to contents of ONLY the dataset:"
    Write-Host "     SZLHOLDINGS/david-leads-data   (no write, no inference, no org boxes)"
    try {
        Start-Process "https://huggingface.co/settings/tokens/new?tokenType=fineGrained"
        $tok = Read-TokenFromClipboard -Label "David reader token" -Pattern '^hf_[A-Za-z0-9]{20,}$'
        if (-not $tok) { Set-Lane -Name "david" -State "SKIPPED" -Detail "live-lanes canary stays red (FORM5500_VERIFIED_SNAPSHOT_UNAVAILABLE)" }
        else {
            $h = @{ Authorization = ("Bearer " + $tok) }
            $who = Test-HfFineGrained -Headers $h
            $ds = Invoke-RestMethod -UseBasicParsing -Uri "https://huggingface.co/api/datasets/SZLHOLDINGS/david-leads-data" -Headers $h
            if (-not $ds.sha) { throw "token cannot read SZLHOLDINGS/david-leads-data" }
            $tok | & gh secret set DAVID_DATASET_READ_TOKEN --repo szl-holdings/david-leads --env david-space-credential-rotation
            if ($LASTEXITCODE -ne 0) { throw "gh secret set DAVID_DATASET_READ_TOKEN failed (needs admin on david-leads)" }
            & gh workflow run rotate-space-credentials.yml --repo szl-holdings/david-leads --ref main
            if ($LASTEXITCODE -ne 0) { throw "rotation dispatch failed" }
            Set-Lane -Name "david" -State "DISPATCHED" -Detail ("identity " + $who.name + "; dataset @ " + ([string]$ds.sha).Substring(0, 10) + "; rotation dispatched (approve the environment run when GitHub asks)")
        }
    } catch { Fail-Lane -Name "david" -Err $_ }
    finally { $tok = $null; $h = $null; $who = $null }
    }

    # ================================================================ 4. EDGE - Cloudflare production authority
    Write-Host ""
    if (-not (Lane-Enabled "edge")) { Set-Lane -Name "edge" -State "NOT_SELECTED" } else {
    Write-Host "4) EDGE - custom Cloudflare USER API token (not the Global API Key) with exactly:"
    Write-Host "     Account > Workers Scripts > Edit (your SZL account)"
    Write-Host "     Zone > Workers Routes > Edit, Zone > DNS > Edit, Zone > Zone > Read  -  zones a-11-oy.com and a11oy.net"
    try {
        Start-Process "https://dash.cloudflare.com/profile/api-tokens"
        $tok = Read-TokenFromClipboard -Label "Cloudflare token" -Pattern '^[A-Za-z0-9_-]{30,}$'
        if (-not $tok) { Set-Lane -Name "edge" -State "SKIPPED" -Detail "edge-repair workflow keeps recording UNAVAILABLE" }
        else {
            $h = @{ Authorization = ("Bearer " + $tok); Accept = "application/json"; "User-Agent" = "SZL-owner-master/1.0" }
            $verify = Invoke-RestMethod -UseBasicParsing -Uri "https://api.cloudflare.com/client/v4/user/tokens/verify" -Headers $h
            if ($verify.success -ne $true -or $verify.result.status -ne "active") { throw "Cloudflare did not report the token as active" }
            foreach ($zoneName in @("a-11-oy.com", "a11oy.net")) {
                $zones = Invoke-RestMethod -UseBasicParsing -Uri ("https://api.cloudflare.com/client/v4/zones?name=" + [Uri]::EscapeDataString($zoneName) + "&status=active&per_page=50") -Headers $h
                if ($zones.success -ne $true -or @($zones.result).Count -ne 1) { throw ("token cannot resolve exactly one active zone for " + $zoneName) }
                $zoneId = [string](@($zones.result)[0].id)
                $dns = Invoke-RestMethod -UseBasicParsing -Uri ("https://api.cloudflare.com/client/v4/zones/" + $zoneId + "/dns_records?per_page=1") -Headers $h
                $routes = Invoke-RestMethod -UseBasicParsing -Uri ("https://api.cloudflare.com/client/v4/zones/" + $zoneId + "/workers/routes") -Headers $h
                if ($dns.success -ne $true -or $routes.success -ne $true) { throw ("readback failed for " + $zoneName) }
                Write-Host ("   zone OK: " + $zoneName + " (id ..." + $zoneId.Substring([Math]::Max(0, $zoneId.Length - 6)) + ")")
            }
            $tok | & gh secret set CLOUDFLARE_API_TOKEN --repo szl-holdings/a11oy --env production
            if ($LASTEXITCODE -ne 0) { throw "gh secret set CLOUDFLARE_API_TOKEN failed (needs admin on a11oy)" }
            & gh workflow run repair-cloudflare-product-edge-production.yml --repo szl-holdings/a11oy --ref main -f dry_run=false
            if ($LASTEXITCODE -ne 0) { throw "edge repair dispatch failed" }
            Set-Lane -Name "edge" -State "DISPATCHED" -Detail "CLOUDFLARE_API_TOKEN stored in a11oy/production; bounded edge repair dispatched (approve the production environment if GitHub asks)"
        }
    } catch { Fail-Lane -Name "edge" -Err $_ }
    finally { $tok = $null; $h = $null }
    }

    # ================================================================ 5. DPO - khipu-abstain challenger (CUDA only)
    Write-Host ""
    if (-not (Lane-Enabled "dpo")) { Set-Lane -Name "dpo" -State "NOT_SELECTED" } else {
    Write-Host "5) DPO - khipu-abstain challenger: pinned runbook, CUDA only, ~30 minutes, then the evidence bundle becomes a szl-forge PR"
    try {
        $gpu = $false
        if (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) {
            & python -c "import sys, importlib.util; sys.exit(3) if importlib.util.find_spec('torch') is None else None; import torch; sys.exit(0 if torch.cuda.is_available() else 2)"
            if ($LASTEXITCODE -eq 0) { $gpu = $true }
        }
        if (-not $gpu) { Set-Lane -Name "dpo" -State "UNAVAILABLE" -Detail "no CUDA torch on this machine; run this runbook on the RTX 5050 laptop for lane 5" }
        else {
            $dpo = Get-PinnedFrontierFile -RelPath "payloads/runbooks/SZL-KHIPU-DPO-RUNBOOK.ps1" -Want $DpoRunbookSha -OutFile (Join-Path $Root "tools\SZL-KHIPU-DPO-RUNBOOK.ps1")
            Write-Host ("   runbook byte-verified: " + $dpo)
            $before = Get-Date
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $dpo
            if ($LASTEXITCODE -ne 0) { throw ("DPO runbook exited " + $LASTEXITCODE + "; read logs\khipu-dpo-*.log (nothing was published)") }
            $bundleDir = Get-ChildItem -LiteralPath $Root -Directory -Filter "bundle-*" | Where-Object { $_.LastWriteTime -ge $before.AddMinutes(-1) } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if (-not $bundleDir) { throw "DPO finished but no bundle-* directory was created" }
            $runDir = Get-ChildItem -LiteralPath (Join-Path $bundleDir.FullName "receipts\khipu-abstain") -Directory | Select-Object -First 1
            if (-not $runDir) { throw "bundle has no receipts\khipu-abstain\<run_id> directory" }
            $runId = $runDir.Name
            # hand back: one GitHub-signed commit per file through the contents API, then a pull request
            $mainSha = [string](& gh api repos/szl-holdings/szl-forge/git/ref/heads/main --jq .object.sha)
            if ($LASTEXITCODE -ne 0) { throw "could not read szl-forge main" }
            $branch = "receipts/khipu-abstain-" + $runId + "-" + $Stamp
            & gh api repos/szl-holdings/szl-forge/git/refs -f ("ref=refs/heads/" + $branch) -f ("sha=" + $mainSha) | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "could not create the receipts branch" }
            $files = Get-ChildItem -LiteralPath $runDir.FullName -File -Recurse
            foreach ($f in $files) {
                $rel = $f.FullName.Substring($runDir.FullName.Length).TrimStart("\") -replace "\\", "/"
                $repoPath = "receipts/khipu-abstain/" + $runId + "/" + $rel
                $body = @{ message = ("receipt(khipu-abstain): " + $runId + " - " + $rel); content = [Convert]::ToBase64String([IO.File]::ReadAllBytes($f.FullName)); branch = $branch } | ConvertTo-Json -Compress
                $bodyFile = Join-Path $env:TEMP ("szl-body-" + [Guid]::NewGuid().ToString("N") + ".json")
                [IO.File]::WriteAllText($bodyFile, $body, (New-Object System.Text.UTF8Encoding($false)))
                $encodedPath = (($repoPath -split "/") | ForEach-Object { [Uri]::EscapeDataString($_) }) -join "/"
                & gh api -X PUT ("repos/szl-holdings/szl-forge/contents/" + $encodedPath) --input $bodyFile | Out-Null
                $code = $LASTEXITCODE
                Remove-Item -LiteralPath $bodyFile -Force
                if ($code -ne 0) { throw ("upload failed for " + $rel) }
                Write-Host ("   staged " + $repoPath)
            }
            $prBody = "## Origin`n`nOwner laptop run of payloads/runbooks/SZL-KHIPU-DPO-RUNBOOK.ps1 (szl-hf-frontier@" + $FrontierPin.Substring(0, 8) + ") via the owner master runbook " + $Stamp + ".`n`n## Evidence`n`nImmutable bundle receipts/khipu-abstain/" + $runId + "/ (MANIFEST.json, STATUS.md, dpo_receipt.json, eval receipts). publication_eligible stays false; promotion stays NOT_PROMOTABLE until the canonical Forge gate derives otherwise.`n`n## Tests`n`nStaged and re-validated by tools/ingest_khipu_abstain_receipts.py on the laptop before upload.`n`n## Rollback`n`nClose this PR; nothing outside receipts/khipu-abstain/" + $runId + "/ is touched."
            $prUrl = [string](& gh pr create --repo szl-holdings/szl-forge --base main --head $branch --title ("receipt(khipu-abstain): challenger bundle " + $runId) --body $prBody)
            if ($LASTEXITCODE -ne 0) { throw "pull request creation failed (branch and files are pushed; open the PR by hand)" }
            Set-Lane -Name "dpo" -State "PR_OPENED" -Detail ($prUrl + " (promotion stays NOT_PROMOTABLE; the Forge gate decides)")
        }
    } catch { Fail-Lane -Name "dpo" -Err $_ }
    }

    # ================================================================ 6. MKT - marketing engine, local only
    Write-Host ""
    if (-not (Lane-Enabled "mkt")) { Set-Lane -Name "mkt" -State "NOT_SELECTED" } else {
    Write-Host "6) MKT - live labeled factbase, operating plan and first channel drafts (files only; nothing is posted)"
    try {
        $py = $null
        & python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 3)"
        if ($LASTEXITCODE -eq 0) { $py = "python" }
        elseif (Get-Command py.exe -ErrorAction SilentlyContinue) { & py -3.12 -c "import sys" ; if ($LASTEXITCODE -eq 0) { $py = "py312" } }
        if (-not $py -and (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
            # szl-brand requires Python 3.12+. One guarded attempt to add it side by side (the existing interpreter is untouched).
            Write-Host "   Python 3.12+ not found; installing Python 3.12 side by side with winget (one attempt)"
            & winget install --exact --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements --silent
            $env:Path = ([Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")).Trim(";")
            if (Get-Command py.exe -ErrorAction SilentlyContinue) { & py -3.12 -c "import sys" ; if ($LASTEXITCODE -eq 0) { $py = "py312" } }
        }
        if (-not $py) { Set-Lane -Name "mkt" -State "UNAVAILABLE" -Detail "szl-brand needs Python 3.12+ and none is usable here; run lane 6 on the OMEN (Python 3.12)" }
        else {
            $brandDir = Join-Path $Root "szl-brand"
            if (-not (Test-Path -LiteralPath (Join-Path $brandDir ".git"))) { & git clone -q https://github.com/szl-holdings/szl-brand $brandDir; if ($LASTEXITCODE -ne 0) { throw "git clone szl-brand failed" } }
            & git -C $brandDir fetch -q origin
            & git -C $brandDir checkout -q $BrandPin
            if ($LASTEXITCODE -ne 0) { throw ("could not check out szl-brand@" + $BrandPin) }
            $venv = Join-Path $Root ".venv-brand"
            $vpy = Join-Path $venv "Scripts\python.exe"
            if (-not (Test-Path -LiteralPath $vpy)) { if ($py -eq "python") { & python -m venv $venv } else { & py -3.12 -m venv $venv }; if ($LASTEXITCODE -ne 0) { throw "venv creation failed" } }
            & $vpy -m pip install --quiet --disable-pip-version-check $brandDir
            if ($LASTEXITCODE -ne 0) { throw "pip install szl-brand failed" }
            $out = Join-Path $Root "marketing-out"
            & $vpy -m szl_brand.marketing.cli facts --out $out
            if ($LASTEXITCODE -ne 0) { throw "factbase pull failed" }
            & $vpy -m szl_brand.marketing.cli plan --out (Join-Path $out "plan.md")
            if ($LASTEXITCODE -ne 0) { throw "plan render failed" }
            & $vpy -m szl_brand.marketing.cli compose --facts (Join-Path $out "factbase.json") --subject-a "Receipts, not vibes" --subject-b "The honest label" --body-text "[CREATIVE CONTROL: the team's essay goes here. The fact block above stays.]" --out $out
            if ($LASTEXITCODE -ne 0) { throw "compose blocked by the linter (see output above)" }
            $facts = Get-Content -LiteralPath (Join-Path $out "factbase.json") -Raw | ConvertFrom-Json
            Set-Lane -Name "mkt" -State "DONE" -Detail ("factbase " + $facts.generated_at + ": hf " + $facts.hf.label + ", github " + $facts.github.label + "; drafts in " + $out)
        }
    } catch { Fail-Lane -Name "mkt" -Err $_ }
    }

    # ================================================================ 7. VERIFY - dispatched runs and Hub readback
    Write-Host ""
    Write-Host "7) VERIFY - waiting for dispatched runs (bounded), then reading the Hub back"
    try {
        if ($Lanes.Contains("brand") -and $Lanes["brand"].state -eq "DISPATCHED") {
            Start-Sleep -Seconds 15
            $run = Get-LatestRun -Repo "szl-holdings/szl-brand" -Workflow "hf-marketing-spaces.yml"
            if ($run) {
                & gh run watch ([string]$run.databaseId) --repo szl-holdings/szl-brand --exit-status --interval 15
                $conclusion = if ($LASTEXITCODE -eq 0) { "success" } else { "failure" }
                $dl = Join-Path $Root ("receipts\brand-run-" + $run.databaseId)
                & gh run download ([string]$run.databaseId) --repo szl-holdings/szl-brand --dir $dl
                $states = @()
                Get-ChildItem -LiteralPath $dl -Recurse -Filter "*-publish.json" -ErrorAction SilentlyContinue | ForEach-Object { $r = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json; $states += ($r.target.name + "=" + $r.state) }
                $hub = @()
                foreach ($s in @("szl-marketing-1.1", "szl-brand-campaign")) {
                    $meta = Invoke-RestMethod -UseBasicParsing -Uri ("https://huggingface.co/api/spaces/SZLHOLDINGS/" + $s)
                    $hasReceipt = @($meta.siblings | Where-Object { $_.rfilename -eq "PUBLICATION_RECEIPT.json" }).Count -eq 1
                    $hub += ($s + "@" + ([string]$meta.sha).Substring(0, 8) + $(if ($hasReceipt) { " receipt" } else { " NO-RECEIPT" }))
                }
                Set-Lane -Name "brand-verify" -State ($(if ($conclusion -eq "success") { "CONVERGED" } else { "NOT_CONVERGED" })) -Detail (($states -join ", ") + " | hub: " + ($hub -join ", ") + " | " + $run.url)
            } else { Set-Lane -Name "brand-verify" -State "UNAVAILABLE" -Detail "run not found yet; check Actions" }
        }
        if ($Lanes.Contains("david") -and $Lanes["david"].state -eq "DISPATCHED") {
            Start-Sleep -Seconds 10
            $run = Get-LatestRun -Repo "szl-holdings/david-leads" -Workflow "rotate-space-credentials.yml"
            if ($run) { Set-Lane -Name "david-verify" -State ("RUN_" + ([string]$run.status).ToUpper()) -Detail ($run.url + " - if it shows 'waiting', approve the environment deployment there; the next live-lanes canary should turn green"); Start-Process ([string]$run.url) }
        }
        if ($Lanes.Contains("edge") -and $Lanes["edge"].state -eq "DISPATCHED") {
            Start-Sleep -Seconds 10
            $run = Get-LatestRun -Repo "szl-holdings/a11oy" -Workflow "repair-cloudflare-product-edge-production.yml"
            if ($run) { Set-Lane -Name "edge-verify" -State ("RUN_" + ([string]$run.status).ToUpper()) -Detail ($run.url + " - approve the production environment if GitHub asks; receipt status must not read UNAVAILABLE"); Start-Process ([string]$run.url) }
        }
    } catch { Fail-Lane -Name "verify" -Err $_ }

    # ================================================================ receipt and summary
    $receipt = [ordered]@{
        schema = "szl.owner-master-runbook/v1"; started_utc = $StartedUtc.ToString("o"); finished_utc = [DateTime]::UtcNow.ToString("o")
        machine = $env:COMPUTERNAME; user = $env:USERNAME; frontier_pin = $FrontierPin; brand_pin = $BrandPin
        secrets_recorded = $false; lanes = $Lanes
        remaining_owner_decisions = @(
            "Nemo v3 signing ceremony: szl-gpu-bridge #93 / #20 (enrolled laptop key; not automated here)",
            "Org code scanning default setup (.github #523 / #586): deliberate org-settings change, not automated here",
            "Private Spaces visibility: hatun-mcp, nexus, szl-real-estate, vessels (decision, not credential)",
            "Public copy taxonomy: carry the profile direction to the Hub card and index.html, or restore the taxonomy (receipt session 9)"
        )
    }
    $receiptPath = Join-Path $Root ("receipts\owner-master-" + $Stamp + ".json")
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
    Write-Host ""
    Write-Host "== SUMMARY =="
    foreach ($k in $Lanes.Keys) { Write-Host (("  {0,-13} {1,-15} {2}" -f $k, $Lanes[$k].state, $Lanes[$k].detail)) }
    Write-Host ("  receipt: " + $receiptPath)
    Write-Host ("  transcript: " + (Join-Path $Root ("logs\owner-master-" + $Stamp + ".log")))
    $failed = @($Lanes.Keys | Where-Object { $Lanes[$_].state -eq "FAILED" -or $Lanes[$_].state -eq "NOT_CONVERGED" })
    if ($failed.Count -gt 0) { Write-Host ("RUN INCOMPLETE - failed lanes: " + ($failed -join ", ")); $script:ExitCode = 1 } else { Write-Host "RUN COMPLETE - every lane is DONE, DISPATCHED, OWNER_ATTESTED, SKIPPED or UNAVAILABLE as printed above"; $script:ExitCode = 0 }
}
finally {
    Stop-Transcript | Out-Null
}
exit $script:ExitCode
