# Perfect Recall Desktop

The Windows control panel for DragonMine Z: Perfect Recall. It combines a
Tauri 2 shell, a React/TypeScript interface, and the existing Python/OpenCV
detection engine.

The interface starts in English and includes an `EN | PT` control for a fully
localized Brazilian Portuguese UI. The selected language is saved locally.

## Commands

```powershell
npm install
npm run tauri dev
npm run bundle
```

`npm run bundle` first packages the Python engine with PyInstaller, then builds
the frontend, native Tauri executable, and NSIS installer.
