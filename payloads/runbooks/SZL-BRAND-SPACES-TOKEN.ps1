# SZL brand Spaces publisher token - one paste, administrator PowerShell 5.1, no prior shell state.
# Why: szl-brand's repository secret HF_TOKEN is rejected by Hugging Face (/whoami-v2 -> 400 Bad request),
# so hf-marketing-spaces.yml fails closed and the two public marketing Spaces stay on their stale bytes.
# What it does: opens the fine-grained token page, reads the token from the clipboard (you click Copy in the browser,
# then press Enter here; nothing is typed or pasted into the console), proves the token
# is fine-grained and carries repo.write on exactly the two Spaces (or on the SZLHOLDINGS org), stores it as
# the repository secret HF_TOKEN on szl-holdings/szl-brand, and dispatches the exact-projection workflow.
# The token never appears in the transcript, in an argument, or in this file; the clipboard is overwritten afterwards.
# Does not change: any other secret, the Spaces' current bytes (the workflow writes them, with a receipt),
# GitHub branches.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Repo     = "szl-holdings/szl-brand"
$Workflow = "hf-marketing-spaces.yml"
$Spaces   = @("SZLHOLDINGS/szl-marketing-1.1", "SZLHOLDINGS/szl-brand-campaign")

$gh = Get-Command gh.exe -ErrorAction SilentlyContinue
if (-not $gh) { throw "GitHub CLI (gh) is required: winget install --id GitHub.cli, open a new window, rerun." }
& gh auth status --hostname github.com 2>$null
if ($LASTEXITCODE -ne 0) { & gh auth login --hostname github.com --web --git-protocol https --scopes "repo,workflow" }

Write-Host "1) In the browser tab that opens, create a FINE-GRAINED token:"
Write-Host "   name: szl-brand-spaces-publisher"
Write-Host "   Repositories -> select the two Spaces below and tick 'Write access to contents/settings of selected repos'"
foreach ($s in $Spaces) { Write-Host ("     - " + $s) }
Write-Host "   leave inference, org-admin, billing and every other box unticked"
Start-Process "https://huggingface.co/settings/tokens/new?tokenType=fineGrained"

# Clipboard route: nothing is typed or pasted into this window. Click the token's Copy button in the
# browser, come back here, press Enter. The script reads the clipboard, validates the shape, and
# overwrites the clipboard when it is done so the token does not linger there.
$plain = $null
for ($attempt = 1; $attempt -le 3; $attempt++) {
    [void](Read-Host "2) Click the token's COPY button in the browser, then press Enter here (type nothing)")
    $clip = ""
    try { $clip = [string](Get-Clipboard -Raw) } catch { $clip = "" }
    $clip = $clip.Trim()
    if ($clip.StartsWith("hf_") -and $clip.Length -ge 20 -and $clip -notmatch "\s") { $plain = $clip; break }
    Write-Host ("   clipboard does not hold a token (got " + $clip.Length + " chars). Copy the token again - attempt " + $attempt + " of 3.")
}
if (-not $plain) { throw "No Hugging Face token found on the clipboard after 3 attempts. Nothing was stored or dispatched." }
Set-Clipboard -Value "cleared"

try {
    $headers = @{ Authorization = ("Bearer " + $plain) }
    $who = Invoke-RestMethod -UseBasicParsing -Uri "https://huggingface.co/api/whoami-v2" -Headers $headers
    $role = [string]$who.auth.accessToken.role
    if (($role -replace "[^a-zA-Z]", "").ToLower() -ne "finegrained") { throw ("Token role is '" + $role + "', not fine-grained. Mint a fine-grained token.") }

    # Prove repo.write on each Space (or on the whole SZLHOLDINGS org) from the token's own scope list.
    $fg = $who.auth.accessToken.fineGrained
    $scoped = @()
    if ($fg -and $fg.PSObject.Properties["scoped"]) { $scoped = @($fg.scoped) }
    foreach ($s in $Spaces) {
        $ok = $false
        foreach ($entry in $scoped) {
            $name = ""
            if ($entry.PSObject.Properties["entity"] -and $entry.entity.PSObject.Properties["name"]) { $name = [string]$entry.entity.name }
            $perms = @()
            if ($entry.PSObject.Properties["permissions"]) { $perms = @($entry.permissions) }
            if (($name -eq $s -or $name -eq "SZLHOLDINGS") -and ($perms -contains "repo.write")) { $ok = $true }
        }
        if (-not $ok) { throw ("Token has no repo.write on " + $s + ". Add that Space (write) under the token's repository access.") }
        $meta = Invoke-RestMethod -UseBasicParsing -Uri ("https://huggingface.co/api/spaces/" + $s) -Headers $headers
        Write-Host ("   write scope OK: " + $s + " (current revision " + ([string]$meta.sha).Substring(0, 10) + ")")
    }
    Write-Host ("3) token OK: identity " + $who.name + " | role " + $role)

    $plain | & gh secret set HF_TOKEN --repo $Repo
    if ($LASTEXITCODE -ne 0) { throw "gh secret set failed (needs admin on the repository)." }
    Write-Host ("4) secret stored: " + $Repo + " -> HF_TOKEN")
}
finally {
    $plain = $null
    $headers = $null
    [GC]::Collect()
}

& gh workflow run $Workflow --repo $Repo --ref main -f confirmation=PUBLISH-SZL-MARKETING-SPACES -f target=all
if ($LASTEXITCODE -ne 0) { throw "workflow dispatch failed" }
Start-Sleep -Seconds 20
& gh run list --repo $Repo --workflow $Workflow --limit 1
Write-Host "5) Projection dispatched. Success = job 'hf-marketing-spaces/publish-exact' green and both reports/spaces/*-publish.json in the run artifact say PUBLISHED_CONVERGED."
Write-Host "   Verify from any browser: https://huggingface.co/spaces/SZLHOLDINGS/szl-brand-campaign (live labeled numbers, no template text)"
Write-Host "                            https://huggingface.co/spaces/SZLHOLDINGS/szl-marketing-1.1 (Operating plan + Provenance tabs present)"
