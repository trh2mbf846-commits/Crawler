@echo off
cd /d "%~dp0"
title Ausschreibungs-Crawler
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crawler-starten.ps1"
if errorlevel 1 pause
