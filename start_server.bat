@echo off
title AssetCore Server
echo ========================================================
echo               AssetCore Local Server
echo ========================================================
echo.
echo Starting the server on your computer...
echo.
echo IMPORTANT: 
echo Your data is saved permanently in this folder inside
echo the file named: database.sqlite
echo.
echo Keep this black window open while using the website!
echo You can minimize it.
echo ========================================================
echo.

:: Open the browser
start http://localhost:8000

:: Run the python server
python server.py

pause
