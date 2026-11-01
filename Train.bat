@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title Automatic Full YOLO Workflow

cd /d "D:\yoloTrain"

call .\venv\Scripts\activate
set "VENV_PYTHON=D:\yoloTrain\venv\Scripts\python.exe"
set "VENV_PIP=D:\yoloTrain\venv\Scripts\pip.exe"
set "VENV_YOLO=D:\yoloTrain\venv\Scripts\yolo.exe"

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
timeout /t 5 > nul

echo [Step 2/4] Preparing dataset split and YAML...
"%VENV_PYTHON%" train_val_split.py --datapath="D:\yoloTrain\custom_data" --train_pct=.9
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
timeout /t 20 > nul

REM =================================================================
REM  [Step 3] เริ่มเทรนโมเดล
REM =================================================================
echo [ขั้นตอนที่ 3/4] กำลังเริ่มการฝึกสอนโมเดล YOLOv8s...
REM คำสั่งเทรนที่คุณเลือกใช้
REM yolo detect train data=data.yaml model=yolov8s.pt epochs=180 imgsz=640   device=0 workers=2
rem yolo detect train data=data.yaml model=yolov8s.pt epochs=60 imgsz=640   device=0  

yolo detect train data=data.yaml model=yolov8s.pt imgsz=640 epochs=130   device=0
rem yolo detect train data=data.yaml model=yolo11s.pt imgsz=640 epochs=130   device=0
 

echo.
echo Model training process finished.
timeout /t 15 > nul

:COPY_CHECK
echo [Step 4/4] Verifying and copying model...
@echo off


set "src=D:\yoloTrain\runs\detect\train\weights\best.pt"
set "dst1=D:\docker\LM-Backend\label-studio-ml-backend\label_studio_ml\examples\yolo\models\best.pt"
set "dst2=d:\rice_anomaly_detection_PyTorch\models\yolo\best.pt"
set "dst3=D:\docker\LM-Backend-Git\label-studio-ml-backend\label_studio_ml\examples\yolo\models\best.pt"

if exist "%src%" (
    copy /Y "%src%" "%dst1%"
    copy /Y "%src%" "%dst2%"
    copy /Y "%src%" "%dst3%"
    echo [OK] Model updated and backed up.
) else (
    echo [!] Error: source file not found.
)


:END
powershell -c (New-Object Media.SoundPlayer "c:\Windows\Media\Alarm01.wav").PlaySync()
powershell -c (New-Object Media.SoundPlayer "c:\Windows\Media\Alarm01.wav").PlaySync()
powershell -c (New-Object Media.SoundPlayer "c:\Windows\Media\Alarm01.wav").PlaySync()

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
