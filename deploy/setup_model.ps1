# NutriCycle - Setup model for Windows deployment
# This script copies the trained model from AI-Model/ to deploy/models/
# Run from repo root: .\deploy\setup_model.ps1

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

# Source model locations
$SourceModel = Join-Path $RepoRoot "AI-Model\runs\detect\nutricycle_foreign_only\weights\best.pt"
$SourceOnnx = Join-Path $RepoRoot "AI-Model\runs\detect\nutricycle_foreign_only\weights\best.onnx"

# Destination
$DestDir = Join-Path $RepoRoot "deploy\models"

Write-Host "=== NutriCycle Model Setup ===" -ForegroundColor Cyan

# Create destination directory
if (-not (Test-Path $DestDir)) {
    New-Item -ItemType Directory -Path $DestDir | Out-Null
    Write-Host "Created directory: $DestDir" -ForegroundColor Green
}

# Copy best.pt (PyTorch model - recommended)
if (Test-Path $SourceModel) {
    Write-Host "Copying $SourceModel -> $DestDir\best.pt" -ForegroundColor Yellow
    Copy-Item $SourceModel -Destination (Join-Path $DestDir "best.pt") -Force
    Write-Host "OK best.pt ready" -ForegroundColor Green
} else {
    Write-Host "Warning: $SourceModel not found" -ForegroundColor Yellow
}

# Copy best.onnx if available (optional, for ONNX runtime)
if (Test-Path $SourceOnnx) {
    Write-Host "Copying $SourceOnnx -> $DestDir\best.onnx" -ForegroundColor Yellow
    Copy-Item $SourceOnnx -Destination (Join-Path $DestDir "best.onnx") -Force
    Write-Host "OK best.onnx ready" -ForegroundColor Green
} else {
    Write-Host "Info: ONNX model not found (optional)" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "=== Model files ready in $DestDir ===" -ForegroundColor Cyan
Get-ChildItem $DestDir | Format-Table Name, Length, LastWriteTime

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Activate venv" -ForegroundColor White
Write-Host "2. Test: python deploy\test_video.py --model deploy\models\best.pt --source 0" -ForegroundColor White
Write-Host "3. Start server: python deploy\webrtc_server.py --model deploy\models\best.pt --source 0" -ForegroundColor White
