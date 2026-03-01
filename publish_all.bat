echo off
setlocal
set "PFX=%~dp0"
set "PATH=%PFX%tool;%PFX%tool\vendor;%PATH%"
set "PYTHONPATH=%PFX%tool\vendor"
pushd "%PFX%"

set VERSION=2020
call make.bat publish-version VERSION=2020
set VERSION=2023
call make.bat publish-version VERSION=2023
set VERSION=2024
call make.bat publish-version VERSION=2024
set VERSION=2025
call make.bat publish-version VERSION=2025
set VERSION=2026
call make.bat publish-version VERSION=2026

popd
