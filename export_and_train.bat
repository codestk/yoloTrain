@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ======================================================================
rem  Export from Label Studio (JSON only) + build YOLO dataset + train.
rem  Everything shown on screen is also written to D:\yoloTrain\logs\run_*.log
rem ======================================================================

set "ROOT=D:\yoloTrain"
set "PROJECT_ID=9"
set "LS_CONTAINER=label-studio-label-studio-1"
set "UPLOAD_DIR=D:\docker\label-studio\media\upload\9"
set "PY=%ROOT%\venv\Scripts\python.exe"
rem 1 = shut the PC down at the end (also after a failure), 0 = keep it on
set "DO_SHUTDOWN=1"

rem ---- First call: start logging, then run this same file again with output copied to the log
if /i not "%~1"=="__logged" (
    if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
    for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
    set "RUNLOG=%ROOT%\logs\run_!TS!.log"
    set "SELF=%~f0"
    echo Log file: !RUNLOG!
    powershell -NoProfile -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; & cmd.exe /d /c ('\"' + $env:SELF + '\" __logged 2>&1') | Tee-Object -FilePath $env:RUNLOG; exit $LASTEXITCODE"
    set "RC=!errorlevel!"
    echo.
    if "!RC!"=="0" (echo RESULT: SUCCESS) else (echo RESULT: FAILED  ^(exit code !RC!^) - see !RUNLOG!)
    if "%DO_SHUTDOWN%"=="1" (
        echo System will force shutdown in 60 seconds... type: shutdown /a  to cancel
        shutdown /s /f /t 60
    ) else (
        pause
    )
    exit /b !RC!
)

rem ======================================================================
rem  Everything below is logged
rem ======================================================================
cd /d "%ROOT%"
set "STEP=0 - pre-checks"
call :log "===== START  %date% %time% ====="
call :log "Computer: %COMPUTERNAME%   User: %USERNAME%   Folder: %CD%"

call :log "[STEP %STEP%]"
if not exist "%PY%" (set "WHY=venv python not found: %PY%" & goto :FAIL)
"%PY%" --version
"%PY%" -c "import ultralytics, torch; print('ultralytics', ultralytics.__version__, '| torch', torch.__version__, '| CUDA', torch.cuda.is_available())"
if errorlevel 1 (set "WHY=python packages ultralytics/torch not working" & goto :FAIL)
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader 2>nul

for %%f in (ls_json_to_yolo.py train_val_split.py compare_and_deploy.py Train.bat classes.txt dataYaml.py) do (
    if not exist "%ROOT%\%%f" (set "WHY=missing file %ROOT%\%%f" & goto :FAIL)
)
call :log "Scripts present: OK"

if not exist "%UPLOAD_DIR%" (set "WHY=image folder not found: %UPLOAD_DIR%" & goto :FAIL)
set /a NIMG=0
for /f %%c in ('dir /b /a-d "%UPLOAD_DIR%" 2^>nul ^| find /c /v ""') do set "NIMG=%%c"
call :log "Images in %UPLOAD_DIR%: !NIMG!"

if exist "%ROOT%\champion\best.pt" (call :log "Champion model: present") else (call :log "WARNING: no champion\best.pt - the new model will be deployed automatically")
if exist "%ROOT%\val_split.txt" (call :log "Frozen val list: present") else (call :log "Frozen val list: not yet - current data\validation will be frozen")

docker ps --filter "name=%LS_CONTAINER%" --format "{{.Names}}  {{.Status}}"
docker ps --filter "name=%LS_CONTAINER%" --format "{{.Names}}" | findstr /i "%LS_CONTAINER%" >nul
if errorlevel 1 (set "WHY=Docker container %LS_CONTAINER% is not running (start Docker Desktop / Label Studio)" & goto :FAIL)
call :log "Docker container: running"

rem ----------------------------------------------------------------------
set "STEP=1 - clear custom_data"
call :log "[STEP %STEP%]"
if exist "%ROOT%\custom_data" rmdir /s /q "%ROOT%\custom_data"
mkdir "%ROOT%\custom_data"
if errorlevel 1 (set "WHY=could not recreate %ROOT%\custom_data" & goto :FAIL)

rem ----------------------------------------------------------------------
set "STEP=2 - export JSON from Label Studio"
call :log "[STEP %STEP%]"
call :log "docker exec %LS_CONTAINER% label-studio export %PROJECT_ID% JSON --export-path=/yolo_export"
docker exec %LS_CONTAINER% label-studio export %PROJECT_ID% JSON --export-path=/yolo_export < nul
set "RC=!errorlevel!"
call :log "docker export exit code: !RC!"
if not "!RC!"=="0" (set "WHY=label-studio export command failed (exit code !RC!) - see the docker messages above" & goto :FAIL)

call :log "Waiting for the JSON file in %ROOT%\custom_data (max 10 minutes)..."
set /a WAITED=0
:WAIT_FOR_JSON
if exist "%ROOT%\custom_data\*.json" goto JSON_FOUND
if !WAITED! GEQ 600 (
    call :log "Files currently in the container export folder:"
    docker exec %LS_CONTAINER% ls -la /yolo_export
    set "WHY=no JSON file appeared in %ROOT%\custom_data after 10 minutes. Check that /yolo_export in the container is mounted to %ROOT%\custom_data"
    goto :FAIL
)
timeout /t 1 /nobreak >nul 2>&1
set /a WAITED+=1
goto WAIT_FOR_JSON

:JSON_FOUND
timeout /t 5 /nobreak >nul 2>&1
set "EXPORT_JSON="
for /f "delims=" %%f in ('dir /b /o-d "%ROOT%\custom_data\*.json"') do if not defined EXPORT_JSON set "EXPORT_JSON=%ROOT%\custom_data\%%f"
for %%A in ("!EXPORT_JSON!") do set "JSIZE=%%~zA"
call :log "JSON found after !WAITED! s: !EXPORT_JSON!  (!JSIZE! bytes)"

rem ----------------------------------------------------------------------
set "STEP=3 - build YOLO dataset from JSON + images"
call :log "[STEP %STEP%]"
"%PY%" ls_json_to_yolo.py --json "!EXPORT_JSON!" --upload_dir "%UPLOAD_DIR%" --out "%ROOT%\custom_data"
set "RC=!errorlevel!"
call :log "ls_json_to_yolo.py exit code: !RC!"
if not "!RC!"=="0" (set "WHY=ls_json_to_yolo.py failed (exit code !RC!) - see its messages above" & goto :FAIL)
for /f %%c in ('dir /b /a-d "%ROOT%\custom_data\images" 2^>nul ^| find /c /v ""') do set "NI=%%c"
for /f %%c in ('dir /b /a-d "%ROOT%\custom_data\labels" 2^>nul ^| find /c /v ""') do set "NL=%%c"
call :log "custom_data: !NI! images, !NL! label files"
if "!NI!"=="0" (set "WHY=custom_data\images is empty" & goto :FAIL)

rem ----------------------------------------------------------------------
set "STEP=4-5 - split + train + compare (Train.bat)"
call :log "[STEP %STEP%]  started %time%"
call "%ROOT%\venv\Scripts\activate.bat"
call "%ROOT%\Train.bat" < nul
set "RC=!errorlevel!"
call :log "Train.bat finished %time%, exit code: !RC!"

set "LASTRUN="
for /f "delims=" %%d in ('dir /b /ad /o-d "%ROOT%\runs\detect\m640_*" 2^>nul') do if not defined LASTRUN set "LASTRUN=%%d"
if not defined LASTRUN (set "WHY=no runs\detect\m640_* folder was created - training did not start, see Train.bat output above" & goto :FAIL)
if not exist "%ROOT%\runs\detect\!LASTRUN!\weights\best.pt" (set "WHY=training of !LASTRUN! did not produce best.pt - see the training output above" & goto :FAIL)
call :log "Last run: !LASTRUN!"
if exist "%ROOT%\champion\history.csv" (
    call :log "Last lines of champion\history.csv:"
    powershell -NoProfile -Command "Get-Content '%ROOT%\champion\history.csv' -Tail 3"
)

call :log "===== SUCCESS  %date% %time% ====="
exit /b 0

:FAIL
echo.
call :log "############################################################"
call :log "FAILED at step: %STEP%"
call :log "Reason: %WHY%"
call :log "############################################################"
exit /b 1

:log
echo [%date% %time:~0,8%] %~1
exit /b 0
