@echo off
chcp 65001 > nul
echo ===================================================
echo   GitHub로 코드 푸시 중... (AIKS Repository)
echo ===================================================
echo.

git push -u origin main

echo.
if errorlevel 1 (
    echo [오류] 푸시에 실패했습니다. 위 오류 메시지를 확인해 주세요.
) else (
    echo [성공] GitHub에 코드가 성공적으로 업로드되었습니다!
)
echo.
pause
