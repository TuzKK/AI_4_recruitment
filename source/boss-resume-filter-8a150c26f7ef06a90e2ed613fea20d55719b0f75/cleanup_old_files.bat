@echo off
echo 清理旧的候选人文件...
cd /d "%~dp0"

echo.
echo 清理前:
dir /b candidates_*.json candidates_*.xlsx 2>nul | find /c /v ""

:: 删除所有带时间戳的 JSON 文件（保留 candidates_all.json）
for /f "delims=" %%i in ('dir /b candidates_*.json 2^>nul ^| findstr /v "^candidates_all\.json$"') do (
    del /q "%%i"
)

:: 删除所有带时间戳的 Excel 文件（保留 candidates_all.xlsx）
for /f "delims=" %%i in ('dir /b candidates_*.xlsx 2^>nul ^| findstr /v "^candidates_all\.xlsx$"') do (
    del /q "%%i"
)

echo.
echo 清理后:
dir /b candidates_*.json candidates_*.xlsx 2>nul | find /c /v ""

echo.
echo 保留的文件:
dir /b candidates_all.* 2>nul

echo.
echo 清理完成!
pause
