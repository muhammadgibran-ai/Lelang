@echo off
title Aplikasi Estimasi Harga Mobil Bekas Lelang - Sistem Cerdas
echo ==========================================================
echo   MENJALANKAN APLIKASI WEB ESTIMASI HARGA MOBIL LELANG
echo ==========================================================
echo.
echo Sedang meluncurkan server lokal Streamlit pada port 8566...
echo.
streamlit run app.py --server.port 8566
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Gagal menjalankan Streamlit. Pastikan library sudah terinstall.
    echo Silakan jalankan 'pip install -r requirements.txt' terlebih dahulu.
    echo.
    pause
)
