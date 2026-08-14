@echo off
cd /d "%~dp0"
echo Opening Pixabay music searches (download MP3s, rename as listed in README.md)
start "" "https://pixabay.com/music/search/upbeat%%20loop/"
timeout /t 1 /nobreak >nul
start "" "https://pixabay.com/music/search/upbeat%%20energetic/"
timeout /t 1 /nobreak >nul
start "" "https://pixabay.com/music/search/calm%%20loop/"
timeout /t 1 /nobreak >nul
start "" "https://pixabay.com/music/search/ambient%%20calm/"
echo.
echo Save as:
echo   starting-soon.mp3  (upbeat)
echo   lobby.mp3          (upbeat)
echo   brb.mp3            (calm)
echo   ending.mp3         (calm)
echo.
pause
