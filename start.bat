@echo off
rem This script automates the startup process for the ChatBet application on Windows.

echo Starting ChatBet services...

rem Start containers in detached mode to run them in the background.
rem The --build flag ensures the images are up-to-date with the latest code.
docker-compose up --build -d

echo.
echo Waiting for the backend service to initialize...
echo This may take a minute during the first run as caches are being built from the API.
echo Subsequent runs will be much faster by using the local cache files.

:poll
rem Use curl (expected to be in PATH, e.g., from Git for Windows) to check the health status.
rem The findstr command will search for the ready signal and set errorlevel to 0 if found.
curl -s http://localhost:8000/health/status | findstr /R "\"cache_ready\": *true" > nul
if %errorlevel% equ 0 (
    echo.
    echo.
    echo ChatBet is ready!
    echo Opening the application in your default browser...
    rem Open the URL in the default browser.
    start http://localhost:8D001
    goto:eof
)

rem Print a dot to show progress.
echo | set /p=.

rem Wait for 5 seconds before trying again.
timeout /t 5 /nobreak > nul
goto :poll

:eof
echo.
echo Your ChatBet instance is running in the background.
echo To view live logs, run: docker-compose logs -f
echo To stop the services, run: docker-compose down
