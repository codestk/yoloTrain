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
echo 2. Exporting dataset from Label Studio...
echo ==========================================
docker exec label-studio-label-studio-1 label-studio export 9 YOLO_WITH_IMAGES --export-path=/yolo_export < nul
if errorlevel 1 (
    echo [ERROR] Export failed. Training aborted.
    goto :FAIL
)

echo Waiting for the exported ZIP file to be ready (max 10 minutes)...
set /a WAITED=0
:WAIT_FOR_ZIP
if exist "D:\yoloTrain\custom_data\*.zip" goto ZIP_FOUND
if !WAITED! GEQ 600 (
    echo [ERROR] No ZIP file after 10 minutes. Training aborted.
    goto :FAIL
)
timeout /t 1 /nobreak >nul 2>&1
set /a WAITED+=1
goto WAIT_FOR_ZIP

:ZIP_FOUND
rem Give the export a few seconds to finish writing the file
timeout /t 5 /nobreak >nul 2>&1
echo ZIP file found! Proceeding to extraction...

echo.
echo ==========================================
echo 3. Extracting files and cleaning up...
echo ==========================================
powershell -NoProfile -Command "Expand-Archive -Path 'D:\yoloTrain\custom_data\*.zip' -DestinationPath 'D:\yoloTrain\custom_data\temp' -Force"
if errorlevel 1 (
    echo [ERROR] Could not extract the ZIP file. Training aborted.
    goto :FAIL
)
powershell -NoProfile -Command "Move-Item -Path 'D:\yoloTrain\custom_data\temp\*' -Destination 'D:\yoloTrain\custom_data\' -Force"
powershell -NoProfile -Command "Remove-Item -Path 'D:\yoloTrain\custom_data\*.zip' -Force"
powershell -NoProfile -Command "Remove-Item -Path 'D:\yoloTrain\custom_data\temp' -Recurse -Force"

if not exist "D:\yoloTrain\custom_data\images" (
    echo [ERROR] custom_data\images not found after extraction. Training aborted.
    goto :FAIL
)
if not exist "D:\yoloTrain\custom_data\labels" (
    echo [ERROR] custom_data\labels not found after extraction. Training aborted.
    goto :FAIL
)
if not exist "D:\yoloTrain\custom_data\classes.txt" (
    echo [ERROR] custom_data\classes.txt not found after extraction. Training aborted.
    goto :FAIL
)

echo.
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
