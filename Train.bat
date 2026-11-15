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

echo [Step 1/4] Keeping old runs (no cleanup). data\train and data\validation are rebuilt in step 2.
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "TS=%%i"
rem ---- Model settings: change only these two lines to switch model / image size ----
set "MODEL=yolo11s"
set "IMGSZ=640"
set "RUN=%MODEL%_%IMGSZ%_%TS%"
rem Remember the run name so export_and_train.bat can find it
> "%~dp0last_run.txt" echo %RUN%
echo Run name: %RUN%
echo.

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
timeout /t 20 > nul 2>&1

REM =================================================================
REM  [Step 3] เริ่มเทรนโมเดล
REM =================================================================
echo [ขั้นตอนที่ 3/4] กำลังเริ่มการฝึกสอนโมเดล %MODEL% ...
REM คำสั่งเทรนที่คุณเลือกใช้
REM yolo detect train data=data.yaml model=yolov8s.pt epochs=180 imgsz=640   device=0 workers=2
rem yolo detect train data=data.yaml model=yolov8s.pt epochs=60 imgsz=640   device=0  

rem yolo detect train data=data.yaml model=yolov8s.pt imgsz=640 epochs=130   device=0
rem yolo detect train data=data.yaml model=yolov8s.pt imgsz=960 epochs=150 patience=30 batch=8 workers=4 device=0 cos_lr=True close_mosaic=15 flipud=0.5 fliplr=0.5 name=train_s960_norot
rem yolo detect train data=data.yaml model=yolov8s.pt imgsz=960 epochs=130 device=0 batch=4

rem yolo detect train data=data.yaml model=yolo11s.pt imgsz=640 epochs=130   device=0
rem 
rem yolo detect train data=data.yaml model=yolov8m.pt imgsz=640 epochs=150 patience=40 batch=12 workers=4 device=0 cos_lr=True close_mosaic=15 flipud=0.5 fliplr=0.5 name=train_m640
rem yolo detect train data=data.yaml model=yolov8m.pt imgsz=640 epochs=150 patience=40 batch=12 workers=4 device=0 cos_lr=True close_mosaic=70 flipud=0.5 fliplr=0.5 seed=0 name=train_m640_close70
 
rem Best command for training YOLOv8m with specific parameters:
rem yolo detect train data=data.yaml model=yolov8m.pt imgsz=640 epochs=150 patience=40 batch=12 workers=4 device=0 cos_lr=True close_mosaic=70 flipud=0.5 fliplr=0.5 seed=0 name=train_m640_close70
"%VENV_YOLO%" detect train data=data.yaml model=%MODEL%.pt imgsz=%IMGSZ% epochs=150 patience=40 batch=12 workers=4 device=0 cos_lr=True close_mosaic=70 flipud=0.5 fliplr=0.5 seed=0 name=%RUN%

echo.
echo Model training process finished.
timeout /t 15 > nul 2>&1

:COPY_CHECK
echo [Step 4/4] Comparing with champion and deploying only if better...

set "src=D:\yoloTrain\runs\detect\%RUN%\weights\best.pt"
set "dst1=D:\docker\LM-Backend\label-studio-ml-backend\label_studio_ml\examples\yolo\models\best.pt"
set "dst2=d:\rice_anomaly_detection_PyTorch\models\yolo\best.pt"
set "dst3=D:\docker\LM-Backend-Git\label-studio-ml-backend\label_studio_ml\examples\yolo\models\best.pt"

if not exist "%src%" (
    echo [!] Error: source file not found: %src%
    goto :END
)
REM YOLO26 needs ultralytics 8.4+. The rice app (8.3.225) and the Label Studio ML backends
REM may not load it yet, so for yolo26 models only compare - do not copy to the apps.
set "DEPLOY_ARGS=--dest "%dst1%" --dest "%dst2%" --dest "%dst3%""
if /i "%MODEL:~0,6%"=="yolo26" (
    set "DEPLOY_ARGS="
    echo [i] %MODEL%: compare only. Not copied to rice app / Label Studio - upgrade ultralytics there first.
)
"%VENV_PYTHON%" compare_and_deploy.py --imgsz %IMGSZ% --new "%src%" %DEPLOY_ARGS%


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
