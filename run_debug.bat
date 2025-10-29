@echo off
echo ========================================
echo OPM Editor - DEBUG MODE
echo ========================================
echo.
echo Aplikace běží v debug režimu s podrobným logováním.
echo Veškeré chyby a kroky se zobrazí v této konzoli.
echo.
echo Pokud program spadne, NEUZAVÍREJTE TOTO OKNO!
echo Zkopírujte log výše a pošlete jej.
echo.
echo ========================================
echo.

python -u app.py

echo.
echo ========================================
echo Program byl ukončen.
echo ========================================
echo.
pause

