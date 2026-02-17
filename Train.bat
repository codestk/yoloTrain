@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title Automatic Full YOLO Workflow

:: เข้าไปที่โฟลเดอร์โปรเจกต์
cd /d "D:\yoloTrain"

:: Activate venv
call .\venv\Scripts\activate



REM =================================================================
REM  [START] เริ่มจับเวลา
REM =================================================================
set "startTime=%time%"
echo =================================================================
echo   Starting Automatic Full YOLO Workflow...
echo   Start Time : %startTime%
echo =================================================================
echo.

REM =================================================================
REM  [Step 1] ลบโฟลเดอร์เก่า
REM =================================================================
echo [ขั้นตอนที่ 1/4] กำลังลบโฟลเดอร์เก่า (custom_data, data, runs)...
if exist "data" ( rd /s /q "data" )
if exist "runs" ( rd /s /q "runs" )
echo Cleanup complete.
echo.
timeout /t 2 > nul

REM =================================================================
REM  [Step 2] เตรียมข้อมูล
REM =================================================================
echo [ขั้นตอนที่ 2/4] กำลังเตรียมข้อมูล Split Data YAML...
python train_val_split.py --datapath="D:\yoloTrain\custom_data" --train_pct=.9
python.exe dataYaml.py
echo Data preparation complete.
echo.
timeout /t 2 > nul

REM =================================================================
REM  [Step 3] เริ่มเทรนโมเดล
REM =================================================================
echo [ขั้นตอนที่ 3/4] กำลังเริ่มการฝึกสอนโมเดล YOLOv8s...
REM คำสั่งเทรนที่คุณเลือกใช้
yolo detect train data=data.yaml model=yolov8s.pt epochs=180 imgsz=640 

echo.
echo Model training process finished.
timeout /t 2 > nul

REM =================================================================
REM  [Step 4] ตรวจสอบความถูกต้องและ Copy ไฟล์
REM =================================================================
echo [ขั้นตอนที่ 4/4] Verifying and Copying Model...

set "sourceFile=D:\yoloTrain\runs\detect\train\weights\best.pt"
set "destFile=D:\rice_anomaly_detection_PyTorch\models\yolo\best.pt"

REM เช็คว่าไฟล์ best.pt มีอยู่จริงไหม (ถ้าเทรน error ไฟล์จะไม่มี)
if exist "%sourceFile%" (
    echo [INFO] Found best.pt successfully.
    echo [INFO] Copying to project folder...
    
    copy /Y "%sourceFile%" "%destFile%"
    
    if !errorlevel! equ 0 (
        echo [SUCCESS] Copy success ✅
    ) else (
        echo [ERROR] Copy failed ❌
    )
) else (
    echo.
    echo =========================================================
    echo [CRITICAL ERROR] Training FAILED or Interrupted! 
    echo File 'best.pt' not found.
    echo [SKIP] Skipping file copy to protect old model.
    echo =========================================================
    echo.
)

REM =================================================================
REM  [END] แจ้งเตือนเสียง และ สรุปเวลา
REM =================================================================
powershell -c (New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlaySync()
powershell -c (New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlaySync()
powershell -c (New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlaySync()

set "endTime=%time%"
echo.
echo =================================================================
echo   WORKFLOW SUMMARY
echo =================================================================
echo   Start Time : %startTime%
echo   End Time   : %endTime%
echo.
REM คำนวณเวลาที่ใช้จริง
powershell -Command "$s=[datetime]::Parse('%startTime%'); $e=[datetime]::Parse('%endTime%'); if ($e -lt $s) { $e = $e.AddDays(1) }; $diff=$e-$s; Write-Host ('   Total Duration : ' + $diff.ToString('hh\:mm\:ss')) -ForegroundColor Cyan"
echo =================================================================
echo.

pause