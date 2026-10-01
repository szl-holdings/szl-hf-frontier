# SZL CLOSEOUT v5 2026-10-01 — one paste, administrator PowerShell 5.1, no prior shell state.
# 1 reclaims disk (Docker build cache + dangling images, Docker VHDX compaction, reduced hiberfil), 2 sizes the pagefile,
# 3-4 take the two tokens (MASKED, patient: copy in the browser FIRST, come back, right-click or press Enter; the clipboard
# is wiped after every read), 5 runs the DPO lane WSL-first from the estate's qualified szl-unsloth venv (profile C3).
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$env:HF_HUB_DISABLE_PROGRESS_BARS = "1"

$Root = Join-Path $env:USERPROFILE "szl"
New-Item -ItemType Directory -Force -Path $Root | Out-Null
Set-Location -LiteralPath $Root
$Stamp = Get-Date -Format "yyyyMMdd-HHmm"
$Status = [ordered]@{}
$Receipt = Join-Path $Root ("closeout-" + $Stamp + ".json")

function Get-Plain([System.Security.SecureString]$Secure) {
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}
function Clear-ClipboardQuietly { try { Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::Clear() } catch { } }
function Get-SecretInput([string]$What, [scriptblock]$Validate) {
    $try = 0
    while ($true) {
        $try++
        $sec = Read-Host ("    " + $What + " -> copy it in the browser, come back, then right-click here (hidden) or just press Enter  [attempt " + $try + "; type skip to give up]") -AsSecureString
        $typed = Get-Plain $sec
        if ($typed.Trim().ToLower() -eq "skip") { return $null }
        $tok = ($typed -replace "[^\x21-\x7E]", "")
        if ($tok.Length -lt 20) {
            $raw = ""
            try { $raw = [string](Get-Clipboard -Raw) } catch { $raw = "" }
            $tok = ($raw -replace "[^\x21-\x7E]", "")
        }
        Clear-ClipboardQuietly
        if ($tok.Length -lt 20) { Write-Host "    nothing was pasted and the clipboard held no token. Copy the token in the browser FIRST, then press Enter here."; continue }
        $why = & $Validate $tok
        if ([string]::IsNullOrEmpty($why)) { return $tok }
        Write-Host ("    REJECTED: " + $why)
        Write-Host "    Fix it in the browser, copy the NEW token, then press Enter here (the clipboard was wiped)."
    }
}
function Get-RunState([string]$Repo, [int64]$RunId) {
    $j = & gh api ("repos/" + $Repo + "/actions/runs/" + $RunId)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($j -join ""))) { throw ("cannot read run " + $RunId + " in " + $Repo) }
    $o = ($j -join "") | ConvertFrom-Json
    return [pscustomobject]@{ status = [string]$o.status; conclusion = [string]$o.conclusion }
}
function Get-NewestRunId([string]$Repo, [string]$Workflow) {
    $j = & gh run list --repo $Repo --workflow $Workflow --limit 1 --json databaseId
    if ([string]::IsNullOrWhiteSpace(($j -join ""))) { return [int64]0 }
    $a = @(($j -join "") | ConvertFrom-Json); if ($a.Count -eq 0) { return [int64]0 }; return [int64]$a[0].databaseId
}
function Invoke-Dispatch([string]$Repo, [string]$Workflow, [string[]]$Fields) {
    $before = Get-NewestRunId $Repo $Workflow
    if ($Fields.Count -gt 0) { & gh workflow run $Workflow --repo $Repo --ref main @Fields | Out-Null } else { & gh workflow run $Workflow --repo $Repo --ref main | Out-Null }
    if ($LASTEXITCODE -ne 0) { throw ("dispatch failed: " + $Repo + " " + $Workflow) }
    for ($i = 0; $i -lt 24; $i++) {
        Start-Sleep -Seconds 10
        $now = Get-NewestRunId $Repo $Workflow
        if ($now -ne 0 -and $now -ne $before) { return $now }
    }
    throw ("dispatched " + $Workflow + " but no new run appeared")
}
function Approve-Deployment([string]$Repo, [int64]$RunId) {
    $j = & gh api ("repos/" + $Repo + "/actions/runs/" + $RunId + "/pending_deployments")
    if ([string]::IsNullOrWhiteSpace(($j -join ""))) { return "nothing-pending" }
    $pending = @(($j -join "") | ConvertFrom-Json); if ($pending.Count -eq 0) { return "nothing-pending" }
    $names = @()
    foreach ($p in $pending) {
        if (-not $p.current_user_can_approve) { throw ("this account cannot approve environment " + $p.environment.name) }
        & gh api -X POST ("repos/" + $Repo + "/actions/runs/" + $RunId + "/pending_deployments") -F ("environment_ids[]=" + $p.environment.id) -f state=approved -f comment="Owner approval from the SZL closeout block 2026-10-01." | Out-Null
        if ($LASTEXITCODE -ne 0) { throw ("approval failed for " + $p.environment.name) }
        $names += $p.environment.name
    }
    return ("approved:" + ($names -join ","))
}
function Wait-GhRun([string]$Repo, [int64]$RunId, [int]$Minutes) {
    $deadline = (Get-Date).AddMinutes($Minutes)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 20
        $r = Get-RunState $Repo $RunId
        if ($r.status -eq "completed") { return $r.conclusion }
        if ($r.status -eq "waiting") { return "waiting" }
    }
    return "timeout"
}
function Wait-ThroughApproval([string]$Repo, [int64]$RunId, [int]$Minutes) {
    $state = Wait-GhRun $Repo $RunId $Minutes
    if ($state -eq "waiting") { Write-Host ("      " + (Approve-Deployment $Repo $RunId)); $state = Wait-GhRun $Repo $RunId $Minutes }
    return $state
}
function Show-DpoReceipt([string]$Path) {
    try {
        $j = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        $reason = ""; if ($j.PSObject.Properties["reason"]) { $reason = [string]$j.reason }
        Write-Host ("    " + (Split-Path (Split-Path $Path -Parent) -Leaf) + " : " + [string]$j.status + " " + $reason)
        if ($j.PSObject.Properties["memory_profile"]) {
            $mp = $j.memory_profile
            if ($mp.PSObject.Properties["prompt_tokens"]) { Write-Host ("      prompt tokens max=" + $mp.prompt_tokens.max + " mean=" + $mp.prompt_tokens.mean + " ; completion tokens max=" + $mp.completion_tokens_max) }
            if ($mp.PSObject.Properties["attempts_before_fit"]) {
                foreach ($a in @($mp.attempts_before_fit)) {
                    $peak = [math]::Round(([double]$a.peak_allocated_bytes) / 1GB, 2)
                    $msg = [string]$a.message; if ($msg.Length -gt 260) { $msg = $msg.Substring(0, 260) }
                    Write-Host ("      max_length=" + $a.max_length + " peak_alloc=" + $peak + " GiB : " + $msg)
                }
            }
        }
    } catch { Write-Host ("    could not read " + $Path + ": " + $_.Exception.Message) }
}

# ---- 0. preflight ----
try {
    if (-not (Get-Command gh.exe -ErrorAction SilentlyContinue)) {
        winget install --id GitHub.cli -e --accept-source-agreements --accept-package-agreements
        throw "GitHub CLI was just installed: open a NEW administrator PowerShell window and paste this block again."
    }
    & gh auth status --hostname github.com 2>$null
    if ($LASTEXITCODE -ne 0) { & gh auth login --hostname github.com --web --git-protocol https --scopes "repo,workflow"; if ($LASTEXITCODE -ne 0) { throw "gh login failed" } }
    $Me = ((& gh api user) -join "") | ConvertFrom-Json
    Write-Host ("[0] gh ready as " + $Me.login + " | root " + $Root)
    $Status["0-preflight"] = "OK as " + $Me.login
} catch { $Status["0-preflight"] = "FAILED: " + $_.Exception.Message; Write-Host $Status["0-preflight"] }

# ---- 1. disk: reclaim what is only cache, report what is not ----
try {
    function Get-FreeGB { return [math]::Round((Get-PSDrive C).Free / 1GB, 2) }
    function Compact-Vhdx([string]$Path) {
        $script = Join-Path $env:TEMP ("szl-compact-" + [guid]::NewGuid().ToString("N") + ".txt")
        @(("select vdisk file=`"" + $Path + "`""), "attach vdisk readonly", "compact vdisk", "detach vdisk") | Set-Content -LiteralPath $script -Encoding Ascii
        $prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        try { $out = & diskpart.exe /s $script 2>&1 } finally { $ErrorActionPreference = $prevEap; Remove-Item -LiteralPath $script -Force -ErrorAction SilentlyContinue }
        return (($out -join " ") -replace "\s+", " ")
    }
    $freeStart = Get-FreeGB
    Write-Host ("[1] C: free before: " + $freeStart + " GB")
    $dockerNote = "docker cli absent"
    if (Get-Command docker.exe -ErrorAction SilentlyContinue) {
        $prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        try {
            $null = & docker.exe info 2>$null
            if ($LASTEXITCODE -ne 0) {
                $dd = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
                if (Test-Path -LiteralPath $dd) {
                    Start-Process -FilePath $dd | Out-Null
                    for ($i = 0; $i -lt 18; $i++) { Start-Sleep -Seconds 10; $null = & docker.exe info 2>$null; if ($LASTEXITCODE -eq 0) { break } }
                }
            }
            $null = & docker.exe info 2>$null
            if ($LASTEXITCODE -eq 0) {
                $b = (& docker.exe builder prune -af 2>&1) -join " "
                $im = (& docker.exe image prune -f 2>&1) -join " "
                $dockerNote = ("build cache: " + (($b -split "Total")[-1]).Trim() + " | dangling images: " + (($im -split "Total")[-1]).Trim())
                Write-Host ("    docker pruned (build cache + dangling images only; tagged images and volumes untouched): " + $dockerNote)
                Get-Process -Name "Docker Desktop", "com.docker.backend", "com.docker.build" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 5
            } else { $dockerNote = "docker engine not reachable; prune skipped" }
        } finally { $ErrorActionPreference = $prevEap }
    }
    if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
        $prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        try { & wsl.exe --shutdown 2>$null } finally { $ErrorActionPreference = $prevEap }
        Start-Sleep -Seconds 3
    }
    $vhdxRoot = Join-Path $env:LOCALAPPDATA "Docker\wsl"
    if (Test-Path -LiteralPath $vhdxRoot) {
        foreach ($v in Get-ChildItem -LiteralPath $vhdxRoot -Recurse -Filter *.vhdx -ErrorAction SilentlyContinue) {
            $beforeMB = [math]::Round($v.Length / 1MB)
            $res = Compact-Vhdx $v.FullName
            $afterMB = [math]::Round((Get-Item -LiteralPath $v.FullName).Length / 1MB)
            Write-Host ("    compacted " + $v.Name + ": " + $beforeMB + " MB -> " + $afterMB + " MB" + $(if ($res -match "successfully") { "" } else { " (diskpart: " + $res.Substring(0, [math]::Min(140, $res.Length)) + ")" }))
        }
    }
    foreach ($v in Get-ChildItem -LiteralPath (Join-Path $env:LOCALAPPDATA "Packages") -Recurse -Depth 2 -Filter ext4.vhdx -ErrorAction SilentlyContinue) {
        Write-Host ("    WSL distro disk (REPORT ONLY, not compacted): " + $v.FullName + " = " + [math]::Round($v.Length / 1GB, 1) + " GB")
    }
    $hib = Get-Item -LiteralPath "C:\hiberfil.sys" -Force -ErrorAction SilentlyContinue
    if ($hib) {
        $hb = [math]::Round($hib.Length / 1GB, 1)
        $prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        try { $null = & powercfg.exe /hibernate /type reduced 2>&1 } finally { $ErrorActionPreference = $prevEap }
        $hib2 = Get-Item -LiteralPath "C:\hiberfil.sys" -Force -ErrorAction SilentlyContinue
        $ha = $(if ($hib2) { [math]::Round($hib2.Length / 1GB, 1) } else { 0 })
        Write-Host ("    hiberfil.sys: " + $hb + " GB -> " + $ha + " GB (reduced type keeps fast startup; 'powercfg /h /type full' reverts)")
    }
    $freeEnd = Get-FreeGB
    $Status["1-disk"] = "C: " + $freeStart + " GB -> " + $freeEnd + " GB free; " + $dockerNote
    Write-Host ("    C: free after: " + $freeEnd + " GB")
} catch { $Status["1-disk"] = "FAILED: " + $_.Exception.Message; Write-Host $Status["1-disk"] }

# ---- 2. pagefile: sized to what C: can carry (active after the next reboot) ----
try {
    $freeC = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
    $os = Get-CimInstance Win32_OperatingSystem
    $commit = ([string][math]::Round(($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1MB, 1)) + " / " + ([string][math]::Round($os.TotalVirtualMemorySize / 1MB, 1)) + " GB"
    if ($freeC -ge 18) { $pfInit = 12288; $pfMax = 16384 } elseif ($freeC -ge 14) { $pfInit = 8192; $pfMax = 12288 } else { $pfInit = 0; $pfMax = 0 }
    if ($pfInit -eq 0) {
        $Status["2-pagefile"] = "SKIPPED: C: has " + $freeC + " GB free (<14); commit now " + $commit
    } else {
        $cs = Get-CimInstance Win32_ComputerSystem
        if ($cs.AutomaticManagedPagefile) { Set-CimInstance -InputObject $cs -Property @{ AutomaticManagedPagefile = $false } | Out-Null }
        $pf = Get-CimInstance Win32_PageFileSetting -Filter "Name='C:\\pagefile.sys'" -ErrorAction SilentlyContinue
        if ($pf) { Set-CimInstance -InputObject $pf -Property @{ InitialSize = $pfInit; MaximumSize = $pfMax } | Out-Null }
        else { New-CimInstance -ClassName Win32_PageFileSetting -Property @{ Name = "C:\pagefile.sys"; InitialSize = $pfInit; MaximumSize = $pfMax } | Out-Null }
        $Status["2-pagefile"] = "set " + $pfInit + "/" + $pfMax + " MB (was 3739 MB; active after reboot); commit now " + $commit
    }
    Write-Host ("[2] " + $Status["2-pagefile"])
} catch { $Status["2-pagefile"] = "FAILED: " + $_.Exception.Message; Write-Host $Status["2-pagefile"] }

# ---- router readback: root cause recorded, nothing to approve (Space attests szl-router 0b6a90ec; main is dfb94389; deploy is path-filtered) ----
$Status["router-review"] = "run 36803151644 completed failure = Space bound to szl-router 0b6a90ec while main is dfb94389; owner decision pending (gate vs deploy path); no action in this block"
Write-Host ("[r] " + $Status["router-review"])

# ---- 3. David dataset reader token (FINE-GRAINED, read-only) -> environment secret -> rotation (approved) -> canary ----
try {
    $Dataset = "SZLHOLDINGS/david-leads-data"
    Write-Host "[3] Hugging Face token page opens. On 'Create new Access Token' the FIRST control is 'Token type' with three choices: Fine-grained / Read / Write."
    Write-Host "    Choose FINE-GRAINED (the two tokens you made tonight were 'Write' and were rejected; revoke them while you are there)."
    Write-Host "    Name: david-dataset-reader. Scroll to 'Repositories': tick ONLY 'Read access to contents of selected repos' and add $Dataset."
    Write-Host "    Leave every other box unticked. Click 'Create token', click 'Copy', then come back here and press Enter."
    Start-Process "https://huggingface.co/settings/tokens/new?tokenType=fineGrained"
    $hfValidate = {
        param($t)
        try {
            if (-not $t.StartsWith("hf_")) { return "not a Hugging Face token (must start with hf_)" }
            $h = @{ Authorization = ("Bearer " + $t) }
            $who = Invoke-RestMethod -UseBasicParsing -Uri "https://huggingface.co/api/whoami-v2" -Headers $h
            $role = [string]$who.auth.accessToken.role
            if (($role -replace "[^a-zA-Z]", "").ToLower() -ne "finegrained") { return ("token type is '" + $role + "'. Pick FINE-GRAINED under 'Token type' (top of the create page), not Read or Write. Revoke this '" + $role + "' token.") }
            $ds = Invoke-RestMethod -UseBasicParsing -Uri ("https://huggingface.co/api/datasets/" + $Dataset) -Headers $h
            if (-not $ds.sha) { return ("token cannot read " + $Dataset + " - add it under 'Read access to contents of selected repos'") }
            Write-Host ("    token OK: " + $who.name + " | " + $role + " | dataset @ " + $ds.sha.Substring(0, 10))
            return ""
        } catch { return ("validation call failed: " + $_.Exception.Message) }
    }
    $plain = Get-SecretInput "fine-grained Hugging Face token" $hfValidate
    if ($null -eq $plain) { throw "skipped by owner; rotation not run" }
    try {
        $plain | & gh secret set DAVID_DATASET_READ_TOKEN --repo szl-holdings/david-leads --env david-space-credential-rotation
        if ($LASTEXITCODE -ne 0) { throw "gh secret set failed (needs admin on david-leads)" }
    } finally { $plain = $null; [GC]::Collect() }
    Write-Host "    secret stored: david-leads -> david-space-credential-rotation -> DAVID_DATASET_READ_TOKEN"
    $rot = Invoke-Dispatch "szl-holdings/david-leads" "rotate-space-credentials.yml" @()
    Write-Host ("    rotation run " + $rot + " dispatched; waiting for the environment gate")
    $rotState = Wait-ThroughApproval "szl-holdings/david-leads" $rot 25
    Write-Host ("    rotation: " + $rotState)
    $can = Invoke-Dispatch "szl-holdings/david-leads" "frontier-live-canary.yml" @()
    $canState = Wait-GhRun "szl-holdings/david-leads" $can 15
    Write-Host ("    canary run " + $can + ": " + $canState)
    $Status["3-david-reader"] = "secret set; rotation " + $rot + "=" + $rotState + "; canary " + $can + "=" + $canState
} catch { $Status["3-david-reader"] = "FAILED: " + $_.Exception.Message; Write-Host $Status["3-david-reader"] }

# ---- 4. Cloudflare: new token with all four permissions -> replace the exposed secret -> edge repair ----
try {
    Write-Host "[4] Cloudflare API Tokens page opens. Delete the exposed token (prefix cfut_SIXu) and tonight's incomplete one if it is still listed."
    Write-Host "    'Create Token' -> 'Create Custom Token' -> add FOUR permission rows:"
    Write-Host "      Account | Workers Scripts | Edit        Account Resources: Include -> your account"
    Write-Host "      Zone    | Workers Routes  | Edit        Zone Resources: Include -> Specific zone -> a-11-oy.com, then add a11oy.net (or All zones)"
    Write-Host "      Zone    | DNS             | Edit"
    Write-Host "      Zone    | Zone            | Read"
    Write-Host "    'Continue to summary' -> 'Create Token' -> 'Copy', then come back here and press Enter."
    Start-Process "https://dash.cloudflare.com/profile/api-tokens"
    $cfValidate = {
        param($t)
        $h = @{ Authorization = ("Bearer " + $t) }
        try {
            $v = Invoke-RestMethod -UseBasicParsing -Uri "https://api.cloudflare.com/client/v4/user/tokens/verify" -Headers $h
            if ($v.success -ne $true -or $v.result.status -ne "active") { return "Cloudflare did not report the token as active" }
        } catch { return ("token verify failed: " + $_.Exception.Message) }
        $acct = ""
        foreach ($z in @("a-11-oy.com", "a11oy.net")) {
            try {
                $zr = Invoke-RestMethod -UseBasicParsing -Uri ("https://api.cloudflare.com/client/v4/zones?name=" + $z + "&status=active") -Headers $h
                if ($zr.success -ne $true -or @($zr.result).Count -ne 1) { return ("Zone > Zone > Read is missing for " + $z + " (Zone Resources must include it)") }
                $zid = $zr.result[0].id; $acct = [string]$zr.result[0].account.id
            } catch { return ("zone lookup failed for " + $z + ": " + $_.Exception.Message) }
            try { $null = Invoke-RestMethod -UseBasicParsing -Uri ("https://api.cloudflare.com/client/v4/zones/" + $zid + "/dns_records?per_page=1") -Headers $h } catch { return ("Zone > DNS > Edit is missing for " + $z) }
            try { $null = Invoke-RestMethod -UseBasicParsing -Uri ("https://api.cloudflare.com/client/v4/zones/" + $zid + "/workers/routes") -Headers $h } catch { return ("Zone > Workers Routes > Edit is missing for " + $z + " (this is exactly what blocked run 36810260940)") }
        }
        try { $null = Invoke-RestMethod -UseBasicParsing -Uri ("https://api.cloudflare.com/client/v4/accounts/" + $acct + "/workers/scripts") -Headers $h } catch { return "Account > Workers Scripts > Edit is missing (Account Resources must include your account)" }
        Write-Host "    token OK: active; both zones, DNS, Workers Routes and Workers Scripts all readable"
        return ""
    }
    $plain = Get-SecretInput "NEW Cloudflare API token" $cfValidate
    if ($null -eq $plain) { throw "skipped by owner (the exposed token stays in the a11oy production secret until replaced)" }
    try {
        $plain | & gh secret set CLOUDFLARE_API_TOKEN --repo szl-holdings/a11oy --env production
        if ($LASTEXITCODE -ne 0) { throw "gh secret set failed (needs admin on a11oy)" }
    } finally { $plain = $null; [GC]::Collect() }
    Write-Host "    secret replaced: a11oy -> production -> CLOUDFLARE_API_TOKEN"
    $edge = Invoke-Dispatch "szl-holdings/a11oy" "repair-cloudflare-product-edge-production.yml" @("-f", "dry_run=false")
    $edgeState = Wait-ThroughApproval "szl-holdings/a11oy" $edge 30
    $edgeDir = Join-Path $Root ("edge-receipt-" + $Stamp)
    & gh run download $edge --repo szl-holdings/a11oy -D $edgeDir 2>$null
    $edgeNote = ""
    if (Test-Path -LiteralPath $edgeDir) {
        foreach ($f in Get-ChildItem -LiteralPath $edgeDir -Recurse -Filter *.json) {
            $j = Get-Content -LiteralPath $f.FullName -Raw | ConvertFrom-Json
            $st = ""; $er = ""
            if ($j.PSObject.Properties["status"]) { $st = [string]$j.status }
            if ($j.PSObject.Properties["error"]) { $er = [string]$j.error }
            $edgeNote += (" " + $f.Name + ": status=" + $st)
            if ($er) { $edgeNote += (" error=" + $er) }
        }
    }
    foreach ($u in @("https://a-11-oy.com/", "https://a-11-oy.com/spectral", "https://a-11-oy.com/controller")) {
        $code = "ERR"
        try { $code = (Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop).StatusCode } catch { if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode } }
        Write-Host ("    probe " + $u + " -> " + $code)
    }
    $Status["4-cloudflare"] = "secret replaced; edge run " + $edge + "=" + $edgeState + ";" + $edgeNote
    Write-Host ("    edge repair: " + $Status["4-cloudflare"])
} catch { $Status["4-cloudflare"] = "FAILED: " + $_.Exception.Message; Write-Host $Status["4-cloudflare"] }

# ---- WO6: closed by owner at 2026-09-30T23:47:40 (hf_nGHC, hf_rpzm, hf_BOUr revoked) ----
$Status["wo6"] = "closed 2026-09-30T23:47:40 (owner confirmed revocation of hf_nGHC, hf_rpzm, hf_BOUr)"
Write-Host ("[w] " + $Status["wo6"])

# ---- 5. DPO lane: earlier receipts for the record, then the re-pinned runbook (WSL-first, profile C3) -> bundle -> PR ----
try {
    Write-Host "[5] earlier receipts in this folder (for the record):"
    foreach ($d in Get-ChildItem -LiteralPath $Root -Directory -Filter "dpo-khipu-r4-challenger-*" | Sort-Object Name) {
        $rp = Join-Path $d.FullName "dpo_receipt.json"
        if (Test-Path -LiteralPath $rp) { Show-DpoReceipt $rp }
    }
    $RbPin  = "738d359b7ba59ee17db242adb1b03d82b6929407"
    $RbWant = "51880728d7fff28e95b026d2cd38b4fbcf8833a338d71e0073d02a026d948868"
    $RbPath = Join-Path $Root "SZL-KHIPU-DPO-RUNBOOK.ps1"
    $b64 = ((& gh api ("repos/szl-holdings/szl-hf-frontier/contents/payloads/runbooks/SZL-KHIPU-DPO-RUNBOOK.ps1?ref=" + $RbPin) --jq .content) -join "")
    [IO.File]::WriteAllBytes($RbPath, [Convert]::FromBase64String($b64))
    $got = (Get-FileHash -LiteralPath $RbPath -Algorithm SHA256).Hash.ToLower()
    if ($got -ne $RbWant) { throw ("runbook hash mismatch: got " + $got) }
    Write-Host ("    runbook OK sha256=" + $got + " ; starting the GPU lane (WSL szl-unsloth venv if present, else Windows python; profile C3; fails closed without CUDA)")
    $before = @(Get-ChildItem -LiteralPath $Root -Directory -Filter "bundle-*" | ForEach-Object { $_.Name })
    $beforeReceipts = @(Get-ChildItem -LiteralPath $Root -Directory -Filter "dpo-khipu-r4-challenger-*" | ForEach-Object { $_.Name })
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $RbPath
    $rbExit = $LASTEXITCODE
    if ($rbExit -ne 0) {
        Write-Host "    runbook stopped; new receipt:"
        foreach ($d in Get-ChildItem -LiteralPath $Root -Directory -Filter "dpo-khipu-r4-challenger-*" | Where-Object { $beforeReceipts -notcontains $_.Name }) {
            $rp = Join-Path $d.FullName "dpo_receipt.json"
            if (Test-Path -LiteralPath $rp) { Show-DpoReceipt $rp }
        }
        throw "runbook stopped before completion (receipt summary printed above); nothing was staged"
    }
    $bundleRoot = Get-ChildItem -LiteralPath $Root -Directory -Filter "bundle-*" | Where-Object { $before -notcontains $_.Name } | Sort-Object Name | Select-Object -Last 1
    if (-not $bundleRoot) { throw "runbook finished but no new bundle-<stamp> directory exists" }
    $bundleDir = Get-ChildItem -LiteralPath (Join-Path $bundleRoot.FullName "receipts\khipu-abstain") -Directory | Select-Object -First 1
    $runId = $bundleDir.Name
    Write-Host ("    bundle " + $runId + " at " + $bundleDir.FullName)
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw ("git is not installed; hand back " + $bundleDir.FullName + " manually") }
    $work = Join-Path $Root ("szl-forge-" + $Stamp)
    & gh repo clone szl-holdings/szl-forge $work -- --depth 1 --branch huggingface --quiet
    if ($LASTEXITCODE -ne 0) { throw "clone of szl-forge failed" }
    $dest = Join-Path $work ("receipts\khipu-abstain\" + $runId)
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    Copy-Item -LiteralPath $bundleDir.FullName -Destination $dest -Recurse
    $branch = "receipts/khipu-abstain-" + $runId
    $email = ($Me.id.ToString() + "+" + $Me.login + "@users.noreply.github.com")
    & git -C $work checkout -q -b $branch
    & git -C $work add -A receipts/khipu-abstain
    & git -C $work -c user.name=$Me.login -c user.email=$email commit -q -m ("receipts(khipu-abstain): evidence bundle " + $runId + " (NOT_PROMOTABLE; derived state block)")
    if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
    & git -C $work push -q -u origin $branch
    if ($LASTEXITCODE -ne 0) { throw "git push failed" }
    $statusMd = Get-Content -LiteralPath (Join-Path $bundleDir.FullName "STATUS.md") -Raw
    $body = "Immutable evidence bundle staged by tools/ingest_khipu_abstain_receipts.py on the owner laptop and re-validated before commit. Publication stays false; promotion stays NOT_PROMOTABLE until the canonical Forge gate says otherwise.`n`n" + $statusMd
    $prUrl = & gh pr create --repo szl-holdings/szl-forge --base huggingface --head $branch --title ("receipts(khipu-abstain): evidence bundle " + $runId) --body $body
    if ($LASTEXITCODE -ne 0) { throw "gh pr create failed (branch is pushed; open the PR by hand)" }
    $Status["5-dpo-bundle"] = "bundle " + $runId + " -> " + $prUrl
    Write-Host ("    PR opened: " + $prUrl)
} catch { $Status["5-dpo-bundle"] = "FAILED: " + $_.Exception.Message; Write-Host $Status["5-dpo-bundle"] }

# ---- summary (no secret values anywhere in this file) ----
$Status | ConvertTo-Json | Set-Content -LiteralPath $Receipt -Encoding UTF8
Write-Host ""
Write-Host "=== SZL CLOSEOUT SUMMARY (paste this back with the [5] lane lines; reboot afterwards so the pagefile takes effect) ==="
foreach ($k in $Status.Keys) { Write-Host ($k + " : " + $Status[$k]) }
Write-Host ("receipt: " + $Receipt)
