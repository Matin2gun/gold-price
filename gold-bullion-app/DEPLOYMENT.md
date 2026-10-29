# راهنمای کامل اتصال اپلیکیشن به دامنه شخصی و استقرار ۲۴ ساعته

این راهنما گام‌به‌گام نحوه استقرار برنامه و اتصال آن به دامنه اینترنتی دلخواه (مانند `gold.yourdomain.com` یا `yourdomain.ir`) را توضیح می‌دهد تا بدون وقفه و هر ۳۰ ثانیه یک‌بار نرخ‌ها را به‌روزرسانی کند.

---

## فهرست روش‌های استقرار
1. [روش ۱: استقرار با داکر و Nginx روی سرور مجازی (VPS) - توصیه شده](#روش-۱-استقرار-با-داکر-و-nginx-روی-سرور-مجازی-vps)
2. [روش ۲: اتصال دامین محلی با Cloudflare Tunnel (بدون نیاز به خرید سرور)](#روش-۲-اتصال-دامین-محلی-با-cloudflare-tunnel)
3. [روش ۳: انتشار روی پلتفرم‌های ابری رایگان (Render / Railway)](#روش-۳-انتشار-روی-پلتفرمهای-ابری-render--railway)

---

## روش ۱: استقرار با داکر و Nginx روی سرور مجازی (VPS)

این روش مطمئن‌ترین شیوه برای کارکرد ۲۴ ساعته و اتصال مستقیم دامین با گواهی امنیتی SSL (HTTPS) رایگان است.

### گام اول: انتقال فایل‌ها به سرور
فایل‌های پوشه پروژه (`gold-bullion-app`) را به سرور لینوکسی خود منتقل کنید:
```bash
scp -r gold-bullion-app user@your-vps-ip:/home/user/
```

### گام دوم: اجرای برنامه با Docker
روی سرور دستورات زیر را اجرا کنید:
```bash
cd /home/user/gold-bullion-app
docker compose up -d --build
```
اکنون برنامه روی پورت 8000 سرور به صورت پس‌زمینه و دائم در حال اجرا است.

### گام سوم: تنظیم DNS دامنه
در پنل مدیریت دامنه خود (مثلاً Cloudflare یا ایرنیک یا رجیسترار):
- یک رکورد از نوع **A Record** بسازید.
- نام زیردامنه را مشخص کنید (مثلاً `gold` یا `@`).
- مقدار IP را برابر با IP سرور VPS خود قرار دهید.

### گام چهارم: پیکربندی Nginx و باز ارسال WebSocket
فایل تنظیمات Nginx را ایجاد کنید:
```bash
sudo nano /etc/nginx/sites-available/gold.yourdomain.com
```

محتوای زیر را درون آن قرار دهید (نام دامنه خود را جایگزین کنید):
```nginx
server {
    server_name gold.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        # تنظیمات حیاتی وب‌سوکت برای آپدیت‌های زنده ۳۰ ثانیه‌ای
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # جلوگیری از تایم‌اوت وب‌سوکت
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

سپس فعال‌سازی و ری‌استارت Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/gold.yourdomain.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### گام پنجم: فعال‌سازی SSL رایگان با Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d gold.yourdomain.com
```
اکنون داشبورد شما با آدرس امن `https://gold.yourdomain.com` در سراسر جهان در دسترس است و هر ۳۰ ثانیه بدون وقفه به‌روز می‌شود!

---

## روش ۲: اتصال دامین محلی با Cloudflare Tunnel (رایگان، بدون نیاز به VPS)

اگر می‌خواهید برنامه روی رایانه شخصی یا لپ‌تاپ شما اجرا شود ولی از طریق یک دامنه رسمی اینترنتی باز شود:
1. در پنل Cloudflare وارد بخش **Zero Trust > Networks > Tunnels** شوید.
2. یک Tunnel جدید بسازید و دستور نصب `cloudflared` را روی سیستم خود اجرا کنید.
3. در تنظیمات Public Hostname:
   - ساب‌دامین: `gold.yourdomain.com`
   - سرویس: `HTTP`
   - آدرس: `localhost:8000`
4. بلافاصله و بدون نیاز به IP استاتیک، دامنه شما به برنامه محلی متصل شده و دارای SSL خودکار می‌شود!

---

## روش ۳: انتشار روی پلتفرم‌های ابری (Render / Railway)

1. پروژه را روی حساب GitHub خود در یک مخزن (Repository) قرار دهید.
2. وارد [Render.com](https://render.com) یا [Railway.app](https://railway.app) شوید.
3. گزینه **New Web Service** را انتخاب کرده و مخزن گیت‌هاب را متصل کنید.
4. تنظیمات ساخت:
   - **Environment:** Docker (خودکار از Dockerfile پروژه استفاده می‌کند)
   - **Port:** 8000
5. پس از ساخت، وارد بخش **Settings > Custom Domains** شوید و دامنه دلخواه خود را وارد کنید.
6. رکورد CNAME ارائه شده را در پنل دامنه خود ست کنید.

---

## بررسی صحت کارکرد سرویس (Health Check)
برای بررسی آنلاین بودن و سلامت موتور ۳۰ ثانیه‌ای می‌توانید آدرس زیر را فراخوانی کنید:
```
https://gold.yourdomain.com/api/health
```
پاسخ نمونه:
```json
{
  "status": "healthy",
  "loop_running": true,
  "active_ws_clients": 3,
  "seconds_since_last_update": 12.4
}
```
