# 🎓 EDU MEMORY

Telegram orqali maktab sinfining davomatini yuritish va ota-onalarga avtomatik davomat hisobotlarini yuborish tizimi.

**Texnologiyalar:** Python 3.11+, aiogram 3.x, SQLite (SQLAlchemy async), APScheduler, python-dotenv.

## Ishga tushirish

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
# .env ichiga BOT_TOKEN va ADMIN_IDS ni yozing
python main.py
```

## Sozlamalar (`.env`)

| O‘zgaruvchi | Tavsif |
|---|---|
| `BOT_TOKEN` | @BotFather bergan token (majburiy) |
| `ADMIN_IDS` | Adminlar Telegram ID'lari, vergul bilan (majburiy). ID ni @userinfobot orqali bilib oling |
| `DATABASE_URL` | Standart: `sqlite+aiosqlite:///attendance.db` |
| `TIMEZONE` | Standart: `Asia/Tashkent` |
| `WEEKLY_REPORT_ENABLED` | Haftalik hisobot (standart `true`) |
| `REPORT_HOUR`, `REPORT_MINUTE` | Haftalik hisobot vaqti, shanba (standart 18:00) |
| `MONTHLY_REPORT_ENABLED` | Oylik hisobot (standart `true`) |
| `MONTHLY_REPORT_HOUR` | Oylik hisobot soati, oyning oxirgi kuni (standart 19) |

## Qanday ishlaydi

**O‘qituvchi (admin):**
- `/davomat` — bugungi sana bilan barcha o‘quvchilar chiqadi. Boshida hamma ⚪ Belgilanmagan. Tugma bosilganda status aylanadi: ⚪ → 🟢 Bor → 🔴 Yo‘q → 🟡 Sababli → 🟢 Bor. «💾 Saqlash» faqat hamma o‘quvchi belgilangandan keyin ishlaydi (adashib noto‘g‘ri davomat saqlanmasin). Bugungi yozuv bor bo‘lsa, yangilanadi (dublikat bo‘lmaydi).
- Belgilar har bosishda bazaga qoralama sifatida yoziladi, shuning uchun bot restart bo‘lsa ham yo‘qolmaydi.
- `/manage` (yoki `🛠 Boshqarish`) — o‘quvchini tanlab ismini o‘zgartirish yoki o‘chirish (o‘chirishda davomat va ota-ona bog‘lanishlari ham o‘chadi, tasdiq so‘raladi).
- `/add_student` (yoki `/add_student Ali Valiyev`) — o‘quvchi qo‘shadi, unikal ID kod beradi (masalan `A7K92X`).
- `/students` — o‘quvchilar va ularning kodlari.

**Ota-ona:**
- `/start` → farzandning ID kodini kiritadi → bog‘lanadi. Bir nechta farzand qo‘shish mumkin (`➕ Farzand qo‘shish`).
- `📊 Davomat` — faqat o‘z farzandlarining statistikasi.
- Har shanba 18:00 (Asia/Tashkent) va har oyning oxirgi kuni avtomatik hisobot keladi.
- Hisobot yuborishda botni bloklaganlar yoki xatolik bo‘lsa, adminlarga qisqa xulosa boradi.

## Scheduler va dublikatdan himoya
- APScheduler bot bilan bir event loop'da ishlaydi, polling'ga xalaqit bermaydi.
- Bot qayta ishga tushganda scheduler avtomatik ishga tushadi. Oxirgi 24 soat ichida o‘tkazib yuborilgan hisobot bo‘lsa, u qayta yuboriladi.
- `report_logs` jadvali (`kind + period + chat_id` unikal) bir hisobotning ikki marta ketishiga yo‘l qo‘ymaydi.

## Xavfsizlik
- Token faqat `.env` da, `.env` va `*.db` `.gitignore` da.
- Davomat va o‘quvchi boshqaruvi faqat `ADMIN_IDS` uchun (xabar va callback darajasida).
- Barcha SQL so‘rovlar parametrlangan (SQLAlchemy), SQL injection yo‘q.
- Ota-ona faqat `parents` jadvalida bog‘langan farzandlarini ko‘radi.
- Student kodini taxmin qilishga urinishlar cheklangan (10 daqiqada 5 xato).

## Tuzilma

```
edu_memory/
├── main.py                # kirish nuqtasi
├── app/
│   ├── config.py          # .env sozlamalari
│   ├── models.py          # students, parents, attendance, attendance_drafts, report_logs
│   ├── database.py        # engine, foreign key, init
│   ├── repository.py      # barcha DB amallari
│   ├── keyboards.py       # inline va reply klaviaturalar
│   ├── texts.py           # matnlar, statuslar
│   ├── middleware.py      # DB sessiya
│   ├── reports.py         # haftalik/oylik hisobot
│   ├── scheduler.py       # APScheduler + catch-up
│   └── handlers/{admin,parent}.py
├── legacy/                # eski telebot loyihasi (arxiv)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Eslatma
Eski loyihadagi token ochiq yozilgan edi. Uni @BotFather orqali **bekor qiling (/revoke)** va yangi token oling.
