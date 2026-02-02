# Model Conversion Script for Desktop
# Converts YOLOv8 PyTorch → ONNX → NCNN with INT8 quantization

param(
    [string]$ModelPath = "AI-Model\runs\detect\nutricycle_foreign_only\weights\best.pt",
    [string]$ImageSize = "320",
    [string]$CalibrationDir = "calibration_images"
)

Write-Host "🔥 NutriCycle Model Conversion to NCNN" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Check if model exists
if (-not (Test-Path $ModelPath)) {
    Write-Host "❌ Model not found: $ModelPath" -ForegroundColor Red
    exit 1
}

$ModelDir = Split-Path $ModelPath
$ModelBase = [System.IO.Path]::GetFileNameWithoutExtension($ModelPath)

Write-Host "📦 Model: $ModelPath" -ForegroundColor Green
Write-Host "📐 Image Size: $ImageSize" -ForegroundColor Green
Write-Host ""

# Step 1: Export to ONNX
Write-Host "Step 1: Exporting to ONNX..." -ForegroundColor Yellow
try {
    yolo export model="$ModelPath" format=onnx imgsz=$ImageSize opset=12 simplify=True
    Write-Host "✅ ONNX export complete" -ForegroundColor Green
} catch {
    Write-Host "❌ ONNX export failed: $_" -ForegroundColor Red
    exit 1
}

$OnnxPath = Join-Path $ModelDir "$ModelBase.onnx"

if (-not (Test-Path $OnnxPath)) {
    Write-Host "❌ ONNX file not found: $OnnxPath" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 2: Check for NCNN tools
Write-Host "Step 2: Checking NCNN tools..." -ForegroundColor Yellow

$NcnnDir = "$env:USERPROFILE\ncnn"
$Onnx2Ncnn = "$NcnnDir\build\tools\onnx\onnx2ncnn.exe"
$Ncnn2Int8 = "$NcnnDir\build\tools\quantize\ncnn2int8.exe"

if (-not (Test-Path $Onnx2Ncnn)) {
    Write-Host "⚠️  NCNN tools not found. Building..." -ForegroundColor Yellow
    Write-Host ""
    
    # Clone NCNN
    if (-not (Test-Path $NcnnDir)) {
        Write-Host "   Cloning NCNN repository..." -ForegroundColor Cyan
        git clone --depth=1 https://github.com/Tencent/ncnn $NcnnDir
    }
    
    # Build NCNN
    Write-Host "   Building NCNN (this may take 5-10 minutes)..." -ForegroundColor Cyan
    Push-Location $NcnnDir
    
    if (-not (Test-Path "build")) {
        New-Item -ItemType Directory -Path "build" | Out-Null
    }
    
    Push-Location build
    cmake .. -G "Visual Studio 17 2022" -A x64
    cmake --build . --config Release
    Pop-Location
    Pop-Location
    
    if (-not (Test-Path $Onnx2Ncnn)) {
        Write-Host "❌ Failed to build NCNN tools" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ NCNN tools built successfully" -ForegroundColor Green
} else {
    Write-Host "✅ NCNN tools found" -ForegroundColor Green
}

Write-Host ""

# Step 3: Convert ONNX to NCNN
Write-Host "Step 3: Converting ONNX to NCNN..." -ForegroundColor Yellow

$ParamPath = Join-Path $ModelDir "$ModelBase.param"
$BinPath = Join-Path $ModelDir "$ModelBase.bin"

try {
    & $Onnx2Ncnn "$OnnxPath" "$ParamPath" "$BinPath"
    Write-Host "✅ NCNN conversion complete" -ForegroundColor Green
} catch {
    Write-Host "❌ NCNN conversion failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 4: INT8 Quantization (optional but recommended)
Write-Host "Step 4: INT8 Quantization..." -ForegroundColor Yellow

if (Test-Path $CalibrationDir) {
    $ImageCount = (Get-ChildItem "$CalibrationDir\*.jpg","$CalibrationDir\*.png" -ErrorAction SilentlyContinue).Count
    
    if ($ImageCount -gt 0) {
        Write-Host "   Found $ImageCount calibration images" -ForegroundColor Cyan
        
        $Int8ParamPath = Join-Path $ModelDir "$ModelBase-int8.param"
        $Int8BinPath = Join-Path $ModelDir "$ModelBase-int8.bin"
        
        try {
            & $Ncnn2Int8 "$ParamPath" "$BinPath" "$Int8ParamPath" "$Int8BinPath" "$CalibrationDir\"
            Write-Host "✅ INT8 quantization complete" -ForegroundColor Green
            Write-Host ""
            Write-Host "📦 Output files:" -ForegroundColor Cyan
            Write-Host "   FP32: $ParamPath" -ForegroundColor White
            Write-Host "   FP32: $BinPath" -ForegroundColor White
            Write-Host "   INT8: $Int8ParamPath" -ForegroundColor Green
            Write-Host "   INT8: $Int8BinPath" -ForegroundColor Green
            Write-Host ""
            Write-Host "⚡ Use INT8 model for 2× faster inference on Pi 4" -ForegroundColor Yellow
        } catch {
            Write-Host "⚠️  INT8 quantization failed (using FP32 model): $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "⚠️  No calibration images found in $CalibrationDir" -ForegroundColor Yellow
        Write-Host "   Skipping INT8 quantization (FP32 model only)" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  Calibration directory not found: $CalibrationDir" -ForegroundColor Yellow
    Write-Host "   Skipping INT8 quantization (FP32 model only)" -ForegroundColor Yellow
    Write-Host "   Create '$CalibrationDir' with 100-300 sample images for INT8" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "✅ Conversion Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Copy model files to Raspberry Pi:" -ForegroundColor White
Write-Host "      scp $ModelBase-int8.* pi@raspberrypi:~/NutriCycle-RaspBerry-v2/deploy/ncnn/models/" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. On Raspberry Pi, run:" -ForegroundColor White
Write-Host "      cd ~/NutriCycle-RaspBerry-v2/deploy" -ForegroundColor Gray
Write-Host "      ./setup_ncnn_pi.sh" -ForegroundColor Gray
Write-Host ""
Write-Host "   3. Test inference:" -ForegroundColor White
Write-Host "      python test_video_ncnn.py --source 1 --flip vertical" -ForegroundColor Gray
Write-Host ""
