"""
gemini_generator.py
-------------------
ใช้ Gemini API (Free Tier) สร้าง:
  - วิดีโอ script สไตล์ "เพื่อนแนะนำเพื่อน" 10 วินาที
  - Hashtags สำหรับ Shopee (ไม่มีราคา/โปร)
  - Caption สำหรับโพสต์

Model: gemini-3.8-flash (ฟรี tier)
SDK: google-genai >= 2.30.1

Shopee Compliance Rules (Phase 1):
  ✅ ไม่พูดราคา (บาท / หลักร้อย / กี่สิบ)
  ✅ ไม่พูดโปร (แฟลชเซล / ส่งฟรี / ลด X%)
  ✅ ไม่ overclaim (ขาวทันที / หายขาด 100%)
  ✅ CTA ชี้ตะกร้าส้มแบบเป็นมิตร
"""
import os
import json
import logging
import re
import base64
import mimetypes
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from google import genai
from src.shopee_scraper import Product

logger = logging.getLogger(__name__)

# ============================================================
# คำต้องห้าม Shopee Compliance — ตรวจก่อนส่ง
# ============================================================
BANNED_PRICE_WORDS = [
    "บาท", "หลักร้อย", "หลักพัน", "ไม่ถึงร้อย", "กี่สิบ",
    "ราคา", "ถูกมาก", "แพง", "คุ้ม",
]
BANNED_PROMO_WORDS = [
    "ส่งฟรี", "แฟลชเซล", "flash sale", "ลด 5", "ลด 6", "ลด 7",
    "ลด 8", "ลด 9", "โปรวันนี้", "เฉพาะวันนี้", "ก่อนโปรหมด",
    "ราคาพิเศษ", "โปรโมชัน", "promotion",
]
BANNED_OVERCLAIM_WORDS = [
    "ขาวทันที", "หายขาด", "100%", "ดีที่สุดในโลก",
    "ดีที่สุด", "ไม่มีใครเทียบ", "รักษาหาย", "โรคหาย",
    "ลด 10 โล", "ขาวถาวร", "หน้าเด็กตลอดกาล",
]
BANNED_AUTHORITY_WORDS = [
    "หมอแนะนำ", "แพทย์รับรอง", "คุณหมอการันตี",
    "เภสัชกรแนะนำ", "ดาราแนะนำ", "คนดังใช้",
]


# ============================================================
# Prompt Template — Phase 1 "เพื่อนแนะนำเพื่อน" 10 วินาที
# ============================================================
PROMPT_TEMPLATE = """\
คุณคือเพื่อนสนิทที่ชอบป้ายยาของใช้ดีๆ ให้เพื่อนฟัง
จงสร้างสคริปต์วิดีโอสั้นและแคปชันสำหรับ Shopee Video จากข้อมูลสินค้า:

ชื่อสินค้า: {product_name}
จุดเด่น: {product_desc}

[ข้อกำหนดเด็ดขาด — ห้ามฝ่าฝืน]
1. ความยาวสคริปต์: ไม่เกิน 40 คำ (อ่านจบภายใน 10 วินาทีพอดี)
2. โทนเสียง: พูดคุยเป็นกันเอง ภาษาพูดสไตล์เพื่อนแนะนำเพื่อน (เช่น แก, คือดีย์, เพิ่งลอง, ป้ายยา)
3. ห้ามระบุราคาเด็ดขาด (ห้ามพูดคำว่า บาท, หลักร้อย, ราคาถูก, กี่สิบบาท, คุ้ม)
4. ห้ามระบุโปรโมชันเด็ดขาด (ห้ามพูดคำว่า แฟลชเซล, ส่งฟรี, ลด 50%, โปรวันนี้, ราคาพิเศษ)
5. ห้าม overclaim (ห้ามพูดว่า ขาวทันที, หายขาด 100%, ดีที่สุด)
6. ปิดท้ายด้วยการบอกพิกัดตะกร้าส้มแบบน่ารัก ไม่ hard sell

[โครงสร้างคลิป 10 วินาที]
- hook (0–3 วิ): สะกิดปัญหาใกล้ตัว สั้นและสะดุดหู
- body (3–7 วิ): จุดเด่น 1–2 ข้อ สไตล์คนใช้จริง
- cta (7–10 วิ): ชี้ตะกร้าส้มซ้ายล่าง แบบเป็นมิตร

[รูปแบบ JSON ที่ต้องการส่งกลับ — ตอบ JSON เท่านั้น]
{{
  "hook": "ข้อความเปิดคลิป 0–3 วิ (สั้นและสะดุดหู)",
  "body": "บอกจุดเด่นการใช้งาน 3–7 วิ (1–2 จุดเด่น)",
  "cta": "ชี้พิกัดตะกร้าส้ม 7–10 วิ แบบเป็นมิตร",
  "full_script": "ข้อความรวมทั้งหมด ไม่เกิน 40 คำ",
  "video_title": "ชื่อวิดีโอ ไม่เกิน 40 ตัวอักษร ห้ามมีราคา",
  "caption": "แคปชันโพสต์ 1–2 บรรทัด + hashtag ไม่พูดเรื่องราคา/โปร",
  "hashtags": ["shopee", "shopeeth", "ของดีบอกต่อ", "แนะนำสินค้า"]
}}
"""

# ============================================================
# Prompt Template — Gemini Vision 100% ตรงปก (Phase 1 Upgrade)
# ============================================================
PROMPT_VISION_TEMPLATE = """\
คุณคือเพื่อนสนิทที่ชอบป้ายยาของใช้ดีๆ ให้เพื่อนฟังใน Shopee Video
จงดูภาพสินค้าจริงทั้ง {image_count} ภาพด้านบนอย่างละเอียด แล้วเขียนสคริปต์วิดีโอ 10 วินาทีและข้อความให้ "ตรงกับสิ่งที่ตาเห็นในแต่ละภาพแบบ 100%":

ชื่อสินค้า: {product_name}
หมวดหมู่: {category}
จุดเด่นเพิ่มเติม: {product_desc}

[ข้อกำหนดสำคัญเพื่อความตรงปก 100%]:
1. "hook" (ฉากที่ 1, วินาที 0–3): ต้องบรรยายหรืออ้างอิงสิ่งที่เห็นในภาพที่ 1 โดยตรง (เช่น ตัวแพ็กเกจ, ตัวขวด, ตลับ, ดีไซน์ หรือฟังก์ชันหลักที่ภาพแสดง) สั้นกระชับ สะกิดใจ 8–12 คำ
2. "body" (ฉากที่ 2, วินาที 3–7): ต้องบรรยายสิ่งที่เห็นในภาพที่ 2 โดยตรง (เช่น จุดเด่น, เนื้อสัมผัส, วิธีใช้, ด้านใน, รายละเอียดเฉพาะที่ตาเห็นในรูป) 12–16 คำ
3. "cta" (ฉากที่ 3, วินาที 7–10): ปิดท้ายชวนไปที่พิกัดตะกร้าส้มซ้ายล่าง โดยสอดคล้องกับภาพที่ 3 (เช่น ของแถม, ความคุ้มค่า, หรือชี้เป้า) 8–12 คำ
4. ห้ามระบุราคาเด็ดขาด (ห้ามพูดคำว่า บาท, หลักร้อย, หลักพัน, ไม่ถึงร้อย, กี่สิบบาท, ราคาถูก)
5. ห้ามระบุโปรโมชันเด็ดขาด (ห้ามพูดคำว่า แฟลชเซล, ส่งฟรี, flash sale, ลด X%, โปรวันนี้)
6. ห้าม overclaim (ห้ามพูดว่า ขาวทันที, หายขาด 100%, ดีที่สุด)
7. ความยาวรวม full_script ทั้งหมดต้องไม่เกิน 40 คำ เพื่อให้อ่านจบภายใน 10 วินาทีพอดี!
8. น้ำเสียง: ภาษาพูดสไตล์เพื่อนคุยกัน เป็นกันเอง สนุกสนาน น่ารัก ไม่ขายตรงจนน่ารำคาญ

[รูปแบบ JSON ที่ต้องการส่งกลับ — ตอบ JSON เท่านั้น]:
{{
  "hook": "ข้อความเปิดคลิป 0–3 วิ ตรงกับภาพที่ 1",
  "body": "บอกจุดเด่นการใช้งาน 3–7 วิ ตรงกับภาพที่ 2",
  "cta": "ชี้พิกัดตะกร้าส้ม 7–10 วิ ตรงกับภาพที่ 3",
  "full_script": "ข้อความรวม hook + body + cta รวมกันไม่เกิน 40 คำ",
  "video_title": "ชื่อวิดีโอสั้น ไม่เกิน 35 ตัวอักษร",
  "caption": "แคปชันโพสต์ 1–2 บรรทัด + hashtag",
  "hashtags": ["shopee", "shopeeth", "ของดีบอกต่อ", "แนะนำสินค้า"],
  "visual_notes": "บันทึกสั้นๆ ว่าในภาพที่ 1, 2, 3 เห็นอะไรเพื่อยืนยันว่าตรงปก"
}}
"""


@dataclass
class VideoContent:
    """ผลลัพธ์จาก Gemini — Phase 1 (10 วินาที, Shopee Compliant)"""
    product_name: str
    hook: str             # 0–3 วิ: สะกิดปัญหา
    body: str             # 3–7 วิ: จุดเด่น
    cta: str              # 7–10 วิ: ชี้ตะกร้าส้ม
    full_script: str      # script รวมทั้งหมด
    video_title: str      # ชื่อวิดีโอ
    caption: str          # caption สำหรับโพสต์
    hashtags: list[str]   # hashtags
    visual_notes: str = "" # บันทึกสิ่งที่ตาเห็นจากรูป (Vision Accuracy)
    compliance_ok: bool = True  # ผ่าน compliance check หรือไม่

    # --- legacy compat (ใช้ใน telegram_sender) ---
    @property
    def script(self) -> str:
        return self.full_script

    @property
    def key_points(self) -> list[str]:
        return [self.hook, self.body, self.cta]

    @property
    def call_to_action(self) -> str:
        return self.cta

    @property
    def hashtag_string(self) -> str:
        return " ".join(f"#{tag}" for tag in self.hashtags)

    @property
    def full_caption(self) -> str:
        return f"{self.caption}\n\n{self.hashtag_string}"


class GeminiContentGenerator:
    """
    สร้าง script + hashtag ด้วย Gemini API
    Phase 1: 10 วินาที / Shopee Compliant / สไตล์เพื่อนแนะนำเพื่อน

    Free tier limits (gemini-3.8-flash):
    - 500 requests/day
    - 10 requests/minute
    """

    MODEL = "gemini-3.5-flash-lite"

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("ต้องกำหนด GEMINI_API_KEY ใน .env")
        self.client = genai.Client(api_key=api_key)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def generate_video_content(
        self,
        product: Product,
        image_paths: Optional[List[str]] = None,
        language: str = "th",
        video_duration: int = 10,
    ) -> VideoContent:
        """
        สร้าง script + hashtag (Phase 1: 10 วินาที, Shopee compliant)
        หากมี image_paths หรือรูปภาพในสินค้า จะส่งให้ Gemini Vision อ่านรูปจริงก่อนแต่งบท
        """
        # ถ้ามีรูปภาพ ให้ใช้ Gemini Vision เพื่อความตรงปก 100%
        if image_paths or (product.image_urls and any(product.image_urls)):
            return self.generate_video_content_with_vision(
                product=product,
                image_paths=image_paths,
                language=language,
                video_duration=video_duration,
            )

        product_desc = self._build_product_desc(product)
        prompt = PROMPT_TEMPLATE.format(
            product_name=product.name,
            product_desc=product_desc,
        )

        try:
            interaction = self.client.interactions.create(
                model=self.MODEL,
                input=prompt,
                store=False,
            )

            raw = interaction.output_text or ""
            raw = self._extract_json(raw)
            data = json.loads(raw)

            content = VideoContent(
                product_name=product.name,
                hook=data.get("hook", ""),
                body=data.get("body", ""),
                cta=data.get("cta", "ดูพิกัดในตะกร้าส้มซ้ายล่างได้เลยนะ"),
                full_script=data.get("full_script", ""),
                video_title=data.get("video_title", product.short_name),
                caption=data.get("caption", ""),
                hashtags=data.get("hashtags", self._default_hashtags(product)),
            )

            # ===== Compliance Check =====
            content = self._run_compliance_check(content)
            return content

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self._fallback_content(product)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._fallback_content(product)

    def generate_video_content_with_vision(
        self,
        product: Product,
        image_paths: Optional[List[str]] = None,
        language: str = "th",
        video_duration: int = 10,
    ) -> VideoContent:
        """
        สร้างสคริปต์วิดีโอ 10 วินาที ด้วย Gemini Multimodal Vision 100% ตรงปก
        ส่งภาพสินค้าจริงเข้าโมเดลโดยตรง เพื่อให้ AI เห็นภาพแต่ละสไลด์
        และเขียนบทพากย์ที่ตรงกับสิ่งที่เห็นในจอจริง
        """
        candidate_images = []
        if image_paths:
            candidate_images = [p for p in image_paths if p]
        elif product.image_urls:
            candidate_images = [u for u in product.image_urls if u]

        image_inputs = []
        valid_count = 0
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        for img_ref in candidate_images[:3]:
            try:
                b64_data = None
                mime_type = "image/jpeg"
                if os.path.exists(img_ref):
                    with open(img_ref, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode("utf-8")
                    guessed_mime, _ = mimetypes.guess_type(img_ref)
                    if guessed_mime:
                        mime_type = guessed_mime
                elif img_ref.startswith("http://") or img_ref.startswith("https://"):
                    resp = requests.get(img_ref, headers=headers, timeout=12)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        b64_data = base64.b64encode(resp.content).decode("utf-8")
                        mime_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]

                if b64_data:
                    valid_count += 1
                    image_inputs.append({
                        "type": "image",
                        "data": b64_data,
                        "mime_type": mime_type,
                    })
                    image_inputs.append({
                        "type": "text",
                        "text": f"ภาพที่ {valid_count} (สำหรับฉากที่ {valid_count} วินาทีที่ {(valid_count-1)*3.33:.1f} - {valid_count*3.33:.1f})"
                    })
            except Exception as e:
                logger.warning(f"โหลดภาพ {img_ref} สำหรับ Vision ล้มเหลว: {e}")

        # ถ้าไม่มีภาพที่แปลงได้ ให้ส่ง text prompt ตามปกติ
        if not image_inputs:
            product_desc = self._build_product_desc(product)
            prompt = PROMPT_TEMPLATE.format(
                product_name=product.name,
                product_desc=product_desc,
            )
            try:
                interaction = self.client.interactions.create(
                    model=self.MODEL,
                    input=prompt,
                    store=False,
                )
                raw = interaction.output_text or ""
                raw = self._extract_json(raw)
                data = json.loads(raw)
                content = VideoContent(
                    product_name=product.name,
                    hook=data.get("hook", ""),
                    body=data.get("body", ""),
                    cta=data.get("cta", "ดูพิกัดในตะกร้าส้มซ้ายล่างได้เลยนะ"),
                    full_script=data.get("full_script", ""),
                    video_title=data.get("video_title", product.short_name),
                    caption=data.get("caption", ""),
                    hashtags=data.get("hashtags", self._default_hashtags(product)),
                )
                return self._run_compliance_check(content)
            except Exception:
                return self._fallback_content(product)

        product_desc = self._build_product_desc(product)
        prompt_text = PROMPT_VISION_TEMPLATE.format(
            image_count=valid_count,
            product_name=product.name,
            category=product.category or "ทั่วไป",
            product_desc=product_desc,
        )
        image_inputs.append({"type": "text", "text": prompt_text})

        try:
            logger.info(f"👁️ ส่ง {valid_count} ภาพสินค้าจริงให้ Gemini Vision วิเคราะห์และแต่งสคริปต์ตรงปก...")
            interaction = self.client.interactions.create(
                model=self.MODEL,
                input=image_inputs,
                store=False,
            )

            raw = interaction.output_text or ""
            raw = self._extract_json(raw)
            data = json.loads(raw)

            content = VideoContent(
                product_name=product.name,
                hook=data.get("hook", ""),
                body=data.get("body", ""),
                cta=data.get("cta", "ดูพิกัดในตะกร้าส้มซ้ายล่างได้เลยนะ"),
                full_script=data.get("full_script", ""),
                video_title=data.get("video_title", product.short_name),
                caption=data.get("caption", ""),
                hashtags=data.get("hashtags", self._default_hashtags(product)),
                visual_notes=data.get("visual_notes", ""),
            )

            content = self._run_compliance_check(content)
            logger.info(f"✅ Gemini Vision สร้างสคริปต์ตรงปก 100% สำเร็จ! (Notes: {content.visual_notes[:60]})")
            return content

        except Exception as e:
            logger.warning(f"Gemini Vision ขัดข้อง ({e}) — ใช้ Fallback Script")
            return self._fallback_content(product)

    def analyze_product_image(self, product: Product) -> str:
        """
        วิเคราะห์รูปสินค้าด้วย Gemini multimodal
        เพื่อดึงจุดเด่นสำหรับใส่ใน prompt

        Returns:
            คำอธิบายสินค้าจากรูปภาพ (สำหรับ product_desc)
        """
        if not product.image_urls:
            return ""

        try:
            img_url = product.image_urls[0]
            resp = requests.get(img_url, timeout=15)
            resp.raise_for_status()
            img_bytes = resp.content
            mime_type = resp.headers.get("content-type", "image/jpeg")

            interaction = self.client.interactions.create(
                model=self.MODEL,
                input=[
                    {"type": "image", "data": img_bytes, "mime_type": mime_type},
                    {
                        "type": "text",
                        "text": (
                            "วิเคราะห์สินค้าในรูปนี้ สั้นๆ 2–3 ประโยค "
                            "บอกว่าสินค้าคืออะไร ดูดีอย่างไร เหมาะกับใคร "
                            "ห้ามพูดถึงราคาหรือโปรโมชัน"
                        ),
                    },
                ],
                store=False,
            )
            return interaction.output_text or ""

        except Exception as e:
            logger.warning(f"Image analysis skipped: {e}")
            return ""

    # ------------------------------------------------------------------ #
    #  Compliance Check                                                    #
    # ------------------------------------------------------------------ #

    def _run_compliance_check(self, content: VideoContent) -> VideoContent:
        """
        ตรวจ script ว่ามีคำต้องห้าม Shopee หรือไม่
        ถ้าพบ → log warning + ตั้ง compliance_ok = False
        """
        all_text = f"{content.full_script} {content.caption} {content.video_title}".lower()
        violations = []

        for word in BANNED_PRICE_WORDS:
            if word.lower() in all_text:
                violations.append(f"ราคา: '{word}'")

        for word in BANNED_PROMO_WORDS:
            if word.lower() in all_text:
                violations.append(f"โปร: '{word}'")

        for word in BANNED_OVERCLAIM_WORDS:
            if word.lower() in all_text:
                violations.append(f"overclaim: '{word}'")

        for word in BANNED_AUTHORITY_WORDS:
            if word.lower() in all_text:
                violations.append(f"แอบอ้าง: '{word}'")

        if violations:
            logger.warning(
                f"⚠️  Compliance violations พบ {len(violations)} รายการ:\n"
                + "\n".join(f"   • {v}" for v in violations)
            )
            content.compliance_ok = False
        else:
            logger.info("✅ Compliance check ผ่าน — ไม่มีคำต้องห้าม")

        return content

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_product_desc(product: Product) -> str:
        """สร้าง product description สำหรับใส่ใน prompt (ไม่มีราคา)"""
        parts = []
        if product.category:
            parts.append(f"หมวด: {product.category}")
        if product.rating:
            parts.append(f"Rating {product.rating}⭐")
        if product.sold_count:
            parts.append(f"ขายแล้ว {product.sold_count:,} ชิ้น")
        return " | ".join(parts) if parts else product.name

    @staticmethod
    def _extract_json(raw: str) -> str:
        """ดึง JSON ออกจาก markdown code block"""
        if "```json" in raw:
            return raw.split("```json")[1].split("```")[0].strip()
        if "```" in raw:
            return raw.split("```")[1].split("```")[0].strip()
        # fallback: หา { ... } block แรก
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        return match.group(0) if match else raw

    @staticmethod
    def _default_hashtags(product: Product) -> list[str]:
        base = ["shopee", "shopeeth", "ของดีบอกต่อ", "แนะนำสินค้า", "ป้ายยา"]
        cat_tags = {
            "beauty": ["skincare", "beautyreview", "สกินแคร์"],
            "fashion": ["แฟชั่น", "ootd", "เสื้อผ้า"],
            "electronics": ["แกดเจ็ต", "ไอที", "tech"],
            "home": ["ของแต่งบ้าน", "homedecor", "บ้าน"],
        }
        extra = cat_tags.get(product.category.lower(), [])
        return base + extra

    def _fallback_content(self, product: Product) -> VideoContent:
        """Fallback content (Shopee compliant) เมื่อ API มีปัญหา"""
        return VideoContent(
            product_name=product.name,
            hook=f"แก คือเพิ่งรู้จักอันนี้มาไม่นาน...",
            body=f"{product.short_name} ใช้งานง่ายมาก เอาไปเลย",
            cta="ดูพิกัดในตะกร้าส้มซ้ายล่างได้เลยนะ 🧡",
            full_script=(
                f"แก คือเพิ่งรู้จักอันนี้มาไม่นาน "
                f"{product.short_name} ใช้งานง่ายมาก "
                f"ดูพิกัดในตะกร้าส้มซ้ายล่างได้เลยนะ"
            ),
            video_title=f"แนะนำ! {product.short_name[:35]}",
            caption=f"แนะนำเลย! {product.short_name[:50]}\nดูในตะกร้าส้มซ้ายล่างได้เลย 🛒",
            hashtags=self._default_hashtags(product),
            compliance_ok=True,
        )
