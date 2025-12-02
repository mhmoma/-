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
echo Pushing to the main branch...
git push -u -f origin main

echo.
echo --- All files have been uploaded successfully! ---
pause
