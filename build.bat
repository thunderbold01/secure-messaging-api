@echo off
echo ========================================
echo   CHATTING - Build EXE
echo ========================================

echo.
echo [1/3] Copiando frontend...
if not exist "frontend" mkdir frontend
xcopy /E /Y /Q "..\secure-messaging-frontend\dist\*" "frontend\" >nul 2>&1

echo [2/3] Build com PyInstaller...
pyinstaller --clean --noconfirm chatting.spec

echo.
echo [3/3] Pronto!
echo.
echo O EXE esta em: dist\CHATTING\CHATTING.exe
echo.
echo Para distribuir, copie toda a pasta dist\CHATTING\
echo para o outro computador e execute CHATTING.exe
echo.
echo IMPORTANTE: Ambos os PCs precisam estar na mesma rede
echo para as chamadas de voz/video funcionarem.
echo.
pause
