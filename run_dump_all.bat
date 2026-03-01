echo off
setlocal
set "PFX=%~dp0"
set "PATH=%PFX%tool;%PFX%tool\vendor;%PATH%"
set "PYTHONPATH=%PFX%tool\vendor"
pushd "%PFX%"

call "%PFX%run_dump.bat" 2023
call "%PFX%run_dump.bat" 2024
call "%PFX%run_dump.bat" 2025
call "%PFX%run_dump.bat" 2026

popd
