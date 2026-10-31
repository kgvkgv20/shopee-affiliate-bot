"""
image_handler.py
----------------
จัดการรูปภาพสินค้าสำหรับ Shopee Affiliate:
1. ดึงภาพจริงจาก Shopee CDN ผ่าน image_ids ใน URL
2. แกะลิงก์ย่อ Shopee (s.shopee.co.th, shope.ee) เพื่อดึงข้อมูลจริง
3. ดาวน์โหลดรูปภาพความละเอียดสูงเก็บไว้ในเครื่อง
4. ระบบค้นหารูปภาพตรงรุ่นอัตโนมัติ (Auto Image Search Fallback)
"""
import os
import re
import io
import time
import hashlib
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from PIL import Image
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = PROJECT_ROOT / "assets" / "products" / "custom_downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
}


def resolve_shopee_url(url: str) -> str:
    """ตาม Redirect ของ Shopee Short Link (s.shopee.co.th, shope.ee) เพื่อเอา Full URL"""
    url = url.strip()
    if not url:
        return ""

    if "s.shopee.co.th" in url or "shope.ee" in url:
        try:
            resp = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=8)
            final_url = resp.url
            logger.info(f"Resolved short link: {url} -> {final_url}")
            return final_url
        except Exception as e:
            logger.warning(f"Error resolving short link: {e}")
            try:
                resp = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=8)
                return resp.url
            except Exception:
                pass
    return url


def extract_shopee_product_data(raw_url: str) -> Dict:
    """
    ถอดข้อมูลสินค้าและรูปภาพจริงจากลิงก์ Shopee:
    - ชื่อสินค้าจาก Slug
    - รูปภาพจริงจาก Shopee CDN (image_ids)
    - หมวดหมู่สินค้า
    """
    clean_url = resolve_shopee_url(raw_url)
    parsed = urlparse(clean_url)
    qs = parse_qs(parsed.query)

    # 1. ถอดชื่อสินค้าจาก Slug
    path_decoded = unquote(parsed.path)
    slug = path_decoded.strip("/").split("/")[-1]
    clean_slug = re.sub(r"-i\.\d+\.\d+", "", slug)
    clean_name = clean_slug.replace("-", " ").strip()

    if len(clean_name) < 3 or clean_name.startswith("product"):
        clean_name = "สินค้า Shopee คุณภาพดี"

    # 2. ถอด Image IDs จาก Query Parameters
    image_ids = []
    for key in ["image_ids", "image_id", "img_ids", "img_id", "images"]:
        if key in qs:
            for val in qs[key]:
                for item in val.split(","):
                    item = item.strip()
                    if item and item not in image_ids:
                        image_ids.append(item)

    # ถ้าใน extraParams มี image_ids แฝงอยู่
    if "extraParams" in qs:
        for ep in qs["extraParams"]:
            found_ids = re.findall(r'th-[0-9a-zA-Z_-]+', ep)
            for fid in found_ids:
                if fid not in image_ids:
                    image_ids.append(fid)

    # 3. แปลงเป็น Image URLs บน Shopee CDN และดาวน์โหลดเข้าเครื่อง
    local_images = []
    cdn_urls = []
    for img_id in image_ids[:3]:
        # ลบ prefix/suffix ที่ไม่เกี่ยวข้อง
        clean_img_id = img_id.strip()
        cdn_url = f"https://down-th.img.susercontent.com/file/{clean_img_id}"
        cdn_urls.append(cdn_url)

        local_path = download_image_to_file(cdn_url, prefix="shopee_cdn")
        if local_path:
            local_images.append(local_path)

    # 4. คาดเดาหมวดหมู่
    cat = "general"
    lower_name = clean_name.lower()
    if any(w in lower_name for w in ["เซรั่ม", "กันแดด", "ครีม", "ล้างหน้า", "มาส์ก", "แป้ง", "ลิป", "สกินแคร์", "เซรัม", "บำรุง"]):
        cat = "beauty"
    elif any(w in lower_name for w in ["แก้ว", "พัดลม", "หม้อ", "กล่อง", "ที่นอน", "ผ้าปู", "ไม้กวาด", "เก้าอี้", "กระติก", "ถูพื้น", "ดูดฝุ่น", "ล้างจมูก"]):
        cat = "home"
    elif any(w in lower_name for w in ["หูฟัง", "สายชาร์จ", "คีย์บอร์ด", "เมาส์", "พาวเวอร์แบงค์", "ลำโพง", "บลูทูธ", "ชาร์จ", "แท่นชาร์จ", "ไมค์"]):
        cat = "electronics"
    elif any(w in lower_name for w in ["กระเป๋า", "ร่ม", "เสื้อ", "กางเกง", "รองเท้า", "หมวก", "แว่น", "เดรส"]):
        cat = "fashion"

    # ถ้ามีรูปไม่ครบ 3 รูป ให้คัดลอกรูปแรกให้ครบ 3 รูป
    while 0 < len(local_images) < 3:
        local_images.append(local_images[0])

    return {
        "success": True,
        "name": clean_name,
        "category": cat,
        "affiliate_url": raw_url,
        "clean_url": clean_url,
        "image_ids": image_ids,
        "cdn_urls": cdn_urls,
        "local_images": local_images,
        "has_real_images": len(local_images) > 0,
    }


def download_image_to_file(image_url: str, prefix: str = "img") -> Optional[str]:
    """ดาวน์โหลดรูปภาพจาก URL แล้วแปลงเป็น JPEG เซฟเก็บในเครื่อง"""
    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            img_hash = hashlib.md5(resp.content).hexdigest()[:10]
            filename = f"{prefix}_{img_hash}.jpg"
            save_path = DOWNLOADS_DIR / filename

            # แปลงเป็น RGB JPEG ผ่าน PIL เพื่อตัดปัญหาไฟล์สกุล WebP/PNG/CMYK
            im = Image.open(io.BytesIO(resp.content)).convert("RGB")
            im.save(save_path, "JPEG", quality=90)
            logger.info(f"Saved image from {image_url[:40]} -> {save_path.name}")
            return f"assets/products/custom_downloads/{filename}"
    except Exception as e:
        logger.warning(f"Failed to download image from {image_url}: {e}")
    return None
