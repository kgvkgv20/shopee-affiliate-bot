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
import uuid
import time
import shutil
import logging
import re
from pathlib import Path
from typing import Optional, List
from urllib.parse import unquote, urlparse
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
):
    """ดึงรายการสินค้าแนะนำจาก High Commission Database พร้อมค้นหาและกรอง"""
    items = catalog_mgr.get_all_products(
        category=category,
        query=query,
        min_commission=min_commission,
        source=source,
    )
    return {"success": True, "count": len(items), "products": items}


@app.get("/api/my-products")
async def get_my_products():
    """ดึงรายการสินค้าส่วนตัวของผู้ใช้ (My Products)"""
    items = catalog_mgr.get_all_products(source="my_products")
    return {"success": True, "count": len(items), "products": items}


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
        extracted = extract_shopee_product_data(raw_url)
        return {
            "success": True,
            "name": extracted["name"],
            "category": extracted["category"],
            "affiliate_url": extracted["clean_url"],
            "images": extracted["local_images"],
            "cdn_urls": extracted["cdn_urls"],
            "has_real_images": extracted["has_real_images"],
        }
    except Exception as e:
        logger.warning(f"Parse Shopee URL failed: {e}")
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

    if product_id:
        item = catalog_mgr.get_product_by_id(product_id)
        if not item:
            raise HTTPException(status_code=404, detail="ไม่พบสินค้าในระบบ")
        name = item["name"]
        category = item["category"]
        highlight = item["highlight"]
    else:
        name = data.get("name", "").strip()
        category = data.get("category", "general")
        highlight = data.get("highlight", "")

    if not name:
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อสินค้า")

    prod = Product(
        item_id="temp_script",
        shop_id="temp",
        name=name,
        price=0.0,
        original_price=0.0,
        discount_percent=0,
        image_urls=[],
        affiliate_link="",
        category=category,
        rating=4.9,
        sold_count=50000,
        description=highlight,
    )

    content: VideoContent = script_generator.generate_video_content(prod)
    return {
        "success": True,
        "hook": content.hook,
        "body": content.body,
        "cta": content.cta,
        "caption": content.caption,
        "hashtags": content.hashtags,
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

        # 1. เขียนสคริปต์ด้วย Gemini หรือใช้ค่าที่ผู้ใช้แก้ไข
        content: VideoContent = script_generator.generate_video_content(product)

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
        metadata = {
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
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=True)
