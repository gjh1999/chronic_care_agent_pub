@echo off
setlocal
chcp 65001 >nul

echo ============================================
echo  停止慢性病管理 Agent 全部服务
echo ============================================
echo.

for %%p in (8000 8010 8020 5173 5174) do (
  for /f "tokens=5" %%i in ('netstat -ano ^| findstr /R /C:":%%p .*LISTENING"') do (
    echo 停止端口 %%p 上的进程 PID %%i
    taskkill /F /PID %%i >nul 2>&1
  )
)

echo.
echo 已全部停止(若个别进程由其他窗口托管,请手动关闭对应窗口)
echo.
pause
exit /b 0
