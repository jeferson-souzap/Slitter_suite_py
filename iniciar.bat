@echo off

echo.
echo Iniciando aplicativo...
echo Abra o navegador em: http://localhost:8501
echo.
python -m streamlit run home.py --server.port 8501 --server.headless false
pause
