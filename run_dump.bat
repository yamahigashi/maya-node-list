echo off
setlocal
set "PFX=%~dp0"
set "PATH=%PFX%tool;%PFX%tool\vendor;%PATH%"
set "PYTHONPATH=%PFX%tool\vendor"
pushd "%PFX%"

set "MAYA_VERSION=2026"
set MAYA_UI_LANGUAGE=en_US
set "DUMP_ARGS="

if not "%~1"=="" (
    set "MAYA_VERSION=%~1"
    shift
)

:collect_dump_args
if "%~1"=="" goto :args_ready
if not defined DUMP_ARGS goto :set_first_dump_arg
set "DUMP_ARGS=%DUMP_ARGS% %~1"
shift
goto :collect_dump_args

:set_first_dump_arg
set "DUMP_ARGS=%~1"
shift
goto :collect_dump_args

:args_ready

echo Using MAYA_VERSION=%MAYA_VERSION%

if "%DUMP_ARGS%"=="" (
    echo Extra args: ^(none^)
)
if not "%DUMP_ARGS%"=="" (
    echo Extra args: %DUMP_ARGS%
)


for /f "skip=2 tokens=2*" %%A ^
in ('reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Autodesk\Maya\%MAYA_VERSION%\Setup\InstallPath" /v "MAYA_INSTALL_LOCATION"') ^
do set "MAYALOC=%%B"

if "%MAYALOC%"=="" (
    echo Maya install path not found for version %MAYA_VERSION%.
    popd
    exit /b 1
)

set "MAYA_EXE=%MAYALOC%bin\mayapy.exe"
if not exist "%MAYA_EXE%" (
    echo mayapy.exe not found: %MAYA_EXE%
    popd
    exit /b 1
)


call "%MAYA_EXE%" "%PFX%\tool\dump_maya_nodes.py" %DUMP_ARGS%
if errorlevel 1 goto :error

popd
exit /b 0

:error
echo run_dump.bat failed.
popd
exit /b 1
