# 🛒 Shopee Affiliate Bot — Free Automation

> สร้างวิดีโอ Shopee Affiliate อัตโนมัติ **ฟรี 100%** ด้วย Gemini API + FFmpeg + GitHub Actions + Telegram

```
Pipeline: Shopee Products → Gemini Script → FFmpeg Video → Telegram → โพสต์เอง 30 วิ
```

---

## 📋 สิ่งที่ต้องใช้ (ฟรีทั้งหมด)

| เครื่องมือ | สมัครที่ไหน | ใช้ทำอะไร |
|---|---|---|
| **Gemini API Key** | [ai.google.dev](https://ai.google.dev) | สร้าง script + hashtag |
| **Telegram Bot** | [@BotFather](https://t.me/BotFather) | รับวิดีโอบนมือถือ |
| **GitHub Account** | [github.com](https://github.com) | รัน bot ฟรีทุกวัน |
| **Shopee Affiliate** | [affiliate.shopee.co.th](https://affiliate.shopee.co.th) | ดึงสินค้า + affiliate link |
| **FFmpeg** | [ffmpeg.org](https://ffmpeg.org) | สร้างวิดีโอ |

---

## ⚡ Quick Start (5 ขั้นตอน)

### 1. Clone และ Install

```bash
git clone https://github.com/YOUR_USERNAME/shopee-affiliate-bot.git
cd shopee-affiliate-bot

pip install -r requirements.txt

# Windows — ติดตั้ง FFmpeg
winget install ffmpeg

# หรือดาวน์โหลดที่ https://ffmpeg.org/download.html
```

### 2. สร้าง Telegram Bot

1. เปิด Telegram → ค้นหา **@BotFather**
2. ส่ง `/newbot`
3. ตั้งชื่อ bot เช่น `ShopeeBot`
4. รับ **Token** เช่น `7123456789:AAH...`
5. ส่งข้อความใดก็ได้ให้ bot ของตัวเอง
6. เปิด `https://api.telegram.org/bot{TOKEN}/getUpdates`
7. หา `"chat": {"id": XXXXXXX}` ← นี่คือ **Chat ID**

### 3. สร้าง .env

```bash
cp .env.example .env
# แก้ไขด้วย editor
```

เติมค่าใน `.env`:
```env
GEMINI_API_KEY=AIzaSy...
TELEGRAM_BOT_TOKEN=7123456789:AAH...
TELEGRAM_CHAT_ID=1234567890
SHOPEE_APP_ID=...
SHOPEE_SECRET=...
```

### 4. ทดสอบรัน

```bash
# ทดสอบด้วย mock data ก่อน (ไม่ต้องใช้ Shopee API)
python main.py --test --no-telegram

# ดูวิดีโอที่ output/
```

```bash
# รันจริงกับ Telegram
python main.py --category beauty --products 3
```

### 5. Setup GitHub Actions (Auto ทุกวัน)

1. Push code ขึ้น GitHub:
   ```bash
   git init
   git add .
   git commit -m "🚀 initial setup"
   git remote add origin https://github.com/YOUR_USERNAME/shopee-affiliate-bot.git
   git push -u origin main
   ```

2. ไปที่ **Settings → Secrets and variables → Actions**

3. เพิ่ม Secrets:
   | Secret Name | ค่า |
   |---|---|
   | `GEMINI_API_KEY` | API key จาก ai.google.dev |
   | `TELEGRAM_BOT_TOKEN` | Token จาก BotFather |
   | `TELEGRAM_CHAT_ID` | Chat ID ของคุณ |
   | `SHOPEE_APP_ID` | จาก Shopee Affiliate Portal |
   | `SHOPEE_SECRET` | จาก Shopee Affiliate Portal |

4. ไปที่ **Actions** tab → เปิด workflows → รัน manual ครั้งแรก

**✅ หลังจากนี้ bot จะรันทุกวันตีสาม อัตโนมัติ!**

---

## 🔑 Shopee Affiliate API Setup

1. ไปที่ [affiliate.shopee.co.th](https://affiliate.shopee.co.th)
2. สมัคร / Login
3. ไปที่ **เครื่องมือ → API**
4. สร้าง App ใหม่
5. คัดลอก `App ID` และ `Secret`

> **ถ้ายังไม่มี Shopee Affiliate account:** bot จะใช้ mock data แทน
> (สร้างวิดีโอจากสินค้าตัวอย่างก่อน แล้วค่อยเปลี่ยน)

---

## 📱 ผลลัพธ์ที่ได้รับใน Telegram

```
┌─────────────────────────────────────┐
│  🔥 ลด 50%! ครีม Hyaluronic 100ml  │
│                                     │
│  [VIDEO 30 วิ พร้อม text overlay]  │
│                                     │
│  ✨ ลดความหยาบกร้าน                 │
│  ✨ ชุ่มชื้น 24 ชั่วโมง             │
│  ✨ 4.8⭐ ซื้อแล้ว 15,234 คน        │
│                                     │
│  💰 ก่อนหมด! กดลิงก์ด้านล่าง       │
│  🛒 https://shope.ee/xxxxx          │
│                                     │
│  #shopee #shopeeth #beauty...       │
└─────────────────────────────────────┘

📋 วิธีโพสต์ใน Shopee:
1️⃣ บันทึกวิดีโอด้านบน
2️⃣ เปิด Shopee → Live/Video
3️⃣ วาง caption → โพสต์เลย!
```

---

## ⚙️ ปรับแต่ง

### เพิ่มหมวดหมู่

แก้ใน `.env`:
```env
TARGET_CATEGORIES=beauty,fashion,electronics
```

### เปลี่ยนเวลารัน

แก้ใน `.github/workflows/daily_run.yml`:
```yaml
- cron: "0 20 * * *"  # 20:00 UTC = ตี 3 ไทย
- cron: "0 13 * * *"  # 13:00 UTC = 20:00 ไทย
```

### เพิ่มรูปสินค้า

ใส่รูปใน `src/shopee_scraper.py` → `_get_mock_products()` สำหรับสินค้าที่ต้องการ promote เอง

---

## 🆓 Free Tier Limits

| บริการ | Free Limit |
|---|---|
| Gemini API (gemini-3.8-flash) | 500 req/วัน, 10 req/นาที |
| GitHub Actions | 2,000 นาที/เดือน |
| Telegram Bot API | ไม่จำกัด |
| Shopee Affiliate API | ไม่จำกัด |

> 3 สินค้า/วัน ใช้ ~6 API calls/วัน → **ต่ำกว่า limit มาก** ✅

---

## 🗂️ โครงสร้าง Project

```
shopee-affiliate-bot/
├── main.py                    # Entrypoint หลัก
├── src/
│   ├── shopee_scraper.py      # ดึงสินค้าจาก Shopee API
│   ├── gemini_generator.py    # สร้าง script + hashtag
│   ├── video_creator.py       # FFmpeg สร้างวิดีโอ
│   ├── telegram_sender.py     # ส่งวิดีโอไปยัง Telegram
│   └── main.py               # Pipeline orchestrator
├── .github/
│   └── workflows/
│       └── daily_run.yml      # GitHub Actions schedule
├── assets/
│   ├── fonts/                 # Thai fonts
│   └── music/                 # Background music
├── output/                    # วิดีโอที่สร้างแล้ว
├── .env.example               # Template config
├── requirements.txt
└── README.md
```
