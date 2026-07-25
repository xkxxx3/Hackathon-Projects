@echo off
REM ============================================================
REM CatMBTI - one-shot build + start for public-tunnel deploy
REM
REM 1) builds the React frontend into web/dist/
REM 2) starts FastAPI on 0.0.0.0:8000 (serves both API and the
REM    built frontend from the same origin)
REM
REM After this finishes, in a SECOND terminal run cloudflared:
REM   cloudflared tunnel --url http://127.0.0.1:8000
REM and share the printed *.trycloudflare.com URL.
REM
REM IMPORTANT: use 127.0.0.1 not localhost. On Windows, "localhost" resolves
REM to IPv6 ::1 first, but uvicorn --host 0.0.0.0 only binds IPv4. cloudflared
REM would then fail with "connectex: actively refused".
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo [1/2] Building frontend (web/dist) ...
pushd web
call npm install || goto :fail
call npm run build || goto :fail
popd

echo.
echo [2/2] Starting FastAPI on 0.0.0.0:8000 ...
cd server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

goto :eof

:fail
echo.
echo Build failed. Fix the error above and try again.
popd
exit /b 1
