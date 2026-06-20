# Route

سیستم مدیریت ماموریت خودروهای سازمانی ویژه شبکه بهداشت و درمان رودسر.

## ویژگی‌ها

- نرم‌افزار دسکتاپ کاملاً آفلاین
- رابط کاربری مدرن، سازمانی و RTL با PySide6
- دیتابیس محلی SQLite با ایجاد خودکار فایل `database/route.db`
- CRUD رانندگان، دسته‌بندی‌ها، نقاط و ماموریت‌ها
- داشبورد آماری و جدول ماموریت‌های اخیر
- گزارش روزانه، ماهانه، راننده و مقصد
- خروجی Excel با `openpyxl`
- آماده توسعه برای مدیریت مسیرها، رزرو خودرو و نسخه تحت شبکه

## ساختار پروژه

```text
Route
├── main.py
├── database/
│   ├── db.py
│   └── route.db
├── ui/
│   ├── main_window.py
│   └── utils.py
├── pages/
│   ├── dashboard_page.py
│   ├── drivers_page.py
│   ├── locations_page.py
│   ├── missions_page.py
│   └── reports_page.py
└── assets/
    ├── fonts/
    ├── icons/
    └── style.qss
```

## اجرا

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

برای بارگذاری کاملاً آفلاین فونت، فایل‌های `Vazirmatn*.ttf` را داخل
`assets/fonts/` قرار دهید.