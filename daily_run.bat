@echo off
setlocal

cd /d "%~dp0"

echo ============================================================
echo BELLHAVEN DAILY RECONCILIATION
echo ============================================================
echo.

echo [1/2] Scraping Bellhaven website...
".venv\Scripts\python.exe" scrape_website.py

if errorlevel 1 (
    echo.
    echo ERROR: Website scraper failed.
    echo Proposal generation will NOT run.
    exit /b 1
)

echo.
echo [2/2] Generating reconciliation proposals...
".venv\Scripts\python.exe" generate_proposals.py

if errorlevel 1 (
    echo.
    echo ERROR: Proposal generation failed.
    exit /b 1
)

echo.
echo ============================================================
echo DAILY RECONCILIATION COMPLETE
echo ============================================================
echo.

exit /b 0