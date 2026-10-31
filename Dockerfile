# Dockerfile สำหรับรัน Shopee Clip Maker AI บน Cloud (Render, Railway, Cloud Run)
FROM python:3.12-slim

# ตั้งค่าไม่ให้บัฟเฟอร์ stdout/stderr
ENV PYTHONUNBUFFERED=1

# ติดตั้ง FFmpeg และฟอนต์ภาษาไทยสำหรับ Render ข้อความบนวิดีโอ
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-thai-tlwg \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ติดตั้ง Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกซอร์สโค้ดและ Assets
COPY . .

# สร้างโฟลเดอร์สำหรับ Output และ Uploads
RUN mkdir -p output inputs/web_uploads

# Port สำหรับ Cloud Provider (Render / Railway / Cloud Run กำหนด PORT ผ่าน ENV)
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn web.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
