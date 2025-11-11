@echo off
REM Launch Tauri desktop (backend must be running on 5173)
if not exist app_desktop
ode_modules (
    pushd app_desktop
    npm install
    popd
)
cd app_desktop
npm run tauri dev
