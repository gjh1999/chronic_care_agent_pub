@echo off
setlocal

set RAG_DIR=C:\Users\gjh\PycharmProjects\RAG
set INTENT_DIR=C:\Users\gjh\PycharmProjects\Medical_Lora
set FRONTEND_DIR=%~dp0miniprogram

echo ============================================
echo  慢性病管理 Agent 一键启动(全部 4 个服务)
echo ============================================
echo.

echo [1/4] RAG 检索服务 (127.0.0.1:8010)...
netstat -ano | findstr /R /C:":8010 .*LISTENING" >/dev/null 2>&1
if errorlevel 1 (
  start "RAG-8010" cmd /k "cd /d %RAG_DIR% && .venv\Scripts\python.exe -m uvicorn service_app:app --host 127.0.0.1 --port 8010"
) else (
  echo   已在运行,跳过启动
)
call :wait_health "http://127.0.0.1:8010/healthz" "RAG" 150
if errorlevel 1 exit /b 1

echo [2/4] 意图识别服务 (127.0.0.1:8020)...
netstat -ano | findstr /R /C:":8020 .*LISTENING" >/dev/null 2>&1
if errorlevel 1 (
  start "MedicalLora-8020" cmd /k "cd /d %INTENT_DIR% && .venv\Scripts\python.exe -m uvicorn service_app:app --host 127.0.0.1 --port 8020"
) else (
  echo   已在运行,跳过启动
)
call :wait_health "http://127.0.0.1:8020/healthz" "Medical_Lora" 300
if errorlevel 1 exit /b 1

echo [3/4] 本项目后端 (127.0.0.1:8000)...
netstat -ano | findstr /R /C:":8000 .*LISTENING" >/dev/null 2>&1
if errorlevel 1 (
  cd /d "%~dp0"
  if not exist .env (
    copy .env.example .env >/dev/null
    echo 已自动复制 .env.example 为 .env,请确认配置无误
  )
  .venv\Scripts\python.exe scripts\init_db.py
  if errorlevel 1 (
    echo 数据库初始化失败,请检查上方日志
    pause
    exit /b 1
  )
  start "chronic-care-8000" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
) else (
  echo   已在运行,跳过启动
)
call :wait_health "http://127.0.0.1:8000/readyz" "本项目" 60
if errorlevel 1 exit /b 1

echo [4/4] 前端 H5 (http://localhost:5173)...
netstat -ano | findstr /R /C:":5173 .*LISTENING" >/dev/null 2>&1
if errorlevel 1 (
  if not exist "%FRONTEND_DIR%\node_modules" (
    echo   首次运行,安装前端依赖（可能需要几分钟）...
    cd /d "%FRONTEND_DIR%"
    call npm install
    if errorlevel 1 (
      echo 前端依赖安装失败,请检查网络与 npm 配置
      pause
      exit /b 1
    )
    cd /d "%~dp0"
  )
  start "chronic-care-h5" cmd /k "cd /d %FRONTEND_DIR% && npm run dev:h5"
) else (
  echo   5173 已在监听,跳过启动（若为旧进程请先运行 stop_all.bat）
)
call :wait_health "http://localhost:5173/" "前端 H5" 45
if errorlevel 1 (
  call :wait_health "http://localhost:5174/" "前端 H5(漂移到 5174)" 30
)

echo.
echo 全部服务已就绪:
echo   RAG        http://127.0.0.1:8010/healthz
echo   意图服务    http://127.0.0.1:8020/healthz
echo   本项目      http://127.0.0.1:8000/docs
echo   前端 H5     http://localhost:5173/   (若端口被占则 5174)
echo   依赖检查    http://127.0.0.1:8000/dependencies
echo.
echo 提示:网页登录页可输入不同昵称模拟不同测试账号
echo.
pause
exit /b 0

:wait_health
set "url=%~1"
set "name=%~2"
set "tries=%~3"
for /l %%i in (1,1,%tries%) do (
  curl -sf -o nul "%url%" 2>/dev/null
  if not errorlevel 1 goto :ready
  ping -n 3 127.0.0.1 >/dev/null
)
echo %name% 健康检查超时,请查看对应窗口日志
exit /b 1
:ready
echo %name% 已就绪
exit /b 0
