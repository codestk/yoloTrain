@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title Automatic Full YOLO Workflow

cd /d "C:\yoloTrain"

call .\venv\Scripts\activate
set "VENV_PYTHON=C:\yoloTrain\venv\Scripts\python.exe"
set "VENV_PIP=C:\yoloTrain\venv\Scripts\pip.exe"
set "VENV_YOLO=C:\yoloTrain\venv\Scripts\yolo.exe"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] venv python not found: "%VENV_PYTHON%"
    goto :END
)

if not exist "%VENV_YOLO%" (
    echo [INFO] yolo.exe not found in venv. Installing ultralytics...
    "%VENV_PIP%" install ultralytics
    if not exist "%VENV_YOLO%" (
        echo [ERROR] Failed to install ultralytics/yolo in venv.
        goto :END
    )
)

set "startTime=%time%"
echo ================================================================
echo   Starting Automatic Full YOLO Workflow...
echo   Start Time : %startTime%
echo ================================================================
echo.

echo [Step 1/4] Cleaning old folders (data, runs)...
if exist "data" rd /s /q "data"
if exist "runs" rd /s /q "runs"
echo Cleanup complete.
echo.
timeout /t 2 > nul

echo [Step 2/4] Preparing dataset split and YAML...
"%VENV_PYTHON%" train_val_split.py --datapath="C:\yoloTrain\custom_data" --train_pct=.9
if errorlevel 1 (
    echo [ERROR] train_val_split.py failed.
    goto :END
)
"%VENV_PYTHON%" dataYaml.py
if errorlevel 1 (
    echo [ERROR] dataYaml.py failed.
    goto :END
)
echo Data preparation complete.
echo.
timeout /t 2 > nul

echo [Step 3/4] Training YOLOv8s...
echo [INFO] Installing NumPy 1.26.4 for compatibility...
"%VENV_PIP%" install numpy==1.26.4
if errorlevel 1 (
    echo [ERROR] Failed to install NumPy 1.26.4.
    goto :END
)
echo [INFO] Checking CUDA availability in venv torch...
call :CHECK_CUDA
if errorlevel 1 (
    echo [WARN] CUDA not available. Installing CUDA-enabled PyTorch cu124...
    "%VENV_PIP%" install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
    if errorlevel 1 (
        echo [ERROR] Failed to install CUDA-enabled PyTorch.
        goto :END
    )
    echo [INFO] Re-checking CUDA after torch install...
    call :CHECK_CUDA
    if errorlevel 1 (
        echo [ERROR] CUDA still unavailable in this venv.
        echo [HINT] Check NVIDIA driver with: nvidia-smi
        echo [HINT] Then reopen terminal and run Train.bat again.
        goto :END
    )
)
echo [INFO] Training device: GPU 0
"%VENV_YOLO%" detect train data=data.yaml model=yolov8s.pt epochs=180 imgsz=640 project=C:\yoloTrain\runs name=train workers=2 device=0
if errorlevel 1 (
    echo [ERROR] Training command failed.
    goto :COPY_CHECK
)
echo Model training process finished.
timeout /t 2 > nul

:COPY_CHECK
echo [Step 4/4] Verifying and copying model...
set "sourceFile=C:\yoloTrain\runs\train\weights\best.pt"
set "destFile=D:\rice_anomaly_detection_PyTorch\models\yolo\best.pt"

if exist "%sourceFile%" (
    echo [INFO] Found best.pt
    copy /Y "%sourceFile%" "%destFile%"
    if errorlevel 1 (
        echo [ERROR] Copy failed.
    ) else (
        echo [SUCCESS] Copy complete.
    )
) else (
    echo [CRITICAL] Training failed or interrupted. best.pt not found.
    echo [SKIP] Copy skipped to protect existing model.
)

:END
powershell -c (New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlaySync()
powershell -c (New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlaySync()
powershell -c (New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlaySync()

set "endTime=%time%"
echo.
echo ================================================================
echo   WORKFLOW SUMMARY
echo ================================================================
echo   Start Time : %startTime%
echo   End Time   : %endTime%
echo.
powershell -Command "$s=[datetime]::Parse('%startTime%'); $e=[datetime]::Parse('%endTime%'); if ($e -lt $s) { $e = $e.AddDays(1) }; $diff=$e-$s; Write-Host ('   Total Duration : ' + $diff.ToString('hh\:mm\:ss')) -ForegroundColor Cyan"
echo ================================================================
echo.
pause
goto :EOF

:CHECK_CUDA
"%VENV_PYTHON%" -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"
exit /b %errorlevel%
