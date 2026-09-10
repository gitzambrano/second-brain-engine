@echo off
chcp 65001 >nul
echo ===================================================
echo           Publicando Second Brain Atlas
echo ===================================================
echo.
python scripts\publish_site.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] A publicacao falhou com codigo %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo ===================================================
echo       Publicacao concluida com sucesso!
echo ===================================================
pause
