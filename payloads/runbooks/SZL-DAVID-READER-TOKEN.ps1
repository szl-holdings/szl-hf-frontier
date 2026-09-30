# SZL David dataset reader token - one paste, administrator PowerShell 5.1, no prior shell state.
# What it does: opens the Hugging Face fine-grained token page, takes the token through a hidden prompt,
# proves it is fine-grained and can read the private dataset (the same two checks the rotation workflow
# makes), stores it as the environment secret DAVID_DATASET_READ_TOKEN on david-leads, and dispatches
# the rotation. The token never appears in the transcript, in an argument, or in this file.
# Does not change: any other secret, the Space, the dataset, GitHub branches.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Repo     = "szl-holdings/david-leads"
$EnvName  = "david-space-credential-rotation"
$Dataset  = "SZLHOLDINGS/david-leads-data"
$Workflow = "rotate-space-credentials.yml"

$gh = Get-Command gh.exe -ErrorAction SilentlyContinue
if (-not $gh) { throw "GitHub CLI (gh) is required: winget install --id GitHub.cli, open a new window, rerun." }
& gh auth status --hostname github.com 2>$null
if ($LASTEXITCODE -ne 0) { & gh auth login --hostname github.com --web --git-protocol https --scopes "repo,workflow" }

Write-Host "1) In the browser tab that opens, create a FINE-GRAINED token:"
Write-Host "   name: david-dataset-reader"
Write-Host "   Repositories -> tick ONLY 'Read access to contents of selected repos' and select dataset $Dataset"
Write-Host "   leave every write, inference, org-admin and billing box unticked"
Start-Process "https://huggingface.co/settings/tokens/new?tokenType=fineGrained"

$secure = Read-Host "2) Paste the token once (input is hidden)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
if (-not $plain -or -not $plain.StartsWith("hf_")) { throw "No Hugging Face token was entered." }

try {
    $headers = @{ Authorization = ("Bearer " + $plain) }
    $who = Invoke-RestMethod -UseBasicParsing -Uri "https://huggingface.co/api/whoami-v2" -Headers $headers
    $role = [string]$who.auth.accessToken.role
    if (($role -replace "[^a-zA-Z]", "").ToLower() -ne "finegrained") { throw ("Token role is '" + $role + "', not fine-grained. The rotation workflow will reject it; mint a fine-grained token.") }
    $ds = Invoke-RestMethod -UseBasicParsing -Uri ("https://huggingface.co/api/datasets/" + $Dataset) -Headers $headers
    if (-not $ds.sha) { throw ("Token cannot read " + $Dataset + ". Add that dataset under the token's repository access.") }
    Write-Host ("3) token OK: identity " + $who.name + " | role " + $role + " | dataset revision " + $ds.sha.Substring(0, 10))

    $plain | & gh secret set DAVID_DATASET_READ_TOKEN --repo $Repo --env $EnvName
    if ($LASTEXITCODE -ne 0) { throw "gh secret set failed (needs admin on the repository)." }
    Write-Host ("4) secret stored: " + $Repo + " -> environment " + $EnvName + " -> DAVID_DATASET_READ_TOKEN")
}
finally {
    $plain = $null
    $headers = $null
    [GC]::Collect()
}

& gh workflow run $Workflow --repo $Repo --ref main
if ($LASTEXITCODE -ne 0) { throw "workflow dispatch failed" }
Start-Sleep -Seconds 20
& gh run list --repo $Repo --workflow $Workflow --limit 1
Write-Host "5) Rotation dispatched. The environment asks its reviewer to approve the run under Actions; once approved it applies the reader token to the Space and the live-lanes canary turns green on its next run."
