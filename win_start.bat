@echo off
cd /d %~dp0

call .\env\Scripts\activate
python .\main.py
pause