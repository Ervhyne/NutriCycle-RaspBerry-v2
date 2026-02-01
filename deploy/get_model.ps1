param(
    [Parameter(Mandatory=$true)][string]$ModelUrl,
    [Parameter(Mandatory=$true)][string]$DestPath
)

$destDir = Split-Path -Parent $DestPath
if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir | Out-Null }

Write-Host "Downloading $ModelUrl -> $DestPath"
Invoke-WebRequest -Uri $ModelUrl -OutFile $DestPath -UseBasicParsing
Write-Host "Download complete: $DestPath"