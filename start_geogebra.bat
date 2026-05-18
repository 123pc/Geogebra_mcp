@echo off
REM Dynamically find the latest installed GeoGebra Classic 6
setlocal enabledelayedexpansion

set GEOGEBRA_EXE=
for /d %%v in ("%LOCALAPPDATA%\GeoGebra_6\app-*") do set GEOGEBRA_EXE=%%v\GeoGebra.exe

if "%GEOGEBRA_EXE%"=="" (
    echo GeoGebra Classic 6 not found in %LOCALAPPDATA%\GeoGebra_6
    echo Please install GeoGebra Classic 6 from https://www.geogebra.org/download
    pause
    exit /b 1
)

echo Starting: %GEOGEBRA_EXE%
start "" "%GEOGEBRA_EXE%" --remote-debugging-port=9222
echo GeoGebra launched with debug port 9222
