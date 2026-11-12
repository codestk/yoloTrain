@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d D:\yoloTrain
if not exist "D:\yoloTrain\logs" mkdir "D:\yoloTrain\logs"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "TS=%%i"
set "LOG=D:\yoloTrain\logs\run_%TS%.log"

echo ==========================================
echo 1. Clearing old data in D:\yoloTrain\custom_data...
echo ==========================================
if exist "D:\yoloTrain\custom_data" rmdir /s /q "D:\yoloTrain\custom_data"
mkdir "D:\yoloTrain\custom_data"

echo.
echo ==========================================
echo 2. Exporting annotations (JSON only) from Label Studio...
echo ==========================================
docker exec label-studio-label-studio-1 label-studio export 9 JSON --export-path=/yolo_export < nul
if errorlevel 1 (
    echo [ERROR] Export failed. Training aborted.
    goto :FAIL
)

echo Waiting for the exported JSON file (max 10 minutes)...
set /a WAITED=0
:WAIT_FOR_JSON
if exist "D:\yoloTrain\custom_data\*.json" goto JSON_FOUND
if !WAITED! GEQ 600 (
    echo [ERROR] No JSON file after 10 minutes. Training aborted.
    goto :FAIL
)
timeout /t 1 /nobreak >nul 2>&1
set /a WAITED+=1
goto WAIT_FOR_JSON

:JSON_FOUND
rem Give the export a few seconds to finish writing the file
timeout /t 5 /nobreak >nul 2>&1
set "EXPORT_JSON="
for /f "delims=" %%f in ('dir /b /o-d "D:\yoloTrain\custom_data\*.json"') do if not defined EXPORT_JSON set "EXPORT_JSON=D:\yoloTrain\custom_data\%%f"
echo JSON found: !EXPORT_JSON!

echo.
echo ==========================================
echo 3. Building YOLO dataset from JSON + images in D:\docker\label-studio\media\upload\9 ...
echo ==========================================
"D:\yoloTrain\venv\Scripts\python.exe" ls_json_to_yolo.py --json "!EXPORT_JSON!" --upload_dir "D:\docker\label-studio\media\upload\9" --out "D:\yoloTrain\custom_data"
if errorlevel 1 (
    echo [ERROR] Could not build the YOLO dataset. Training aborted.
    goto :FAIL
)

if not exist "D:\yoloTrain\custom_data\images" (
    echo [ERROR] custom_data\images not found. Training aborted.
    goto :FAIL
)
if not exist "D:\yoloTrain\custom_data\labels" (
    echo [ERROR] custom_data\labels not found. Training aborted.
    goto :FAIL
)

echo ==========================================
echo 4. Activating Python Virtual Environment...
echo ==========================================
call D:\yoloTrain\venv\Scripts\activate.bat

echo.
echo ==========================================
echo 5. Running Train.bat...
echo    Full log: %LOG%
echo    (watch it live in PowerShell: Get-Content "%LOG%" -Wait -Tail 20)
echo ==========================================
cd /d D:\yoloTrain
call Train.bat < nul > "%LOG%" 2>&1

echo.
echo ==========================================
echo All Done! Export + Training finished.
echo Last lines of the log:
echo ==========================================
powershell -NoProfile -Command "Get-Content '%LOG%' -Tail 15"
goto :SHUTDOWN

:FAIL
echo [FAIL] See messages above. >> "%LOG%"

:SHUTDOWN
echo.
echo ==========================================
echo System will force shutdown in 60 seconds...
echo (Type 'shutdown /a' in command prompt to cancel)
echo ==========================================
shutdown /s /f /t 60
