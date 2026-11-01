"""
video_creator.py
----------------
สร้างวิดีโอ Shopee-style ด้วย FFmpeg (ฟรี 100%)

Phase 1 Spec:
  - ความยาว: 10 วินาทีพอดี
  - Canvas: 1080×1920 (9:16 แนวตั้ง)
  - รูปสินค้า: 3 รูป × 3.33 วินาที = 10 วินาที
  - Safe Zone: เว้นพื้นที่ล่าง 25% (ไม่บัง UI ตะกร้าส้ม Shopee)
  - Text Layout: hook บนสุด, body กลาง, cta กลางซ้ายล่าง (ในขอบ safe zone)

ต้องติดตั้ง FFmpeg ก่อน:
  - Windows: winget install ffmpeg
  - หรือ: https://ffmpeg.org/download.html
"""
import os
import subprocess
import logging
import requests
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from src.shopee_scraper import Product
from src.gemini_generator import VideoContent

logger = logging.getLogger(__name__)

# ============================================================
# Phase 1 Constants
# ============================================================
VIDEO_WIDTH = 1080          # px (9:16)
VIDEO_HEIGHT = 1920         # px
VIDEO_FPS = 30
VIDEO_DURATION = 10         # วินาที (Phase 1 fixed)
SLIDE_COUNT = 3             # จำนวนรูปสินค้า
SLIDE_DURATION = VIDEO_DURATION / SLIDE_COUNT  # = 3.333... วิ/รูป

# Safe Zone — ล่าง 25% ของจอ = 480px ห้ามมีข้อความ (UI Shopee อยู่ที่นั่น)
SAFE_ZONE_BOTTOM_PX = int(VIDEO_HEIGHT * 0.25)          # 480px จากล่าง
SAFE_ZONE_TOP_LIMIT = VIDEO_HEIGHT - SAFE_ZONE_BOTTOM_PX  # y = 1440

# Text Y positions (อยู่ใน safe zone บน)
TEXT_HOOK_Y = 60            # hook — บนสุด
TEXT_BODY_Y = 180           # body — กลางบน
TEXT_CTA_Y = SAFE_ZONE_TOP_LIMIT - 120  # CTA — แนวล่างสุดของ safe zone

# Text sizes
FONTSIZE_HOOK = 58
FONTSIZE_BODY = 46
FONTSIZE_CTA = 42
FONTSIZE_BADGE = 36


@dataclass
class VideoResult:
    product_name: str
    video_path: str
    thumbnail_path: str
    duration: float  # วินาที
    file_size_mb: float
    compliance_ok: bool = True


class FFmpegVideoCreator:
    """
    สร้างวิดีโอ 10 วินาที 1080×1920 จากรูปสินค้า + text overlay

    Layout แนวตั้ง (1080×1920):
    ┌────────────────────────┐  ← y=0
    │  🔥 HOOK TEXT (y=60)  │
    │                        │
    │     รูปสินค้า          │  ← ภาพเต็มพื้นที่
    │                        │
    │  📝 BODY TEXT (y=180) │
    │                        │
    │  👉 CTA TEXT (y=1320) │  ← อยู่ใน safe zone
    ├────────────────────────┤  ← y=1440 (safe zone boundary)
    │   ❌ NO TEXT ZONE      │  ← ล่าง 25% = UI Shopee
    │   (ตะกร้าส้ม, ปุ่ม)  │
    └────────────────────────┘  ← y=1920
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.font_path = self._find_thai_font()
        self._check_ffmpeg()

    # ------------------------------------------------------------------ #
    #  Setup                                                               #
    # ------------------------------------------------------------------ #

    def _check_ffmpeg(self):
        import shutil, glob
        # ถ้าไม่มีใน PATH ให้ค้นหาในตำแหน่งมาตรฐานของ Windows / WinGet
        if not shutil.which("ffmpeg"):
            user_profile = os.environ.get("USERPROFILE", "")
            winget_pattern = os.path.join(user_profile, r"AppData\Local\Microsoft\WinGet\Packages\**\ffmpeg.exe")
            matches = glob.glob(winget_pattern, recursive=True)
            if matches:
                ffmpeg_dir = os.path.dirname(matches[0])
                os.environ["PATH"] = f"{ffmpeg_dir};" + os.environ.get("PATH", "")
                logger.info(f"ค้นพบ FFmpeg จาก WinGet: {matches[0]}")

        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
            if result.returncode != 0:
                raise RuntimeError("FFmpeg returncode != 0")
        except Exception:
            raise RuntimeError(
                "FFmpeg ไม่พบในระบบ!\n"
                "ติดตั้ง: winget install ffmpeg\n"
                "หรือ: https://ffmpeg.org/download.html"
            )
        logger.info("FFmpeg ✓")

    def _find_thai_font(self) -> str:
        candidates = [
            r"C:\Windows\Fonts\THSarabunNew.ttf",
            r"C:\Windows\Fonts\Tahoma.ttf",
            r"C:\Windows\Fonts\Arial Unicode MS.ttf",
            r"C:\Windows\Fonts\Arial.ttf",
            "/usr/share/fonts/truetype/thai/Garuda.ttf",
            "/usr/share/fonts/truetype/tlwg/TlwgTypist.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            str(Path(__file__).parent.parent / "assets/fonts/NotoSansThai-Regular.ttf"),
        ]
        for f in candidates:
            if os.path.exists(f):
                logger.info(f"Font: {f}")
                return f
        logger.warning("ไม่พบ Thai font — ใช้ default (ข้อความอาจแสดงไม่ถูกต้อง)")
        return "Arial"

    # ------------------------------------------------------------------ #
    #  Download Images                                                     #
    # ------------------------------------------------------------------ #

    def download_images(self, product: Product, tmp_dir: str) -> list[str]:
        """ดาวน์โหลดรูปสินค้า หรือใช้ไฟล์ภาพจากเครื่องในโฟลเดอร์ inputs/"""
        paths = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # 1. ตรวจสอบว่า image_urls เป็นไฟล์ในเครื่องหรือ URL
        for i, url in enumerate(product.image_urls[:SLIDE_COUNT]):
            if not url:
                continue
            # กรณีระบุเป็นไฟล์ในเครื่อง
            if os.path.exists(url):
                paths.append(os.path.abspath(url))
                logger.info(f"  📸 ใช้รูปสินค้าจากเครื่อง: {url}")
                continue
            # กรณีเป็น URL จากอินเทอร์เน็ต
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                img_path = os.path.join(tmp_dir, f"product_{i:02d}.jpg")
                with open(img_path, "wb") as f:
                    f.write(resp.content)
                paths.append(img_path)
                logger.info(f"  รูป {i+1}: {url[:60]}...")
            except Exception as e:
                logger.warning(f"  ดาวน์โหลดรูป {i+1} ไม่สำเร็จ ({e})")

        # 2. ถ้ายังไม่มีรูป ลองตรวจดูในโฟลเดอร์ inputs/ (กรณีผู้ใช้วางไฟล์รูปไว้เอง)
        inputs_dir = Path("inputs")
        if not paths and inputs_dir.exists():
            local_imgs = [
                str(p.resolve())
                for p in inputs_dir.glob("*")
                if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
            ]
            if local_imgs:
                paths = local_imgs[:SLIDE_COUNT]
                logger.info(f"  📂 พบภาพสินค้าในโฟลเดอร์ inputs/ จำนวน {len(paths)} ภาพ:")
                for p in paths:
                    logger.info(f"     • {p}")

        # 3. ถ้ายังไม่มีรูป ให้วิเคราะห์ชื่อสินค้าเพื่อดึงภาพถ่ายสินค้าจริงตรงแบรนด์ ตรงรุ่น 100%
        if not paths:
            from src.trend_researcher import get_accurate_images_for_product
            accurate_urls = get_accurate_images_for_product(product.name, product.category)
            logger.info(f"  🎯 จับคู่ภาพสินค้าจริงตรงรุ่นสำหรับ: '{product.short_name[:30]}' ({len(accurate_urls)} ภาพ)")
            for i, u in enumerate(accurate_urls[:SLIDE_COUNT]):
                try:
                    resp = requests.get(u, headers=headers, timeout=10)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        img_path = os.path.join(tmp_dir, f"accurate_{i:02d}.jpg")
                        with open(img_path, "wb") as f:
                            f.write(resp.content)
                        paths.append(img_path)
                except Exception as e:
                    logger.warning(f"  ดาวน์โหลดภาพตรงรุ่น {i+1} ไม่สำเร็จ: {e}")

        return paths

        return paths

    # ------------------------------------------------------------------ #
    #  Main Create Video                                                   #
    # ------------------------------------------------------------------ #

    def create_video(
        self,
        product: Product,
        content: VideoContent,
        image_paths: list[str],
        template: str = "clean",
        voice_audio_path: Optional[str] = None,
        bgm_audio_path: Optional[str] = None,
    ) -> VideoResult:
        """
        สร้างวิดีโอ 10 วินาที 1080×1920 (Phase 1 spec)
        รองรับ Template สไตล์วิดีโอ, เสียงพากย์ AI ภาษาไทย และเพลง BGM

        ขั้นตอน:
        1. Resize รูปให้ fill เต็ม canvas 1080×1920
        2. สร้าง slideshow 3 รูป × 3.33 วิ = 10 วิ
        3. วาง text overlay (hook / body / cta) ใน safe zone ตาม template
        4. รวมเสียงพากย์ AI + เพลง BGM (ถ้ามี)
        5. Export MP4 พร้อม thumbnail
        """
        if not image_paths:
            raise ValueError("ไม่มีรูปสินค้า — ไม่สามารถสร้างวิดีโอได้")

        # ชื่อไฟล์ output ใช้ product ID เพื่อความแน่นอนบน Windows และ Mobile
        output_path = str(self.output_dir / f"product_{product.item_id}.mp4")
        thumbnail_path = str(self.output_dir / f"product_{product.item_id}_thumb.jpg")

        with tempfile.TemporaryDirectory() as tmp:

            # === Step 1: Resize รูปให้ fill 1080×1920 (cover, crop กลาง) ===
            resized_paths = self._resize_images(image_paths, tmp)

            # === Step 2: เติมรูปให้ครบ SLIDE_COUNT ===
            resized_paths = self._pad_images_to_count(resized_paths, SLIDE_COUNT)

            # === Step 3: สร้าง slideshow + text overlay + xfade + audio ===
            self._build_final_video(
                resized_paths,
                content,
                output_path,
                template=template,
                voice_audio_path=voice_audio_path,
                bgm_audio_path=bgm_audio_path,
            )

            # === Step 4: Thumbnail ===
            self._extract_thumbnail(output_path, thumbnail_path)

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"✅ วิดีโอ 10 วิ: {output_path} ({size_mb:.1f} MB)")

        return VideoResult(
            product_name=product.name,
            video_path=output_path,
            thumbnail_path=thumbnail_path,
            duration=VIDEO_DURATION,
            file_size_mb=size_mb,
            compliance_ok=content.compliance_ok,
        )

    # ------------------------------------------------------------------ #
    #  FFmpeg Steps                                                        #
    # ------------------------------------------------------------------ #

    def _resize_images(self, image_paths: list[str], tmp: str) -> list[str]:
        """ปรับขนาดภาพสินค้าให้อยู่ในสัดส่วน 1080x1920 พร้อมพื้นหลังเบลอสวยงามระดับมืออาชีพ"""
        resized = []
        for i, img in enumerate(image_paths):
            out = os.path.join(tmp, f"resized_{i:02d}.jpg")
            # ใช้พื้นหลังภาพเบลอ (Cinematic Blur) + ภาพสินค้าตัวจริงคมชัดตรงกลาง ไม่โดนตัดขอบ
            vf = (
                f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},boxblur=25:5[bg];"
                f"[0:v]scale={VIDEO_WIDTH - 80}:{VIDEO_HEIGHT - 650}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2-40"
            )
            cmd = ["ffmpeg", "-y", "-i", img, "-filter_complex", vf, "-q:v", "2", out]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode == 0:
                resized.append(out)
            else:
                logger.warning(f"resize ล้มเหลวสำหรับรูป {i}: {result.stderr[-200:]}")
        return resized

    def _pad_images_to_count(self, paths: list[str], target: int) -> list[str]:
        """ถ้ารูปน้อยกว่า target ให้วนซ้ำ"""
        if not paths:
            raise ValueError("ไม่มีรูปสินค้า")
        while len(paths) < target:
            paths = paths + paths
        return paths[:target]

    @staticmethod
    def _wrap_thai_text(text: str, max_len: int = 25) -> list[str]:
        """แบ่งข้อความภาษาไทยยาวๆ ให้เป็น 1 หรือ 2 บรรทัดพอดีคำ ไม่ให้ตกขอบจอ"""
        if not text:
            return [""]
        text = text.strip()
        if len(text) <= max_len:
            return [text]

        mid = len(text) // 2
        delimiters = [' ', '!', '?', ',', 'และ', 'ที่', 'มี', 'ให้', 'ช่วย', 'ได้', 'มาก', 'เลย', 'นะ', 'พิกัด']
        best_idx = -1
        best_dist = 999
        for d in delimiters:
            pos = text.find(d, max(0, mid - 10))
            if pos != -1 and abs(pos - mid) < best_dist and pos < max_len + 8:
                best_dist = abs(pos - mid)
                best_idx = pos + (1 if d == ' ' else 0)

        if best_idx != -1 and best_idx > 5:
            return [text[:best_idx].strip(), text[best_idx:].strip()]
        return [text[:max_len].strip(), text[max_len:].strip()]

    def _build_text_overlay_filter(self, content: VideoContent, template: str = "clean") -> str:
        """
        สร้าง FFmpeg drawtext filter chain แบบ TikTok-style Animated Dynamic Subtitles
        - Slide 1 (0.0s – 3.33s): Hook Headline เด้ง Pop-in + ซับไตเติลคาราโอเกะ
        - Slide 2 (3.33s – 6.66s): Body Feature เด้ง Pop-in + ซับไตเติลจุดเด่น
        - Slide 3 (6.66s – 10.0s): CTA เด้ง Pop-in + ป้ายตะกร้าส้ม Shopee ดิ้นกระตุ้นการสั่งซื้อ
        """
        font = self.font_path.replace("\\", "/").replace(":", "\\:")

        # ป้ายการันตี Shopee Video Exclusive บนสุดตลอดทั้งคลิป (0-10s)
        badge_text = self._esc("🏷️ Shopee Video Exclusive | การันตีของแท้")

        filters = []

        # 1. ป้าย Shopee Video Header Badge บนสุด
        filters.append(
            f"drawtext=fontfile='{font}':text='{badge_text}'"
            f":fontcolor=white:fontsize=30"
            f":x=(w-text_w)/2:y=35"
            f":box=1:boxborderw=8:boxcolor=0x000000@0.60"
        )

        # ตัดบรรทัดข้อความให้พอดีจอ
        hook_lines = self._wrap_thai_text(content.hook[:50], max_len=24)
        body_lines = self._wrap_thai_text(content.body[:52], max_len=24)
        cta_lines = self._wrap_thai_text(content.cta[:44], max_len=24)

        # กำหนดชุดสีตามสไตล์ Template
        if template in ["tiktok_bounce", "3d_motion"]:
            # TikTok Viral Pop / Dynamic Bounce
            hook_bg = "0xFF0055@0.96"  # แดงชมพู TikTok สด
            hook_color = "white"
            hook_border = "borderw=6:bordercolor=0x000000"

            body_bg = "0x00E5FF@0.95"  # ฟ้านีออน TikTok
            body_color = "0x0F172A"
            body_border = "borderw=6:bordercolor=0x000000"

            cta_bg = "0xFFE600@0.98"   # เหลืองนีออน ปักตะกร้า
            cta_color = "0x0F172A"
            cta_border = "borderw=6:bordercolor=0x000000"
        elif template == "retro_tv":
            # Retro TV Shopping (สไตล์ Triple Bot ไวรัล)
            hook_bg = "0xD32F2F@0.96"  # แดงเลือดหมูคลาสสิก
            hook_color = "0xFFEB3B"    # เหลืองสดแนวทีวีแชมป์เปี้ยน
            hook_border = "borderw=6:bordercolor=white"

            body_bg = "0x1976D2@0.92"  # น้ำเงินคลาสสิกทีวี
            body_color = "white"
            body_border = "borderw=6:bordercolor=white"

            cta_bg = "0xE65100@0.98"   # ส้มเข้มวินเทจ
            cta_color = "0xFFEB3B"
            cta_border = "borderw=6:bordercolor=white"
        elif template == "luxury_glow":
            # Luxury Glow / เครื่องสำอาง น้ำหอม สินค้าหรู
            hook_bg = "0x1A1A1A@0.94"  # ดำชาร์โคล
            hook_color = "0xF5E6C8"    # ทองแชมเปญ
            hook_border = "borderw=4:bordercolor=0xD4AF37"

            body_bg = "0x2A2421@0.92"  # น้ำตาลอบอุ่นหรูหรา
            body_color = "white"
            body_border = "borderw=4:bordercolor=0xD4AF37"

            cta_bg = "0xD4AF37@0.96"   # ทองแท้
            cta_color = "0x1A1A1A"
            cta_border = "borderw=4:bordercolor=white"
        elif template == "clean_unboxing":
            # Clean Unboxing / สไตล์แกะกล่อง โมเดิร์น
            hook_bg = "0x2563EB@0.95"  # น้ำเงินโมเดิร์น
            hook_color = "white"
            hook_border = "borderw=4:bordercolor=0x1E40AF"

            body_bg = "0x0F172A@0.90"  # ดำคลีน
            body_color = "white"
            body_border = "borderw=4:bordercolor=0x334155"

            cta_bg = "0x10B981@0.96"   # เขียวสด ปักตะกร้าชัวร์
            cta_color = "white"
            cta_border = "borderw=4:bordercolor=0x065F46"
        elif template == "neon":
            # Neon Pop / Flash Sale
            hook_bg = "0xFFE600@0.96"  # เหลืองนีออน
            hook_color = "0x0F172A"     # ดำเข้ม
            hook_border = "borderw=6:bordercolor=0x0F172A"

            body_bg = "0xFF0055@0.90"  # ชมพูมาเจนต้า
            body_color = "white"
            body_border = "borderw=6:bordercolor=0x0F172A"

            cta_bg = "0x00E5FF@0.95"   # ฟ้านีออน
            cta_color = "0x0F172A"
            cta_border = "borderw=6:bordercolor=0x0F172A"
        elif template == "minimal":
            # Korean Minimal Aesthetic
            hook_bg = "0xF8FAFC@0.95"  # ครีมขาวนวล
            hook_color = "0x1E293B"    # สเลทชาร์โคล
            hook_border = "borderw=2:bordercolor=0xCBD5E1"

            body_bg = "0x334155@0.88"  # เทาหรู
            body_color = "white"
            body_border = "borderw=2:bordercolor=0x475569"

            cta_bg = "0x0F172A@0.92"   # ดำมินิมอล
            cta_color = "white"
            cta_border = "borderw=2:bordercolor=0x334155"
        else:
            # Shopee Clean (Default)
            hook_bg = "0xEE4D2D@0.95"  # ส้ม Shopee สด
            hook_color = "white"
            hook_border = "borderw=5:bordercolor=black"

            body_bg = "0x0F172A@0.88"  # มิดไนท์แบล็ค คมชัด
            body_color = "white"
            body_border = "borderw=5:bordercolor=black"

            cta_bg = "0xEE4D2D@0.98"   # ส้ม Shopee เน้นย้ำ
            cta_color = "white"
            cta_border = "borderw=5:bordercolor=black"

        # ========================================================
        # SLIDE 1: HOOK (0.0s – 3.33s)
        # ========================================================
        for line_idx, line in enumerate(hook_lines):
            line_esc = self._esc(line)
            y_base = 150 if len(hook_lines) == 1 else (120 + line_idx * 72)
            filters.append(
                f"drawtext=fontfile='{font}':text='{line_esc}'"
                f":fontcolor={hook_color}:fontsize={FONTSIZE_HOOK}:box=1:boxborderw=15:boxcolor={hook_bg}"
                f":{hook_border}"
                f":x=(w-text_w)/2:y='{y_base}+22*max(0,1-t/0.18)'"
                f":alpha='min(1,t/0.15)':enable='between(t,0,3.33)'"
            )

        # TikTok Dynamic Subtitle (Lower safe zone y=1340) for Slide 1
        sub1_esc = self._esc(content.hook[:44])
        filters.append(
            f"drawtext=fontfile='{font}':text='{sub1_esc}'"
            f":fontcolor=white:fontsize=44:borderw=5:bordercolor=black"
            f":box=1:boxborderw=12:boxcolor=0x000000@0.75"
            f":x=(w-text_w)/2:y=1340"
            f":alpha='min(1,t/0.15)':enable='between(t,0,3.33)'"
        )

        # ========================================================
        # SLIDE 2: BODY / FEATURES (3.33s – 6.66s)
        # ========================================================
        for line_idx, line in enumerate(body_lines):
            line_esc = self._esc(line)
            y_base = 150 if len(body_lines) == 1 else (120 + line_idx * 70)
            filters.append(
                f"drawtext=fontfile='{font}':text='{line_esc}'"
                f":fontcolor={body_color}:fontsize={FONTSIZE_BODY}:box=1:boxborderw=14:boxcolor={body_bg}"
                f":{body_border}"
                f":x=(w-text_w)/2:y='{y_base}+22*max(0,1-(t-3.33)/0.18)'"
                f":alpha='min(1,(t-3.33)/0.15)':enable='between(t,3.33,6.66)'"
            )

        # TikTok Dynamic Subtitle (Lower safe zone y=1340) for Slide 2
        sub2_esc = self._esc(content.body[:46])
        filters.append(
            f"drawtext=fontfile='{font}':text='{sub2_esc}'"
            f":fontcolor=white:fontsize=44:borderw=5:bordercolor=black"
            f":box=1:boxborderw=12:boxcolor=0x000000@0.75"
            f":x=(w-text_w)/2:y=1340"
            f":alpha='min(1,(t-3.33)/0.15)':enable='between(t,3.33,6.66)'"
        )

        # ========================================================
        # SLIDE 3: CTA & BASKET (6.66s – 10.0s)
        # ========================================================
        for line_idx, line in enumerate(cta_lines):
            line_esc = self._esc(line)
            y_base = 150 if len(cta_lines) == 1 else (120 + line_idx * 70)
            filters.append(
                f"drawtext=fontfile='{font}':text='{line_esc}'"
                f":fontcolor={cta_color}:fontsize={FONTSIZE_CTA}:box=1:boxborderw=15:boxcolor={cta_bg}"
                f":{cta_border}"
                f":x=(w-text_w)/2:y='{y_base}+22*max(0,1-(t-6.66)/0.18)'"
                f":alpha='min(1,(t-6.66)/0.15)':enable='between(t,6.66,10)'"
            )

        # Animated Bouncing Orange Basket CTA Button Sticker (y=1290) for Slide 3
        cart_badge = self._esc("🟠 จิ้มตะกร้าส้มซ้ายล่าง ด่วนก่อนหมด! 🛒")
        filters.append(
            f"drawtext=fontfile='{font}':text='{cart_badge}'"
            f":fontcolor=white:fontsize=46:borderw=6:bordercolor=black"
            f":box=1:boxborderw=16:boxcolor=0xEE4D2D@0.98"
            f":x=(w-text_w)/2:y='1290-10*abs(sin((t-6.66)*6))'"
            f":alpha='min(1,(t-6.66)/0.15)':enable='between(t,6.66,10)'"
        )

        return ",".join(filters)

    def _build_final_video(
        self,
        image_paths: list[str],
        content: VideoContent,
        output_path: str,
        template: str = "clean",
        voice_audio_path: Optional[str] = None,
        bgm_audio_path: Optional[str] = None,
    ):
        """
        สร้างวิดีโอสุดท้าย 10 วินาที ด้วย xfade transition + text overlay + audio mix
        """
        n = len(image_paths)  # = SLIDE_COUNT = 3
        xfade_dur = 0.5

        # แต่ละภาพต้องมี duration อย่างน้อย SLIDE_DURATION + 2 วินาที เพื่อให้ xfade ต่อเนื่องพอดี
        slide_in_dur = SLIDE_DURATION + xfade_dur + 1.0

        # inputs
        inputs = []
        for p in image_paths:
            inputs += ["-loop", "1", "-t", f"{slide_in_dur:.4f}", "-i", p]

        filter_parts = []
        is_dynamic_motion = template in ["tiktok_bounce", "3d_motion", "retro_tv", "luxury_glow", "clean_unboxing", "neon_pop", "clean"]

        if is_dynamic_motion:
            # ========================================================
            # 3D Motion Graphic Engine: Ambient Blur BG + Floating 3D Product
            # ========================================================
            for i in range(n):
                filter_parts.append(f"[{i}:v]split=2[bg_raw_{i}][fg_raw_{i}]")

                # Background: Ambient Blur + Contrast Dim (ป้องกันภาพยืดหรือครอบตัด)
                filter_parts.append(
                    f"[bg_raw_{i}]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                    f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
                    f"boxblur=24:10,colorchannelmixer=0.62:0:0:0:0:0.62:0:0:0:0:0.62,"
                    f"fps={VIDEO_FPS},format=yuv420p[bg_{i}]"
                )

                # Foreground: Dynamic Product Motion ตาม Template
                if template in ["tiktok_bounce", "3d_motion"]:
                    # เด้งดึ๋ง 3D Bounce + Dynamic Tilt (หมุนเอียงมีมิติ)
                    filter_parts.append(
                        f"[fg_raw_{i}]scale=850:850:force_original_aspect_ratio=decrease,"
                        f"format=rgba,rotate='0.038*sin(2*PI*t*1.2)':ow='hypot(iw,ih)':oh='ow':c=none[fg_{i}]"
                    )
                    filter_parts.append(
                        f"[bg_{i}][fg_{i}]overlay=(W-w)/2:'(H-h)/2 - 50 + 26*sin(2*PI*t*1.4)':eval=frame,"
                        f"fps={VIDEO_FPS},format=yuv420p[v{i}]"
                    )
                elif template == "retro_tv":
                    # ทีวีช็อปปิ้ง ย้อนยุค (Triple Bot): กล้องโยกไหวแบบวินเทจ
                    filter_parts.append(
                        f"[fg_raw_{i}]scale=830:830:force_original_aspect_ratio=decrease,format=rgba[fg_{i}]"
                    )
                    filter_parts.append(
                        f"[bg_{i}][fg_{i}]overlay='(W-w)/2 + 6*sin(2*PI*t*2.2)':'(H-h)/2 - 50 + 7*cos(2*PI*t*1.8)':eval=frame,"
                        f"fps={VIDEO_FPS},format=yuv420p[v{i}]"
                    )
                elif template == "luxury_glow":
                    # Luxury Glow: ลอยละมุนสโลว์โมชัน นุ่มนวล
                    filter_parts.append(
                        f"[fg_raw_{i}]scale=840:840:force_original_aspect_ratio=decrease,format=rgba[fg_{i}]"
                    )
                    filter_parts.append(
                        f"[bg_{i}][fg_{i}]overlay=(W-w)/2:'(H-h)/2 - 45 + 15*sin(2*PI*t*0.9)':eval=frame,"
                        f"fps={VIDEO_FPS},format=yuv420p[v{i}]"
                    )
                elif template == "clean_unboxing":
                    # แกะกล่อง Unboxing: ค่อยๆ ซูมเน้นรายละเอียดสินค้า
                    filter_parts.append(
                        f"[fg_raw_{i}]scale=840:840:force_original_aspect_ratio=decrease,"
                        f"scale=w='iw*(1+0.05*t/{slide_in_dur:.2f})':h='ih*(1+0.05*t/{slide_in_dur:.2f})':eval=frame,format=rgba[fg_{i}]"
                    )
                    filter_parts.append(
                        f"[bg_{i}][fg_{i}]overlay=(W-w)/2:'(H-h)/2 - 50':eval=frame,"
                        f"fps={VIDEO_FPS},format=yuv420p[v{i}]"
                    )
                else:
                    # Shopee Clean / Neon
                    filter_parts.append(
                        f"[fg_raw_{i}]scale=850:850:force_original_aspect_ratio=decrease,"
                        f"format=rgba,rotate='0.025*sin(2*PI*t*1.0)':ow='hypot(iw,ih)':oh='ow':c=none[fg_{i}]"
                    )
                    filter_parts.append(
                        f"[bg_{i}][fg_{i}]overlay=(W-w)/2:'(H-h)/2 - 50 + 20*sin(2*PI*t*1.2)':eval=frame,"
                        f"fps={VIDEO_FPS},format=yuv420p[v{i}]"
                    )

            # กำหนดประเภท Transition ให้เข้ากับแต่ละสไตล์
            if template in ["tiktok_bounce", "3d_motion"]:
                trans_type = "slideleft"
            elif template == "retro_tv":
                trans_type = "wipeleft"
            elif template == "luxury_glow":
                trans_type = "smoothleft"
            else:
                trans_type = "fade"

            # xfade chain
            prev = "v0"
            for i in range(1, n):
                offset = SLIDE_DURATION * i
                nxt = f"xf{i}" if i < n - 1 else "xfall"
                filter_parts.append(
                    f"[{prev}][v{i}]xfade=transition={trans_type}"
                    f":duration={xfade_dur}:offset={offset:.4f}[{nxt}]"
                )
                prev = nxt

        else:
            # Fallback Ken Burns Slideshow สำหรับ Classic
            for i in range(n):
                if i % 2 == 0:
                    zoom_filter = (
                        f"scale=w='{VIDEO_WIDTH}*(1+0.05*t/{slide_in_dur:.2f})':"
                        f"h='{VIDEO_HEIGHT}*(1+0.05*t/{slide_in_dur:.2f})':eval=frame,"
                        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(in_w-{VIDEO_WIDTH})/2:(in_h-{VIDEO_HEIGHT})/2"
                    )
                else:
                    zoom_filter = (
                        f"scale=w='{VIDEO_WIDTH}*(1.05-0.05*t/{slide_in_dur:.2f})':"
                        f"h='{VIDEO_HEIGHT}*(1.05-0.05*t/{slide_in_dur:.2f})':eval=frame,"
                        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(in_w-{VIDEO_WIDTH})/2:(in_h-{VIDEO_HEIGHT})/2"
                    )

                filter_parts.append(
                    f"[{i}:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
                    f"force_original_aspect_ratio=increase,"
                    f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
                    f"{zoom_filter},"
                    f"fps={VIDEO_FPS},"
                    f"format=yuv420p[v{i}]"
                )

            # xfade chain
            prev = "v0"
            for i in range(1, n):
                offset = SLIDE_DURATION * i
                nxt = f"xf{i}" if i < n - 1 else "xfall"
                filter_parts.append(
                    f"[{prev}][v{i}]xfade=transition=fade"
                    f":duration={xfade_dur}:offset={offset:.4f}[{nxt}]"
                )
                prev = nxt

        # text overlay บน xfall
        text_filter = self._build_text_overlay_filter(content, template=template)
        filter_parts.append(f"[xfall]{text_filter},format=yuv420p[vout]")

        # Audio routing
        audio_inputs = []
        has_voice = voice_audio_path and os.path.exists(voice_audio_path)
        has_bgm = bgm_audio_path and os.path.exists(bgm_audio_path)

        curr_audio_idx = n
        voice_idx = None
        bgm_idx = None

        if has_voice:
            audio_inputs += ["-i", voice_audio_path]
            voice_idx = curr_audio_idx
            curr_audio_idx += 1
        if has_bgm:
            audio_inputs += ["-stream_loop", "-1", "-i", bgm_audio_path]
            bgm_idx = curr_audio_idx
            curr_audio_idx += 1

        if has_voice and has_bgm:
            # Smart Audio Ducking: ใช้ asplit แยกเสียงพากย์เพื่อเป็นทั้งเสียงหลัก และตัวทริกเกอร์ sidechaincompress หรี่ BGM
            filter_parts.append(f"[{voice_idx}:a]aformat=channel_layouts=stereo:sample_rates=44100,volume=1.0,asplit=2[va_main][va_trigger]")
            filter_parts.append(f"[{bgm_idx}:a]aformat=channel_layouts=stereo:sample_rates=44100,volume=0.22[bgm_in]")
            filter_parts.append(f"[bgm_in][va_trigger]sidechaincompress=threshold=0.08:ratio=4:attack=50:release=350[bgm_ducked]")
            filter_parts.append(f"[va_main][bgm_ducked]amix=inputs=2:duration=first[aout]")
            audio_map = "[aout]"
        elif has_voice:
            filter_parts.append(f"[{voice_idx}:a]volume=1.0[aout]")
            audio_map = "[aout]"
        elif has_bgm:
            filter_parts.append(f"[{bgm_idx}:a]volume=0.32[aout]")
            audio_map = "[aout]"
        else:
            audio_inputs += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
            audio_map = f"{n}:a"

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
        ] + inputs + audio_inputs + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", audio_map,
            "-c:v", "libx264",
            "-profile:v", "high",
            "-level", "4.1",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            "-t", str(VIDEO_DURATION),
            "-movflags", "+faststart",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            logger.warning(f"xfade ล้มเหลว ({result.stderr[-300:]}) — ลอง concat fallback")
            self._build_video_concat_fallback(image_paths, content, output_path)

    def _build_video_concat_fallback(
        self,
        image_paths: list[str],
        content: VideoContent,
        output_path: str,
    ):
        """Fallback: concat ธรรมดา + drawtext (ไม่มี transition)"""
        with tempfile.TemporaryDirectory() as tmp2:
            # สร้าง segment clips
            clips = []
            for i, img in enumerate(image_paths):
                clip = os.path.join(tmp2, f"clip_{i}.mp4")
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-t", f"{SLIDE_DURATION:.3f}", "-i", img,
                    "-vf", (
                        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
                        f"force_original_aspect_ratio=increase,"
                        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
                        f"fps={VIDEO_FPS},format=yuv420p"
                    ),
                    "-c:v", "libx264", "-preset", "ultrafast",
                    clip,
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                clips.append(clip)

            # concat list
            list_path = os.path.join(tmp2, "list.txt")
            with open(list_path, "w") as f:
                for c in clips:
                    clean_c = c.replace("\\", "/")
                    f.write(f"file '{clean_c}'\n")

            # concat + drawtext
            text_filter = self._build_text_overlay_filter(content)
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", list_path,
                "-vf", text_filter,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-t", str(VIDEO_DURATION),
                "-movflags", "+faststart",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg fallback error:\n{result.stderr[-500:]}")

    def _extract_thumbnail(self, video_path: str, thumbnail_path: str):
        """สร้าง thumbnail จากวิดีโอ (กลางคลิป)"""
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ss", "1",
            "-vframes", "1",
            "-q:v", "2",
            thumbnail_path,
        ]
        subprocess.run(cmd, capture_output=True)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _esc(text: str) -> str:
        """Escape text สำหรับ FFmpeg drawtext"""
        return (
            text
            .replace("\\", "\\\\")
            .replace("%", " เปอร์เซ็นต์")
            .replace("'", "\u2019")   # แทน ' ด้วย right single quote
            .replace(":", "\\:")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace(",", "\\,")
        )
