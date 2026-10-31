"""
web/server.py
-------------
FastAPI Web Application สำหรับ Shopee Affiliate Video Maker (MVP)
รองรับทั้งการเลือกสินค้าจาก Verified Catalog และการอัปโหลดสินค้าเอง
"""
import os
import sys
import json
import uuid
import time
import shutil
import logging
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# โหลด .env
load_dotenv()

# ให้โปรเจกต์สามารถ import จาก src ได้
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.shopee_scraper import Product
from src.gemini_generator import GeminiContentGenerator, VideoContent
from src.video_creator import FFmpegVideoCreator
from src.trend_researcher import VERIFIED_PRODUCT_CATALOG

OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"

# ตั้งค่า Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shopee_web")

app = FastAPI(title="Shopee Clip Maker AI", version="1.0.0")

# สร้างโฟลเดอร์ที่จำเป็น
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = BASE_DIR / "inputs" / "web_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Mount Static Files
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Instances
script_generator = GeminiContentGenerator()
video_creator = FFmpegVideoCreator()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """หน้าแรกของเว็บ MVP"""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"catalog": VERIFIED_PRODUCT_CATALOG}
    )


@app.get("/api/catalog")
async def get_catalog(category: Optional[str] = None):
    """ดึงรายการสินค้าแนะนำจาก Verified Catalog"""
    items = VERIFIED_PRODUCT_CATALOG
    if category and category != "all":
        items = [p for p in items if p.get("category") == category]
    return {"success": True, "count": len(items), "products": items}


@app.post("/api/generate-catalog")
async def generate_catalog(data: dict):
    """
    สร้างคลิปจากสินค้าใน Verified Catalog
    Payload: { "product_id": "mizumi_uv", "tone": "friend", "affiliate_url": "" }
    """
    product_id = data.get("product_id")
    tone = data.get("tone", "friend")
    affiliate_url = data.get("affiliate_url", "").strip()

    # ค้นหาสินค้าจาก Catalog
    item = next((p for p in VERIFIED_PRODUCT_CATALOG if p["id"] == product_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้าในระบบ")

    custom_link = affiliate_url if affiliate_url else item["affiliate_link"]

    product = Product(
        item_id=f"web_{item['category']}_{item['id']}",
        shop_id="official_mall",
        name=item["name"],
        price=0.0,
        original_price=0.0,
        discount_percent=0,
        image_urls=item["images"],
        affiliate_link=custom_link,
        category=item["category"],
        rating=float(item.get("rating", 4.9)),
        sold_count=int(item.get("sold_count", 50000)),
        description=item["highlight"],
    )

    return _process_video_generation(product, item["images"], tone)


@app.post("/api/generate-custom")
async def generate_custom(
    name: str = Form(...),
    category: str = Form("general"),
    highlight: str = Form(""),
    tone: str = Form("friend"),
    affiliate_url: str = Form(""),
    images: List[UploadFile] = File(...),
):
    """
    สร้างคลิปจากสินค้าที่ผู้ใช้อัปโหลดเอง
    """
    if not name.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อสินค้า")
    if not images or len(images) == 0:
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดรูปสินค้าอย่างน้อย 1 รูป")

    # บันทึกรูปที่อัปโหลด
    session_id = f"custom_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    target_dir = UPLOAD_DIR / session_id
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_images = []
    for i, file in enumerate(images[:3]):
        ext = Path(file.filename).suffix or ".jpg"
        save_path = target_dir / f"img_{i}{ext}"
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        saved_images.append(str(save_path))

    # ถ้าอัปโหลดมาภาพเดียว ให้ทำซ้ำจนครบ 3 ภาพเพื่อความลื่นไหลของสไลด์
    while len(saved_images) < 3:
        saved_images.append(saved_images[0])

    custom_link = affiliate_url.strip() if affiliate_url.strip() else f"https://shopee.co.th/search?keyword={name}"

    product = Product(
        item_id=f"custom_{int(time.time())}",
        shop_id="user_custom",
        name=name.strip(),
        price=0.0,
        original_price=0.0,
        discount_percent=0,
        image_urls=saved_images,
        affiliate_link=custom_link,
        category=category,
        rating=4.9,
        sold_count=10000,
        description=highlight.strip() if highlight.strip() else "สินค้าแนะนำคุณภาพดี สั่งได้เลย",
    )

    return _process_video_generation(product, saved_images, tone)


def _process_video_generation(product: Product, image_paths: list, tone: str):
    """ประมวลผลการสร้างบทและตัดต่อคลิป"""
    try:
        start_time = time.time()
        logger.info(f"🚀 เริ่มต้นสร้างวิดีโอสำหรับ: {product.name[:30]}...")

        # 1. ให้ Gemini เขียนสคริปต์
        content: VideoContent = script_generator.generate_video_content(product)

        # 2. ปรับแต่ง CTA และ Link
        clean_name = product.name.split()[0] if product.name else "สินค้า"
        content.caption = f"แนะนำเลย! {product.name[:45]}\nดูในตะกร้าส้มซ้ายล่างได้เลย 🛒\n\n📌 พิกัด: {product.affiliate_link}"
        
        # 3. เรนเดอร์วิดีโอด้วย FFmpeg
        # แปลง relative path เป็น absolute path
        abs_images = [str(Path(p).resolve()) if not os.path.isabs(p) else p for p in image_paths]
        result = video_creator.create_video(product, content, abs_images)

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"✅ สร้างวิดีโอสำเร็จใน {elapsed} วินาที: {result.video_path}")

        # บันทึก metadata เพื่อดึงประวัติภายหลัง
        meta_filename = Path(result.video_path).stem + "_meta.json"
        meta_path = OUTPUT_DIR / meta_filename
        metadata = {
            "product_name": product.name,
            "category": product.category,
            "video_filename": Path(result.video_path).name,
            "thumbnail_filename": Path(result.thumbnail_path).name,
            "video_url": f"/output/{Path(result.video_path).name}",
            "thumbnail_url": f"/output/{Path(result.thumbnail_path).name}",
            "hook": content.hook,
            "cta": content.cta,
            "caption": content.caption,
            "hashtags": content.hashtags,
            "affiliate_url": product.affiliate_link,
            "duration": result.duration,
            "file_size_mb": result.file_size_mb,
            "render_time_seconds": elapsed,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": "สร้างวิดีโอเรียบร้อยแล้ว",
            **metadata
        }

    except Exception as e:
        logger.exception("เกิดข้อผิดพลาดในการสร้างวิดีโอ")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการสร้างวิดีโอ: {str(e)}")


@app.get("/api/history")
async def get_history():
    """ดึงรายการประวัติวิดีโอที่เคยสร้างไว้"""
    history = []
    for meta_file in sorted(OUTPUT_DIR.glob("*_meta.json"), key=os.path.getmtime, reverse=True):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                history.append(data)
        except Exception:
            continue
    return {"success": True, "count": len(history), "history": history[:20]}


@app.get("/download/{filename}")
async def download_file(filename: str):
    """ดาวน์โหลดไฟล์วิดีโอโดยตรง"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="video/mp4"
    )


if __name__ == "__main__":
    import uvicorn
    # รันบนพอร์ต 8000
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=True)
