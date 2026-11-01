"""
google_flow_exporter.py
-----------------------
สร้างชุดข้อมูลและ Prompt สำหรับนำไปต่อยอดใน Google Flow (Google Labs Veo / Imagen)
หรือ AI Video Generators (Kling, Luma Dream Machine, Runway Gen-3, Midjourney):
1. First-frame Image Prompt (ภาพนางแบบ AI ถือสินค้าสไตล์ UGC)
2. Video Motion / Animation Prompt (คำสั่งขยับวิดีโอสำหรับ Google Flow / Veo)
3. สคริปต์พากย์ไทย (Hook / Body / CTA)
4. แพ็กเกจรูปภาพสินค้าความละเอียดสูง
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def generate_google_flow_kit(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    สร้าง Prompt และชุดข้อมูลพร้อมโยนเข้า Google Flow / Veo สำหรับสินค้า 1 รายการ
    """
    name = product.get("name", "สินค้า Shopee")
    brand = product.get("brand", "Official")
    category = product.get("category", "general")
    highlight = product.get("highlight", "")
    aff_link = product.get("affiliate_link", "")
    images = product.get("images", [])

    # กำหนดบุคลิก Creator ตามหมวดหมู่สินค้า
    persona = {
        "beauty": {
            "creator": "a beautiful 24-year-old Thai female beauty influencer with radiant glowing glass skin and soft natural makeup",
            "setting": "in a modern sunlit minimalist Bangkok apartment, aesthetic vanity table background",
            "action": "holding the cosmetic product close to the camera, gently showing the texture, smiling warmly with authentic enthusiasm",
            "lighting": "soft natural daylight streaming through window, clean commercial beauty lighting, 8k resolution"
        },
        "home": {
            "creator": "a friendly 26-year-old Thai content creator with a cozy casual aesthetic",
            "setting": "in a clean Scandinavian modern kitchen and living room with warm wooden accents",
            "action": "demonstrating the household product on a table, holding it proudly to camera, nodding happily with a smile",
            "lighting": "warm airy daylight, crisp 4k vertical smartphone photography style"
        },
        "electronics": {
            "creator": "a stylish 25-year-old Thai tech enthusiast wearing clean minimal streetwear",
            "setting": "in a sleek modern aesthetic desk setup with warm ambient desk lamp in the background",
            "action": "holding the gadget close to camera, showing details from different angles, smiling approvingly",
            "lighting": "crisp studio key lighting with soft neon rim light, razor sharp 8k detail"
        },
        "fashion": {
            "creator": "a chic 23-year-old Thai fashion blogger with trendy Korean-minimal hairstyle",
            "setting": "in a trendy bright cafe patio in Bangkok, aesthetic soft tones",
            "action": "holding and showing off the fashion accessory to camera, joyful genuine expression",
            "lighting": "golden hour soft sunlight, high fashion lookbook aesthetic, 8k"
        },
        "general": {
            "creator": "a cheerful 25-year-old Thai creator with a relatable friendly smile",
            "setting": "in a bright clean modern studio room",
            "action": "holding the product happily towards the camera, pointing at it enthusiastically",
            "lighting": "natural bright lighting, 4k vertical UGC smartphone style"
        }
    }.get(category, {
        "creator": "a cheerful 25-year-old Thai UGC creator",
        "setting": "in a bright modern room",
        "action": "holding the product towards camera, smiling genuinely",
        "lighting": "natural daylight, 4k"
    })

    # 1. First Frame Image Prompt (สำหรับเจนภาพเริ่มต้นใน Google Flow หรือ Midjourney/Imagen)
    first_frame_prompt = (
        f"A candid vertical 9:16 smartphone photography of {persona['creator']} {persona['setting']}. "
        f"She is {persona['action']}. The product shown is '{name}'. "
        f"Authentic Thai TikTok / Shopee Video creator aesthetic, highly detailed face, genuine smile, "
        f"{persona['lighting']}, hyper-realistic, photorealistic, cinematic depth of field."
    )

    # 2. Veo / Google Flow Video Motion Prompt (สำหรับใส่ในช่อง Prompt ของ Google Flow เพื่อขยับเป็นวิดีโอ)
    video_motion_prompt = (
        f"Vertical 9:16 video: The Thai female creator happily looks at the camera, holds up '{name}', "
        f"smiles warmly and speaks enthusiastically as if recommending her favorite item to friends. "
        f"Natural hand gestures, subtle lifelike head nodding, smooth camera motion, realistic facial micro-expressions. "
        f"Natural room acoustics, soft daylight, ultra-high quality UGC video, 4k resolution."
    )

    # 3. สคริปต์พากย์เสียงภาษาไทย 3 สเต็ป (Hook, Body, CTA)
    hook = f"แกกก ใครกำลังเล็ง {name[:30]} อยู่ ฟังคลิปนี้ด่วน!"
    body = highlight if highlight else f"ตัวนี้คือดีมาก การันตีรีวิวแน่น คุ้มค่าเกินราคา ใช้แล้วชอบมาก"
    cta = "พิกัดอยู่ที่ตะกร้าส้มซ้ายล่าง รีบกดก่อนของหมดน้า!"

    return {
        "product_id": product.get("id"),
        "product_name": name,
        "brand": brand,
        "category": category,
        "first_frame_image_prompt": first_frame_prompt,
        "google_flow_veo_prompt": video_motion_prompt,
        "thai_script": {
            "hook": hook,
            "body": body,
            "cta": cta,
            "full_script": f"{hook} {body} {cta}"
        },
        "images": images,
        "affiliate_link": aff_link,
        "instructions": [
            "1. คัดลอก 'First-frame Image Prompt' ไปเจนรูปนางแบบถือสินค้าใน Google Flow (Imagen) หรือ Midjourney",
            "2. นำรูปภาพที่ได้อัปโหลดเป็น First Frame ใน Google Flow",
            "3. วาง 'Google Flow Veo Prompt' ในช่อง Motion Prompt แล้วกด Generate Video",
            "4. ดาวน์โหลดวิดีโอที่ได้กลับมา หรือจะใช้ระบบเรนเดอร์ในบอทของเราโดยตรงก็ได้เช่นกัน!"
        ]
    }
