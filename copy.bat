@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title Automatic Full YOLO Workflow

 
 
:COPY_CHECK
echo [Step 4/4] Verifying and copying model...
@echo off
 
set "src=C:\yoloTrain\runs\detect\train\weights\best.pt"
set "dst1=C:\LM-Backend\label-studio-ml-backend\label_studio_ml\examples\yolo\models\best.pt"
set "dst2=\\Detect-Noebook\D\rice_anomaly_detection_PyTorch\models\yolo\best.pt"

if exist "%src%" (
    copy /Y "%src%" "%dst1%"
    copy /Y "%src%" "%dst2%"
    echo [OK] Model updated and backed up.
) else (
    echo [!] Error: source file not found.
)

:END
powershell -c (New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlaySync()
powershell -c (New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlaySync()
powershell -c (New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlaySync()

 
