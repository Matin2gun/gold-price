@echo off
title 24k Gold Bullion Terminal (Iran)
echo ========================================================
echo   سامانه محاسبه ارزش واقعی و حباب شمش طلا ۲۴ عیار ایران
echo   به‌روزرسانی خودکار هر ۳۰ ثانیه
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [خطا] پایتون روی سیستم شما یافت نشد. لطفا پایتون را نصب کنید.
    pause
    exit /b
)

echo [1/2] در حال بررسی و نصب پیش‌نیازها...
pip install -r requirements.txt

echo.
echo [2/2] اجرای سرور در پورت 8000...
echo پس از اجرا، مرورگر را در آدرس http://localhost:8000 باز کنید.
echo.
python app.py
pause
