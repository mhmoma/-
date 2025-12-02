@echo off
set REPO_URL=https://github.com/mhmoma/-.git

REM --- Git 操作 ---
echo.
echo Initializing Git repository and setting main branch...
git init
git checkout -b main

echo.
echo Adding all files to staging...
git add .

echo.
echo Creating a new commit...
git commit -m "feat: Project update on %date% %time%"

echo.
echo Setting remote repository...
git remote add origin %REPO_URL% 2>nul || git remote set-url origin %REPO_URL%

echo.
echo Configuring Git proxy...
git config --global http.proxy http://127.0.0.1:18888
git config --global https.proxy http://127.0.0.1:18888

echo.
echo Pushing to the main branch...
git push -u -f origin main

echo.
echo Removing Git proxy configuration...
git config --global --unset http.proxy
git config --global --unset https.proxy

echo.
echo --- All files have been uploaded successfully! ---
pause
