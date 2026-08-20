@echo off
REM Double-click to open the ShieldAI Launcher GUI.
REM -STA is required for Windows Forms; -ExecutionPolicy Bypass avoids policy prompts.
powershell -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0ShieldAI-Launcher.ps1"
