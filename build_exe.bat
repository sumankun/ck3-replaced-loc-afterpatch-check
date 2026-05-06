@echo off
py -m pip install pyinstaller
py -m PyInstaller --noconsole --onefile --name ck3_loc_checker ck3_loc_checker.py
pause
