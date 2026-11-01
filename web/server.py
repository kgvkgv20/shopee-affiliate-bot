"""
web/server.py
-------------
FastAPI Web Application สำหรับ Shopee Affiliate Video Maker (Pro Feature Pack)
ฟีเจอร์ครบครัน:
  1. สร้างคลิปทีละรายการ หรือโหมด Batch สร้างหลายคลิปพร้อมกัน
  2. เลือก Template สไตล์วิดีโอ (Shopee Clean / Neon Pop / Minimal Aesthetic)
  3. เสียงพากย์ AI ภาษาไทยสมจริง (Thai Neural TTS - หญิง/ชาย)
  4. เพลงพื้นหลัง BGM (Cheerful / Upbeat)
  5. ดึงข้อมูลจากลิงก์ Shopee อัตโนมัติ (Smart Link Extractor)
  6. ดูตัวอย่างและแก้ไขสคริปต์/บทพูดก่อนกดเรนเดอร์ (Preview & Edit Script)
  7. ส่งวิดีโอเข้า Discord / Telegram ได้ทันที
"""
import os
import sys
import json
import asyncio
import uuid
import time
import shutil
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import unquote, urlparse, quote_plus
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
from src.tts_generator import generate_voiceover
from src.discord_sender import DiscordSender
from src.catalog_manager import CatalogManager
from src.image_handler import extract_shopee_product_data, download_image_to_file
from src.shopee_extractor import extract_shopee_product_direct
from src.telegram_sender import TelegramSender
from src.phone_sync import phone_sync_mgr
from src.google_flow_exporter import generate_google_flow_kit
from src.scheduler_service import (
    get_local_ip,
    load_scheduler_config,
    save_scheduler_config,
    record_scheduler_run,
    AutoSchedulerWorker,
)

OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"

# ตั้งค่า Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shopee_web")

app = FastAPI(title="Shopee Clip Maker AI", version="2.0.0")

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
catalog_mgr = CatalogManager()

scheduler_worker: Optional[AutoSchedulerWorker] = None


@app.on_event("startup")
async def startup_event():
    """เริ่มต้น Background Scheduler เมื่อเปิดเว็บ"""
    global scheduler_worker
    scheduler_worker = AutoSchedulerWorker(runner_callback=execute_scheduled_routine)
    asyncio.create_task(scheduler_worker.start())


@app.on_event("shutdown")
def shutdown_event():
    """หยุด Background Scheduler เมื่อปิดเซิร์ฟเวอร์"""
    global scheduler_worker
    if scheduler_worker:
        scheduler_worker.stop()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """หน้าแรกของเว็บ Shopee Clip Maker"""
    all_products = catalog_mgr.get_all_products(source="all")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"catalog": all_products}
    )


@app.get("/api/catalog")
async def get_catalog(
    category: Optional[str] = None,
    query: Optional[str] = None,
    min_commission: int = 0,
    source: str = "all",
    video_status: str = "all",
):
    """ดึงรายการสินค้าแนะนำจาก High Commission Database พร้อมค้นหา กรอง และสถิติสถานะวิดีโอ"""
    items = catalog_mgr.get_all_products(
        category=category,
        query=query,
        min_commission=min_commission,
        source=source,
        video_status_filter=video_status,
    )
    stats = catalog_mgr.get_video_stats()
    return {
        "success": True,
        "count": len(items),
        "products": items,
        "stats": stats,
    }


@app.get("/api/my-products")
async def get_my_products(video_status: str = "all"):
    """ดึงรายการสินค้าส่วนตัวของผู้ใช้ (My Products)"""
    items = catalog_mgr.get_all_products(source="my_products", video_status_filter=video_status)
    stats = catalog_mgr.get_video_stats()
    return {"success": True, "count": len(items), "products": items, "stats": stats}


@app.get("/api/product/{product_id}/caption")
async def get_product_caption(product_id: str):
    """ดึงหรือสร้างแคปชันพร้อมโพสต์ TikTok / Shopee Video สำหรับสินค้า"""
    all_products = catalog_mgr.get_all_products(source="all")
    target = next((p for p in all_products if str(p.get("id")) == str(product_id)), None)
    if not target:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้า")
    caption = target.get("social_caption") or catalog_mgr.generate_social_caption(target)
    return {
        "success": True,
        "product_id": product_id,
        "product_name": target.get("name"),
        "caption": caption
    }


@app.get("/api/phone/status")
async def get_phone_status():
    """ตรวจสอบสถานะการเชื่อมต่อมือถือ Android ผ่าน ADB"""
    available = phone_sync_mgr.is_adb_available()
    devices = phone_sync_mgr.get_connected_devices() if available else []
    ready_count = sum(1 for d in devices if d.get("is_ready"))
    return {
        "success": True,
        "adb_available": available,
        "adb_path": phone_sync_mgr.adb_path,
        "devices": devices,
        "total_devices": len(devices),
        "ready_count": ready_count,
        "is_connected": ready_count > 0
    }


@app.post("/api/phone/push")
async def push_video_to_phone_api(data: dict):
    """
    ผลักไฟล์วิดีโอเข้ามือถือ Android:
    Payload: { "video_filename": "...", "caption": "...", "open_shopee": true }
    """
    video_filename = data.get("video_filename", "").strip()
    caption = data.get("caption", "").strip()
    open_shopee = data.get("open_shopee", True)

    if not video_filename:
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อไฟล์วิดีโอ")

    video_path = OUTPUT_DIR / video_filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์วิดีโอ {video_filename} ในโฟลเดอร์ output")

    result = phone_sync_mgr.push_video_to_phone(
        local_video_path=str(video_path),
        caption=caption,
        open_shopee=open_shopee
    )
    return result


@app.post("/api/phone/test-shopee")
async def test_shopee_phone():
    """สั่งเปิดแอป Shopee บนมือถือเพื่อทดสอบการเชื่อมต่อ"""
    return phone_sync_mgr.trigger_shopee_app()


@app.get("/api/google-flow/{product_id}")
async def get_google_flow_data(product_id: str):
    """สร้าง Prompt และชุดข้อมูลพร้อมโยนเข้า Google Flow / Veo สำหรับสินค้า"""
    all_products = catalog_mgr.get_all_products(source="all")
    target = next((p for p in all_products if str(p.get("id")) == str(product_id)), None)
    if not target:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้า")
    kit = generate_google_flow_kit(target)
    return {
        "success": True,
        "kit": kit
    }


@app.get("/api/sync/status")
async def get_sync_status():
    """ดึงสถานะและรายการลิงก์ใน my_links.txt และสถิติภาพรวม"""
    links = catalog_mgr.parse_links_file()
    stats = catalog_mgr.get_video_stats()
    raw_content = catalog_mgr.get_links_file_content()
    return {
        "success": True,
        "links": links,
        "total_links": len(links),
        "raw_content": raw_content,
        "stats": stats,
    }


@app.post("/api/sync/links-file")
async def save_links_file(data: dict):
    """บันทึกเนื้อหาลงไฟล์ my_links.txt"""
    content = data.get("content", "")
    ok = catalog_mgr.save_links_file_content(content)
    if not ok:
        raise HTTPException(status_code=500, detail="ไม่สามารถบันทึกไฟล์ได้")
    return {"success": True, "message": "บันทึกไฟล์ my_links.txt เรียบร้อยแล้ว"}


@app.post("/api/sync/run")
async def run_sync_links(data: dict):
    """
    ดึงข้อมูลและรูปภาพจริงอัตโนมัติจาก Shopee เพื่อทำคลิปล่าสุด (Auto-Sync)
    Payload: { "source": "file" | "urls", "urls": ["https://..."] }
    """
    source = data.get("source", "file")
    urls_to_process = []

    if source == "file":
        parsed = catalog_mgr.parse_links_file()
        for item in parsed:
            urls_to_process.append({"url": item["url"], "name_hint": item["name_hint"]})
    elif source == "urls":
        raw_urls = data.get("urls", [])
        for u in raw_urls:
            if isinstance(u, str) and u.strip():
                urls_to_process.append({"url": u.strip(), "name_hint": ""})
            elif isinstance(u, dict) and u.get("url"):
                urls_to_process.append({"url": u["url"].strip(), "name_hint": u.get("name_hint", "")})

    if not urls_to_process:
        raise HTTPException(status_code=400, detail="ไม่พบลิงก์สำหรับดึงข้อมูล กรุณาใส่ลิงก์ Shopee อย่างน้อย 1 ลิงก์")

    results = []
    logger.info(f"🔄 เริ่มต้นดึงข้อมูลสินค้าล่าสุดจาก Shopee {len(urls_to_process)} รายการ...")

    for target in urls_to_process:
        url = target["url"]
        name_hint = target["name_hint"]
        try:
            # ใช้ Playwright Direct Extractor ดึงภาพแท้และชื่อจริง
            extracted = await extract_shopee_product_direct(url)

            # ถ้า Direct ได้ภาพไม่ครบ ลอง Fallback
            if not extracted.get("has_real_images") or len(extracted.get("local_images", [])) == 0:
                fb = extract_shopee_product_data(url)
                if fb.get("has_real_images"):
                    extracted["local_images"] = fb["local_images"]
                    extracted["has_real_images"] = True

            product_name = extracted.get("name") or name_hint or "สินค้า Shopee แนะนำ"
            images = extracted.get("local_images", [])

            # บันทึกเข้า 'สินค้าของฉัน'
            item_data = {
                "name": product_name,
                "brand": extracted.get("brand", "ร้านแนะนำ"),
                "category": extracted.get("category", "general"),
                "commission_rate": "25%",
                "commission_badge": "My Pick 25%",
                "price_thb": 0.0,
                "shop_type": "ร้านแนะนำ",
                "highlight": "สินค้าขายดีคุณภาพสูง สั่งซื้อผ่านตะกร้าส้ม",
                "images": images,
                "affiliate_link": extracted.get("affiliate_url", url),
                "rating": 4.9,
                "sold_count": 10000,
            }
            saved = catalog_mgr.add_my_product(item_data)
            results.append(saved)
        except Exception as e:
            logger.error(f"Sync failed for {url}: {e}")

    stats = catalog_mgr.get_video_stats()
    return {
        "success": True,
        "count": len(results),
        "message": f"ดึงข้อมูลและรูปภาพสินค้าสำเร็จ {len(results)} รายการ พร้อมทำคลิปได้ทันที!",
        "products": results,
        "stats": stats,
    }


@app.post("/api/crawler/search")
async def crawler_search_api(data: dict):
    """
    บอทค้นหาสินค้า Shopee อัตโนมัติผ่าน Search Engine Index
    ค้นหาลิงก์ตรงปก ดึงภาพแท้ 1024x1024 และเพิ่มเข้าคลัง 'สินค้าของฉัน' ให้อัตโนมัติ
    Payload: { "keyword": "กันแดด MizuMi", "limit": 2, "category": "beauty" }
    """
    from src.search_crawler import crawl_and_import_products

    keyword = data.get("keyword", "").strip()
    limit = int(data.get("limit", 2))
    category = data.get("category", "general")

    if not keyword:
        raise HTTPException(status_code=400, detail="กรุณาระบุคำค้นหา เช่น ชื่อสินค้า หรือแบรนด์")

    res = await crawl_and_import_products(keyword=keyword, max_products=limit, category=category)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "ไม่พบสินค้าสำหรับคำค้นหานี้"))

    stats = catalog_mgr.get_video_stats()
    return {
        "success": True,
        "count": res.get("count", 0),
        "message": res.get("message"),
        "products": res.get("products", []),
        "stats": stats,
    }


@app.get("/api/crawler/presets")
async def crawler_presets_api():
    """ดึงรายการ Preset คำค้นหาสินค้าขายดีตามหมวดหมู่"""
    from src.search_crawler import CATEGORY_PRESET_KEYWORDS
    return {
        "success": True,
        "presets": CATEGORY_PRESET_KEYWORDS
    }


@app.post("/api/my-products")
async def add_my_product(data: dict):
    """บันทึกสินค้าเข้าหมวด 'สินค้าของฉัน'"""
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อสินค้า")
    saved = catalog_mgr.add_my_product(data)
    return {"success": True, "message": "บันทึกสินค้าเรียบร้อยแล้ว", "product": saved}


@app.delete("/api/my-products/{product_id}")
async def delete_my_product(product_id: str):
    """ลบสินค้าออกจากหมวด 'สินค้าของฉัน'"""
    ok = catalog_mgr.delete_my_product(product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้า")
    return {"success": True, "message": "ลบสินค้าเรียบร้อยแล้ว"}


@app.get("/api/template/download")
async def download_excel_template(format: str = "xlsx"):
    """
    ดาวน์โหลดไฟล์ตัวอย่าง Excel (.xlsx) หรือ CSV สำหรับใช้กรอกข้อมูลสินค้าเพื่อนำเข้า
    """
    from src.excel_importer import create_excel_template
    template_dir = BASE_DIR / "data" / "templates"
    xlsx_file = template_dir / "shopee_products_template.xlsx"
    csv_file = template_dir / "shopee_products_template.csv"

    # ถ้ายังไม่มีไฟล์ ให้สร้างใหม่
    if not xlsx_file.exists() or not csv_file.exists():
        create_excel_template()

    fmt = format.lower().strip()
    if fmt == "csv":
        return FileResponse(
            path=str(csv_file),
            filename="shopee_products_template.csv",
            media_type="text/csv; charset=utf-8",
        )
    else:
        return FileResponse(
            path=str(xlsx_file),
            filename="shopee_products_template.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


@app.post("/api/import/excel")
async def import_excel_api(
    file: UploadFile = File(...),
    auto_fetch_images: bool = Form(True)
):
    """
    นำเข้าสินค้าจากไฟล์ Excel (.xlsx) หรือ CSV เข้าสู่ 'สินค้าของฉัน' พร้อมติดสถานะ 'รอทำคลิป'
    """
    from src.excel_importer import parse_and_import_excel
    filename = file.filename or "import.xlsx"
    ext = Path(filename).suffix.lower()

    if ext not in [".xlsx", ".csv", ".txt"]:
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์นามสกุล .xlsx หรือ .csv เท่านั้น")

    temp_id = uuid.uuid4().hex[:8]
    temp_path = UPLOAD_DIR / f"temp_import_{temp_id}{ext}"
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        # รันการนำเข้าใน worker thread เพื่อไม่ให้บล็อก
        result = await asyncio.to_thread(
            parse_and_import_excel,
            str(temp_path),
            auto_fetch_images=auto_fetch_images
        )
        return result
    except Exception as e:
        logger.error(f"Excel import error: {e}")
        raise HTTPException(status_code=500, detail=f"นำเข้าไฟล์ไม่สำเร็จ: {str(e)}")
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


@app.post("/api/catalog/import")
async def import_csv(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
):
    """นำเข้าสินค้าจำนวนมากจากไฟล์ CSV หรือข้อความ CSV"""
    content = ""
    if file:
        file_bytes = await file.read()
        content = file_bytes.decode("utf-8", errors="replace")
    elif csv_text:
        content = csv_text

    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูล CSV สำหรับนำเข้า")

    imported = catalog_mgr.import_from_csv(content)
    return {
        "success": True,
        "count": len(imported),
        "message": f"นำเข้าสินค้าสำเร็จ {len(imported)} รายการ",
        "products": imported
    }


@app.post("/api/parse-shopee-url")
async def parse_shopee_url(data: dict):
    """
    ดึงชื่อสินค้า หมวดหมู่ และรูปภาพจริงอัตโนมัติจากลิงก์ Shopee (รองรับทั้ง Full URL และ Short Links)
    Payload: { "url": "https://shopee.co.th/..." }
    """
    raw_url = data.get("url", "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="กรุณาระบุลิงก์ Shopee")

    try:
        # 1. ลองดึงข้อมูลลึกและรูปจริง 100% ตรงปกผ่าน Direct Web Extractor (Playwright Edge)
        extracted = await extract_shopee_product_direct(raw_url)
        
        # 2. ถ้ายังไม่ได้รูป ลอง Fallback ไปยัง URL Query Parameter Extractor
        if not extracted.get("has_real_images") or len(extracted.get("local_images", [])) == 0:
            fb = extract_shopee_product_data(raw_url)
            if fb.get("has_real_images"):
                extracted["local_images"] = fb["local_images"]
                extracted["cdn_urls"] = fb["cdn_urls"]
                extracted["has_real_images"] = True
                if extracted.get("name") in ["สินค้า Shopee คุณภาพดี", "error", "verify", "Shopee"]:
                    extracted["name"] = fb["name"]

        return {
            "success": True,
            "name": extracted.get("name", "สินค้า Shopee คุณภาพดี"),
            "category": extracted.get("category", "general"),
            "affiliate_url": extracted.get("affiliate_url", raw_url),
            "clean_url": extracted.get("clean_url", raw_url),
            "images": extracted.get("local_images", []),
            "cdn_urls": extracted.get("cdn_urls", []),
            "has_real_images": extracted.get("has_real_images", False),
        }
    except Exception as e:
        logger.warning(f"Parse Shopee URL failed: {e}")
        try:
            fb = extract_shopee_product_data(raw_url)
            return {
                "success": True,
                "name": fb.get("name", "สินค้า Shopee แนะนำ"),
                "category": fb.get("category", "general"),
                "affiliate_url": fb.get("clean_url", raw_url),
                "images": fb.get("local_images", []),
                "cdn_urls": fb.get("cdn_urls", []),
                "has_real_images": fb.get("has_real_images", False),
            }
        except Exception:
            return {
                "success": True,
                "name": "สินค้า Shopee แนะนำ",
                "category": "general",
                "affiliate_url": raw_url,
                "images": [],
                "has_real_images": False,
            }


@app.post("/api/download-image-url")
async def download_image_url(data: dict):
    """
    ดาวน์โหลดรูปภาพจาก URL (เช่น ภาพจาก Shopee, เว็บไซต์ร้านค้า) มาเก็บไว้ในเครื่อง
    Payload: { "url": "https://..." }
    """
    img_url = data.get("url", "").strip()
    if not img_url:
        raise HTTPException(status_code=400, detail="กรุณาระบุ Image URL")

    saved_path = download_image_to_file(img_url, prefix="custom_url")
    if not saved_path:
        raise HTTPException(status_code=400, detail="ไม่สามารถดาวน์โหลดรูปภาพจาก URL ที่ระบุได้")

    return {
        "success": True,
        "message": "ดาวน์โหลดรูปภาพสำเร็จ",
        "image_path": saved_path,
        "image_url": f"/{saved_path}"
    }


@app.post("/api/generate-script")
async def generate_script(data: dict):
    """
    สร้างบทสคริปต์ล่วงหน้าเพื่อให้ผู้ใช้ดูและแก้ไขก่อนกด Render
    Payload: { "product_id": "...", "name": "...", "category": "...", "highlight": "...", "tone": "friend" }
    """
    product_id = data.get("product_id")
    tone = data.get("tone", "friend")

    images = []
    if product_id:
        item = catalog_mgr.get_product_by_id(product_id)
        if not item:
            raise HTTPException(status_code=404, detail="ไม่พบสินค้าในระบบ")
        name = item["name"]
        category = item["category"]
        highlight = item["highlight"]
        images = item.get("images", [])
    else:
        name = data.get("name", "").strip()
        category = data.get("category", "general")
        highlight = data.get("highlight", "")
        images = data.get("images", [])

    if not name:
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อสินค้า")

    prod = Product(
        item_id="temp_script",
        shop_id="temp",
        name=name,
        price=0.0,
        original_price=0.0,
        discount_percent=0,
        image_urls=images,
        affiliate_link="",
        category=category,
        rating=4.9,
        sold_count=50000,
        description=highlight,
    )

    content: VideoContent = script_generator.generate_video_content(prod, image_paths=images)
    return {
        "success": True,
        "hook": content.hook,
        "body": content.body,
        "cta": content.cta,
        "caption": content.caption,
        "hashtags": content.hashtags,
        "visual_notes": getattr(content, "visual_notes", ""),
    }


@app.post("/api/generate-catalog")
async def generate_catalog(data: dict):
    """
    สร้างคลิปจากสินค้าใน Verified Catalog (รองรับ Template, Voice AI, BGM, และ Custom Script)
    """
    product_id = data.get("product_id")
    tone = data.get("tone", "friend")
    affiliate_url = data.get("affiliate_url", "").strip()
    template = data.get("template", "clean")
    enable_voice = data.get("enable_voice", True)
    voice_type = data.get("voice_type", "female")
    bgm_track = data.get("bgm_track", "cheerful")
    custom_hook = data.get("custom_hook")
    custom_body = data.get("custom_body")
    custom_cta = data.get("custom_cta")

    item = catalog_mgr.get_product_by_id(product_id)
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
    product.product_id = item.get("id", "")

    return _process_video_generation(
        product=product,
        image_paths=item["images"],
        tone=tone,
        template=template,
        enable_voice=enable_voice,
        voice_type=voice_type,
        bgm_track=bgm_track,
        custom_hook=custom_hook,
        custom_body=custom_body,
        custom_cta=custom_cta,
    )


# ============================================================
# Phase 3: Background Batch Render State & Engine
# ============================================================
batch_render_state = {
    "is_running": False,
    "cancel_requested": False,
    "total": 0,
    "current_index": 0,
    "percent": 0,
    "current_product": "",
    "current_step": "พร้อมทำงาน",
    "completed_count": 0,
    "failed_count": 0,
    "completed_items": [],
    "failed_items": [],
    "logs": [],
    "started_at": None,
    "finished_at": None,
}


async def _run_batch_render_task(items: list, config: dict):
    """Background Worker สำหรับสร้างวิดีโอแบบ Batch อัตโนมัติทีละรายการ"""
    global batch_render_state
    batch_render_state["is_running"] = True
    batch_render_state["cancel_requested"] = False
    batch_render_state["total"] = len(items)
    batch_render_state["current_index"] = 0
    batch_render_state["percent"] = 0
    batch_render_state["completed_count"] = 0
    batch_render_state["failed_count"] = 0
    batch_render_state["completed_items"] = []
    batch_render_state["failed_items"] = []
    batch_render_state["logs"] = [f"⚡ เริ่มต้นการสร้าง Batch Render สำหรับ {len(items)} สินค้า..."]
    batch_render_state["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    batch_render_state["finished_at"] = None

    for idx, item in enumerate(items):
        if batch_render_state.get("cancel_requested"):
            batch_render_state["logs"].append("🛑 ได้รับคำสั่งยกเลิกงาน Batch Render จากผู้ใช้")
            break

        batch_render_state["current_index"] = idx + 1
        batch_render_state["current_product"] = item.get("name", "สินค้า")
        batch_render_state["current_step"] = f"กำลังประมวลผล [{idx+1}/{len(items)}]: Gemini Vision + Voice + FFmpeg"
        batch_render_state["percent"] = int((idx / len(items)) * 100)
        batch_render_state["logs"].append(f"▶ [{idx+1}/{len(items)}] เริ่มต้น: {item.get('name', '')[:35]}")

        try:
            def _render_single():
                prod = Product(
                    item_id=f"web_{item.get('category', 'general')}_{item.get('id', uuid.uuid4().hex[:6])}",
                    shop_id="official_mall",
                    name=item["name"],
                    price=0.0,
                    original_price=0.0,
                    discount_percent=0,
                    image_urls=item.get("images", []),
                    affiliate_link=item.get("affiliate_link", ""),
                    category=item.get("category", "general"),
                    rating=float(item.get("rating", 4.9)),
                    sold_count=int(item.get("sold_count", 50000)),
                    description=item.get("highlight", ""),
                )
                prod.product_id = item.get("id", "")
                return _process_video_generation(
                    product=prod,
                    image_paths=item.get("images", []),
                    template=config.get("template", "clean"),
                    enable_voice=config.get("enable_voice", True),
                    voice_type=config.get("voice_type", "female"),
                    bgm_track=config.get("bgm_track", "cheerful"),
                )

            res = await asyncio.to_thread(_render_single)
            batch_render_state["completed_count"] += 1
            batch_render_state["completed_items"].append({
                "id": item.get("id"),
                "name": item.get("name"),
                "video_url": res.get("video_url"),
                "thumbnail_url": res.get("thumbnail_url"),
                "visual_notes": res.get("visual_notes", ""),
                "render_time": res.get("render_time_seconds"),
            })
            batch_render_state["logs"].append(f"✅ สำเร็จ [{idx+1}/{len(items)}]: {item.get('name')[:30]} ({res.get('render_time_seconds')}s)")

        except Exception as e:
            logger.error(f"Batch Render failed for {item.get('id')}: {e}")
            batch_render_state["failed_count"] += 1
            batch_render_state["failed_items"].append({
                "id": item.get("id"),
                "name": item.get("name"),
                "error": str(e),
            })
            batch_render_state["logs"].append(f"❌ ผิดพลาด: {item.get('name')[:25]} - {str(e)[:45]}")

        batch_render_state["percent"] = int(((idx + 1) / len(items)) * 100)
        # Delay สั้นๆ เพื่อพักและเคารพ Rate Limits
        await asyncio.sleep(1.0)

    batch_render_state["is_running"] = False
    batch_render_state["current_step"] = "เสร็จสิ้นการประมวลผลทั้งหมด"
    batch_render_state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    batch_render_state["logs"].append(
        f"🎉 Batch Render จบแล้ว! ทำสำเร็จ {batch_render_state['completed_count']} รายการ (ล้มเหลว {batch_render_state['failed_count']})"
    )


@app.post("/api/batch-render/start")
async def start_batch_render(data: dict):
    """
    เริ่มต้นรัน Batch Render ในเบื้องหลัง (สร้างคลิปทั้งหมดที่ค้างอยู่ หรือเลือกสินค้า)
    Payload: { "target": "pending" | "all" | "selected", "source": "all", "max_items": 0 }
    """
    global batch_render_state
    if batch_render_state.get("is_running"):
        return {
            "success": False,
            "message": "ระบบกำลังประมวลผล Batch Render งานเดิมอยู่แล้ว",
            "state": batch_render_state,
        }

    target = data.get("target", "pending")
    product_ids = data.get("product_ids", [])
    source = data.get("source", "all")

    if target == "pending":
        items = catalog_mgr.get_all_products(source=source, video_status_filter="pending")
    elif target == "selected" and product_ids:
        all_items = catalog_mgr.get_all_products(source="all")
        items = [p for p in all_items if p.get("id") in product_ids]
    else:
        items = catalog_mgr.get_all_products(source=source)

    if not items:
        return {
            "success": False,
            "message": "ไม่มีสินค้าที่รอการทำวิดีโอ (ทำครบทุกตัวแล้ว)",
            "count": 0,
        }

    max_items = int(data.get("max_items", 0))
    if max_items > 0:
        items = items[:max_items]

    config = {
        "template": data.get("template", "clean"),
        "enable_voice": data.get("enable_voice", True),
        "voice_type": data.get("voice_type", "female"),
        "bgm_track": data.get("bgm_track", "cheerful"),
    }

    asyncio.create_task(_run_batch_render_task(items, config))

    return {
        "success": True,
        "message": f"เริ่มต้นสร้างวิดีโอจำนวน {len(items)} รายการในเบื้องหลังเรียบร้อย",
        "total": len(items),
        "target": target,
    }


@app.get("/api/batch-render/status")
async def get_batch_render_status():
    """ดึงสถานะและความคืบหน้าของ Batch Render แบบเรียลไทม์"""
    global batch_render_state
    return {
        "success": True,
        "state": batch_render_state,
        "stats": catalog_mgr.get_video_stats(),
    }


@app.post("/api/batch-render/stop")
async def stop_batch_render():
    """ยกเลิกงาน Batch Render ที่กำลังทำงานอยู่"""
    global batch_render_state
    if batch_render_state.get("is_running"):
        batch_render_state["cancel_requested"] = True
        return {"success": True, "message": "ส่งคำขอยกเลิกงาน Batch Render เรียบร้อยแล้ว"}
    return {"success": False, "message": "ไม่มีงาน Batch Render ที่กำลังรันอยู่"}


@app.post("/api/batch-generate")
async def batch_generate(data: dict):
    """
    สร้างคลิปหลายตัวพร้อมกันในคลิกเดียว (Batch Mode)
    Payload: { "product_ids": ["mizumi_uv", "drpong_28d", ...], "template": "clean", ... }
    """
    product_ids = data.get("product_ids", [])
    if not product_ids:
        raise HTTPException(status_code=400, detail="กรุณาเลือกสินค้าอย่างน้อย 1 รายการ")

    results = []
    tone = data.get("tone", "friend")
    template = data.get("template", "clean")
    enable_voice = data.get("enable_voice", True)
    voice_type = data.get("voice_type", "female")
    bgm_track = data.get("bgm_track", "cheerful")
    affiliate_url = data.get("affiliate_url", "").strip()

    logger.info(f"⚡ เริ่มต้นการสร้าง Batch คลิปจำนวน {len(product_ids)} รายการ...")

    for pid in product_ids:
        item = catalog_mgr.get_product_by_id(pid)
        if not item:
            continue
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
        product.product_id = item.get("id", "")
        try:
            res = _process_video_generation(
                product=product,
                image_paths=item["images"],
                tone=tone,
                template=template,
                enable_voice=enable_voice,
                voice_type=voice_type,
                bgm_track=bgm_track,
            )
            results.append(res)
        except Exception as e:
            logger.error(f"สร้างคลิป {pid} ล้มเหลว: {e}")

    return {
        "success": True,
        "count": len(results),
        "results": results
    }


@app.post("/api/generate-custom")
async def generate_custom(
    name: str = Form(...),
    category: str = Form("general"),
    highlight: str = Form(""),
    tone: str = Form("friend"),
    affiliate_url: str = Form(""),
    template: str = Form("clean"),
    enable_voice: bool = Form(True),
    voice_type: str = Form("female"),
    bgm_track: str = Form("cheerful"),
    custom_hook: Optional[str] = Form(None),
    custom_body: Optional[str] = Form(None),
    custom_cta: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    image_paths_json: Optional[str] = Form(None),
):
    """สร้างคลิปจากสินค้าที่ผู้ใช้อัปโหลดเอง หรือภาพที่ดึงมาจาก Shopee CDN"""
    if not name.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อสินค้า")

    saved_images = []

    # 1. ถ้ามีไฟล์อัปโหลดเข้ามา
    if images and len(images) > 0 and images[0].filename:
        session_id = f"custom_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        target_dir = UPLOAD_DIR / session_id
        target_dir.mkdir(parents=True, exist_ok=True)
        for i, file in enumerate(images[:3]):
            if not file.filename:
                continue
            ext = Path(file.filename).suffix or ".jpg"
            save_path = target_dir / f"img_{i}{ext}"
            with open(save_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            saved_images.append(str(save_path))

    # 2. ถ้าไม่มีไฟล์อัปโหลด แต่มี path ภาพที่ดึงมาจาก Shopee CDN
    if not saved_images and image_paths_json:
        try:
            parsed_paths = json.loads(image_paths_json)
            if isinstance(parsed_paths, list):
                for p in parsed_paths:
                    if os.path.exists(p) or (PROJECT_ROOT / p).exists():
                        saved_images.append(p)
        except Exception as e:
            logger.warning(f"Error parsing image_paths_json: {e}")

    # ถ้ายังไม่มีภาพ ให้แจ้งเตือนผู้ใช้ชัดเจน
    if not saved_images:
        raise HTTPException(
            status_code=400, 
            detail="กรุณาอัปโหลดรูปภาพสินค้า หรือวางลิงก์ Shopee ที่มีรูปภาพสินค้าเพื่อสร้างคลิป"
        )

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

    return _process_video_generation(
        product=product,
        image_paths=saved_images,
        tone=tone,
        template=template,
        enable_voice=enable_voice,
        voice_type=voice_type,
        bgm_track=bgm_track,
        custom_hook=custom_hook,
        custom_body=custom_body,
        custom_cta=custom_cta,
    )


def _process_video_generation(
    product: Product,
    image_paths: list,
    tone: str = "friend",
    template: str = "clean",
    enable_voice: bool = True,
    voice_type: str = "female",
    bgm_track: str = "cheerful",
    custom_hook: Optional[str] = None,
    custom_body: Optional[str] = None,
    custom_cta: Optional[str] = None,
):
    """ประมวลผลการสร้างบท สังเคราะห์เสียง และตัดต่อวิดีโอ"""
    try:
        start_time = time.time()
        logger.info(f"🚀 เริ่มต้นสร้างวิดีโอสำหรับ: {product.name[:30]}... (Template: {template}, Voice: {enable_voice}, BGM: {bgm_track})")

        # 1. เขียนสคริปต์ด้วย Gemini Vision (อ่านภาพจริง 100% ตรงปก) หรือใช้ค่าที่ผู้ใช้แก้ไข
        content: VideoContent = script_generator.generate_video_content(product, image_paths=image_paths)

        if custom_hook and custom_hook.strip():
            content.hook = custom_hook.strip()
        if custom_body and custom_body.strip():
            content.body = custom_body.strip()
        if custom_cta and custom_cta.strip():
            content.cta = custom_cta.strip()

        content.caption = f"แนะนำเลย! {product.name[:45]}\nดูในตะกร้าส้มซ้ายล่างได้เลย 🛒\n\n📌 พิกัด: {product.affiliate_link}"

        # 2. สังเคราะห์เสียงพากย์ AI ภาษาไทย (ถ้าเปิดใช้งาน)
        voice_audio_path = None
        if enable_voice:
            speech_text = f"{content.hook} {content.body} {content.cta}"
            voice_tmp = str(OUTPUT_DIR / f"voice_{product.item_id}.mp3")
            voice_audio_path = generate_voiceover(speech_text, voice_tmp, voice_type=voice_type)

        # 3. เตรียมไฟล์เพลงพื้นหลัง BGM
        bgm_audio_path = None
        if bgm_track and bgm_track != "none":
            bgm_candidate = ASSETS_DIR / "music" / f"bgm_{bgm_track}.mp3"
            if bgm_candidate.exists():
                bgm_audio_path = str(bgm_candidate)

        # 4. เรนเดอร์วิดีโอด้วย FFmpeg
        abs_images = [str(Path(p).resolve()) if not os.path.isabs(p) else p for p in image_paths]
        result = video_creator.create_video(
            product=product,
            content=content,
            image_paths=abs_images,
            template=template,
            voice_audio_path=voice_audio_path,
            bgm_audio_path=bgm_audio_path,
        )

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"✅ สร้างวิดีโอสำเร็จใน {elapsed} วินาที: {result.video_path}")

        # บันทึก metadata เพื่อดึงประวัติ
        meta_filename = Path(result.video_path).stem + "_meta.json"
        meta_path = OUTPUT_DIR / meta_filename
        prod_id = getattr(product, "product_id", "") or getattr(product, "item_id", "")
        metadata = {
            "product_id": prod_id,
            "product_name": product.name,
            "category": product.category,
            "video_filename": Path(result.video_path).name,
            "thumbnail_filename": Path(result.thumbnail_path).name,
            "video_url": f"/output/{Path(result.video_path).name}",
            "thumbnail_url": f"/output/{Path(result.thumbnail_path).name}",
            "hook": content.hook,
            "body": content.body,
            "cta": content.cta,
            "caption": content.caption,
            "hashtags": content.hashtags,
            "visual_notes": getattr(content, "visual_notes", ""),
            "affiliate_url": product.affiliate_link,
            "template": template,
            "has_voice": bool(voice_audio_path),
            "voice_type": voice_type if voice_audio_path else "none",
            "bgm_track": bgm_track,
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


@app.post("/api/forward")
async def forward_video(data: dict):
    """
    ส่งวิดีโอและแคปชันเข้าห้องแชท Discord หรือ Telegram
    Payload: { "video_filename": "...", "channel": "discord", "target": "https://discord.com/api/webhooks/..." }
    """
    filename = data.get("video_filename")
    channel = data.get("channel", "discord")
    target = data.get("target", "").strip()

    video_path = OUTPUT_DIR / filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์วิดีโอ")

    meta_path = OUTPUT_DIR / (video_path.stem + "_meta.json")
    meta = {}
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    if channel == "discord":
        sender = DiscordSender(webhook_url=target)
        from src.video_creator import VideoResult
        vr = VideoResult(
            product_name=meta.get("product_name", "สินค้า Shopee"),
            video_path=str(video_path),
            thumbnail_path=str(OUTPUT_DIR / meta.get("thumbnail_filename", "")),
            duration=10.0,
            file_size_mb=meta.get("file_size_mb", 1.0),
        )
        vc = VideoContent(
            product_name=meta.get("product_name", "สินค้า"),
            hook=meta.get("hook", ""),
            problem="",
            solution=meta.get("body", ""),
            cta=meta.get("cta", ""),
            caption=meta.get("caption", ""),
            hashtags=meta.get("hashtags", []),
        )
        ok = sender.send_video(vr, vc, meta.get("affiliate_url", ""), webhook_url=target)
        if ok:
            return {"success": True, "message": "ส่งวิดีโอเข้า Discord สำเร็จ!"}
        else:
            raise HTTPException(status_code=500, detail="ส่งเข้า Discord ไม่สำเร็จ กรุณาตรวจสอบ Webhook URL")

    raise HTTPException(status_code=400, detail="ยังไม่รองรับช่องทางนี้")


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


@app.get("/api/system-info")
async def get_system_info():
    """ดึงข้อมูลเครือข่าย Local IP และสถานะการเชื่อมต่อบอท"""
    local_ip = get_local_ip()
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    discord_wh = os.getenv("DISCORD_WEBHOOK_URL", "")

    return {
        "success": True,
        "local_ip": local_ip,
        "port": 8000,
        "mobile_base_url": f"http://{local_ip}:8000",
        "telegram_configured": bool(tg_token and tg_chat),
        "telegram_chat_id": tg_chat,
        "discord_configured": bool(discord_wh),
    }


@app.get("/api/qr-url")
async def get_qr_url(filename: str):
    """สร้างลิงก์สำหรับสแกน QR Code ดาวน์โหลดวิดีโอบนมือถือในวง Wi-Fi เดียวกัน"""
    local_ip = get_local_ip()
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์วิดีโอ")

    direct_download_url = f"http://{local_ip}:8000/output/{filename}"
    encoded_url = quote_plus(direct_download_url)
    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&margin=10&data={encoded_url}"

    return {
        "success": True,
        "filename": filename,
        "direct_url": direct_download_url,
        "qr_image_url": qr_image_url,
        "local_ip": local_ip,
    }


@app.post("/api/send-telegram")
async def send_telegram(data: dict):
    """ส่งวิดีโอและแคปชันเข้า Telegram Bot"""
    filename = data.get("filename", "").strip()
    caption = data.get("caption", "").strip()
    title = data.get("title", "")
    hashtags = data.get("hashtags", "")
    affiliate_url = data.get("affiliate_url", "")
    bot_token = data.get("bot_token", "").strip()
    chat_id = data.get("chat_id", "").strip()

    video_path = OUTPUT_DIR / filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์วิดีโอ")

    meta_path = OUTPUT_DIR / (video_path.stem + "_meta.json")
    thumb_path = None
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                if not caption:
                    caption = meta.get("caption", "")
                if not title:
                    title = meta.get("product_name", "")
                if not hashtags and meta.get("hashtags"):
                    hashtags = " ".join(f"#{t}" for t in meta["hashtags"])
                if not affiliate_url:
                    affiliate_url = meta.get("affiliate_url", "")
                t_name = meta.get("thumbnail_filename")
                if t_name and (OUTPUT_DIR / t_name).exists():
                    thumb_path = str(OUTPUT_DIR / t_name)
        except Exception:
            pass

    sender = TelegramSender(token=bot_token or None, chat_id=chat_id or None)
    if not sender.is_configured():
        raise HTTPException(
            status_code=400,
            detail="กรุณาระบุ Telegram Bot Token และ Chat ID หรือบันทึกใน .env"
        )

    try:
        await sender.send_direct_video(
            video_path=str(video_path),
            caption=caption,
            thumbnail_path=thumb_path,
            title=title,
            hashtags=hashtags,
            affiliate_url=affiliate_url,
        )
        return {"success": True, "message": "ส่งวิดีโอเข้า Telegram เรียบร้อยแล้ว!"}
    except Exception as e:
        logger.error(f"Send telegram failed: {e}")
        raise HTTPException(status_code=500, detail=f"ส่งเข้า Telegram ไม่สำเร็จ: {str(e)}")


@app.post("/api/test-telegram")
async def test_telegram(data: dict):
    """ทดสอบเชื่อมต่อ Telegram Bot"""
    bot_token = data.get("bot_token", "").strip()
    chat_id = data.get("chat_id", "").strip()

    sender = TelegramSender(token=bot_token or None, chat_id=chat_id or None)
    if not sender.is_configured():
        raise HTTPException(status_code=400, detail="กรุณาระบุ Bot Token และ Chat ID")

    try:
        ok = await sender.send_test_message("🎉 ยินดีด้วยครับ! บอท Shopee Affiliate เชื่อมต่อกับ Telegram ของคุณสำเร็จแล้ว!")
        if ok:
            return {"success": True, "message": "เชื่อมต่อ Telegram สำเร็จ! ส่งข้อความทดสอบแล้ว"}
        raise Exception("ไม่สามารถส่งข้อความได้")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"เชื่อมต่อไม่สำเร็จ: {str(e)}")


@app.post("/api/save-telegram-config")
async def save_telegram_config(data: dict):
    """บันทึก Telegram Bot Token และ Chat ID ลงไฟล์ .env"""
    bot_token = data.get("bot_token", "").strip()
    chat_id = data.get("chat_id", "").strip()

    env_path = BASE_DIR / ".env"
    env_content = ""
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            env_content = f.read()

    # อัปเดตหรือเพิ่ม TELEGRAM_BOT_TOKEN
    if "TELEGRAM_BOT_TOKEN=" in env_content:
        env_content = re.sub(r"TELEGRAM_BOT_TOKEN=.*", f"TELEGRAM_BOT_TOKEN={bot_token}", env_content)
    else:
        env_content += f"\nTELEGRAM_BOT_TOKEN={bot_token}"

    # อัปเดตหรือเพิ่ม TELEGRAM_CHAT_ID
    if "TELEGRAM_CHAT_ID=" in env_content:
        env_content = re.sub(r"TELEGRAM_CHAT_ID=.*", f"TELEGRAM_CHAT_ID={chat_id}", env_content)
    else:
        env_content += f"\nTELEGRAM_CHAT_ID={chat_id}"

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content.strip() + "\n")

    os.environ["TELEGRAM_BOT_TOKEN"] = bot_token
    os.environ["TELEGRAM_CHAT_ID"] = chat_id

    return {"success": True, "message": "บันทึกการตั้งค่า Telegram เรียบร้อยแล้ว"}


@app.get("/api/scheduler/config")
async def get_scheduler_config_api():
    """ดึงการตั้งค่าตารางรันอัตโนมัติ"""
    cfg = load_scheduler_config()
    return {"success": True, "config": cfg}


@app.post("/api/scheduler/config")
async def save_scheduler_config_api(data: dict):
    """บันทึกการตั้งค่าตารางรันอัตโนมัติ"""
    saved = save_scheduler_config(data)
    return {"success": True, "message": "บันทึกการตั้งค่าตารางเวลาสำเร็จ", "config": saved}


@app.get("/api/scheduler/history")
async def get_scheduler_history_api():
    """ดึงประวัติการรันอัตโนมัติ"""
    hist_file = BASE_DIR / "data" / "scheduler_history.json"
    history = []
    if hist_file.exists():
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass
    return {"success": True, "history": history}


@app.post("/api/scheduler/run-now")
async def run_scheduler_now():
    """กดสั่งรัน Routine การผลิตคลิปอัตโนมัติตอนนี้ทันที (Test Run)"""
    res = await execute_scheduled_routine(is_manual=True)
    return res


async def execute_scheduled_routine(is_manual: bool = False) -> Dict:
    """ประมวลผลการผลิตคลิปอัตโนมัติตามตารางเวลา"""
    import random
    config = load_scheduler_config()
    count = int(config.get("count_per_run", 3))
    source = config.get("source", "both")
    template = config.get("template", "clean")
    enable_voice = config.get("enable_voice", True)
    voice_type = config.get("voice_type", "female")
    bgm_track = config.get("bgm_track", "cheerful")
    notify_telegram = config.get("notify_telegram", True)
    notify_discord = config.get("notify_discord", False)

    candidates = []
    if source in ["my_products", "both"]:
        my_items = catalog_mgr.get_all_products(source="my_products")
        candidates.extend(my_items)

    if source in ["catalog", "both"] or len(candidates) < count:
        catalog_items = catalog_mgr.get_all_products(source="catalog", min_commission=20)
        candidates.extend(catalog_items)

    if not candidates:
        logger.warning("Scheduler: ไม่พบสินค้าสำหรับสร้างคลิป")
        return {"success": False, "message": "ไม่พบสินค้าสำหรับสร้างคลิป"}

    # ให้ความสำคัญกับสินค้าที่ 'ยังไม่ได้ทำคลิป' เป็นอันดับแรก
    pending_items = [c for c in candidates if not c.get("video_status", {}).get("has_video")]
    if pending_items:
        # สุ่มจากรายการที่ยังไม่ได้ทำคลิป
        selected = pending_items[:count] if len(pending_items) <= count else random.sample(pending_items, count)
    else:
        # ถ้าทำครบหมดแล้ว ให้สุ่มวนซ้ำจากทั้งหมด
        selected = candidates[:count] if len(candidates) <= count else random.sample(candidates, count)

    logger.info(f"⏰ [Scheduler] เริ่มต้นสร้างคลิปอัตโนมัติ {len(selected)} รายการ (ค้างทำคลิป: {len(pending_items)} รายการ)...")
    results = []

    for item in selected:
        try:
            custom_link = item.get("affiliate_link", "") or f"https://shopee.co.th/search?keyword={item['name']}"
            product = Product(
                item_id=f"auto_{item['category']}_{item['id']}_{int(time.time())}",
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
            product.product_id = item.get("id", "")

            res = _process_video_generation(
                product=product,
                image_paths=item["images"],
                tone="friend",
                template=template,
                enable_voice=enable_voice,
                voice_type=voice_type,
                bgm_track=bgm_track,
            )

            results.append(res)

            # ส่งเข้า Telegram ทันทีถ้าเปิดไว้
            if notify_telegram:
                try:
                    tg = TelegramSender()
                    if tg.is_configured():
                        v_path = str(OUTPUT_DIR / res["video_filename"])
                        t_path = str(OUTPUT_DIR / res["thumbnail_filename"])
                        tags_str = " ".join(f"#{t}" for t in res.get("hashtags", []))
                        await tg.send_direct_video(
                            video_path=v_path,
                            caption=res["caption"],
                            thumbnail_path=t_path,
                            title=res["product_name"],
                            hashtags=tags_str,
                            affiliate_url=res.get("affiliate_url"),
                        )
                except Exception as tg_e:
                    logger.warning(f"Telegram auto-send error: {tg_e}")

        except Exception as e:
            logger.error(f"Scheduler generate failed for {item.get('id')}: {e}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    config["last_run_timestamp"] = time.time()
    config["last_run_time_str"] = now_str
    config["total_automated_runs"] = config.get("total_automated_runs", 0) + 1
    config["total_videos_created"] = config.get("total_videos_created", 0) + len(results)
    save_scheduler_config(config)

    run_log = {
        "timestamp": now_str,
        "is_manual": is_manual,
        "count": len(results),
        "products": [r.get("product_name") for r in results],
        "videos": [r.get("video_filename") for r in results],
    }
    record_scheduler_run(run_log)

    return {
        "success": True,
        "count": len(results),
        "results": results,
        "timestamp": now_str,
        "message": f"รันอัตโนมัติสำเร็จ สร้างคลิป {len(results)} รายการเรียบร้อยแล้ว!"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=True)
