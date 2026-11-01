"""
ai_video_engine.py
ระบบจัดการโมเดลสร้างวิดีโอ (Video Generation Engines):
1. Option A (Native 3D Motion Graphic Engine):
   - ไม่ต้องเสียค่า API ภายนอก ทำงานในเครื่องทันที 5-10 วินาที
   - ทำให้สินค้าลอย เด้งดึ๋ง (Bounce), หมุนเอียง 3D (3D Tilt Parallax), และมีแสงสะท้อน (Shine/Flare)
   - แบ็กกราวด์แบบ Ambient Blur Pulse ป้องกันภาพสินค้าโดนครอบตัด
   - สติกเกอร์/ป้ายยอดฮิตเด้งดึ๋ง (🔥 สินค้ากระแส, ⭐ 4.9 ดาว, 🚚 ส่งฟรี)
   - สไตล์: tiktok_bounce, retro_tv (สไตล์ Triple Bot), luxury_glow, clean_unboxing, neon_pop

2. Option B (External AI Image-to-Video Bridge):
   - รองรับโมเดล AI Image-to-Video ชั้นนำ:
     * MiniMax (Hailuo AI video-01)
     * Luma Dream Machine (Ray)
     * Kling AI (Image2Video)
     * Google Veo 2 (Vertex AI / Google GenAI)
   - ระบบจัดเก็บ API Keys (BYOK - Bring Your Own Key) ใน data/ai_models_config.json
   - ระบบ Auto-Poll ตรวจจับสถานะจนได้ไฟล์ .mp4 พร้อมดาวน์โหลดและส่งต่อ
   - มีระบบ Fallback อัตโนมัติกลับมาที่ Native 3D Motion หาก API มีปัญหา
"""

import os
import json
import time
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "data" / "ai_models_config.json"


def get_ai_models_config() -> Dict[str, Any]:
    """โหลดการตั้งค่า API Keys ของโมเดลภายนอก"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read ai_models_config: {e}")
    return {}


def save_ai_models_config(config: Dict[str, Any]) -> bool:
    """บันทึกการตั้งค่า API Keys"""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save ai_models_config: {e}")
        return False


def get_available_engines() -> Dict[str, Any]:
    """ตรวจสอบสถานะของทุก Engine และโมเดลที่มีให้เลือก"""
    cfg = get_ai_models_config()

    luma_key = cfg.get("luma_api_key") or os.environ.get("LUMAAI_API_KEY", "")
    minimax_key = cfg.get("minimax_api_key") or os.environ.get("MINIMAX_API_KEY", "")
    kling_key = cfg.get("kling_api_key") or os.environ.get("KLING_API_KEY", "")
    veo_key = cfg.get("google_veo_key") or os.environ.get("GOOGLE_API_KEY", "")

    return {
        "native_3d": {
            "id": "native_3d",
            "name": "3D Motion Graphic Engine (ในเครื่อง)",
            "description": "สินค้าเด้ง หมุน 3D แสงเงาสะท้อน พื้นหลังขยับได้ สไตล์ TikTok ไวรัล (ฟรี 100% เร็ว 5 วินาที)",
            "is_free": True,
            "status": "ready",
            "badge": "ฟรี & แนะนำ",
            "styles": [
                {"id": "tiktok_bounce", "name": "🔥 TikTok ป้ายยาด่วน (เด้งดึ๋ง + สติกเกอร์กระพริบ)"},
                {"id": "retro_tv", "name": "📺 ทีวีช็อปปิ้ง ย้อนยุค (สไตล์ Triple Bot ไวรัล)"},
                {"id": "luxury_glow", "name": "✨ Luxury Glow (หรูหรา แสงเงาวิเศษ สโลว์โมชัน)"},
                {"id": "clean_unboxing", "name": "📦 แกะกล่อง Unboxing (คมชัด สไตล์โมเดิร์น)"},
                {"id": "neon_pop", "name": "⚡ Flash Sale Neon (สีนีออนสด ดึงดูดสายตา)"},
            ]
        },
        "minimax_hailuo": {
            "id": "minimax_hailuo",
            "name": "MiniMax (Hailuo AI video-01)",
            "description": "ตัวท็อปสินค้าขยับได้เนียนมาก สมจริง ไม่บิดเบี้ยว (Image-to-Video)",
            "is_free": False,
            "status": "configured" if bool(minimax_key) else "needs_key",
            "has_key": bool(minimax_key),
            "key_field": "minimax_api_key",
            "signup_url": "https://api.minimax.chat/"
        },
        "luma_ray": {
            "id": "luma_ray",
            "name": "Luma Dream Machine (Ray)",
            "description": "กล้องเคลื่อนที่ 3D มุมกว้าง สไตล์โฆษณาพรีเมียมระดับภาพยนตร์",
            "is_free": False,
            "status": "configured" if bool(luma_key) else "needs_key",
            "has_key": bool(luma_key),
            "key_field": "luma_api_key",
            "signup_url": "https://lumalabs.ai/dream-machine/api"
        },
        "kling_ai": {
            "id": "kling_ai",
            "name": "Kling AI (Image2Video)",
            "description": "โมเดลยอดฮิต ตัวละครและสินค้าขยับได้เป็นธรรมชาติ",
            "is_free": False,
            "status": "configured" if bool(kling_key) else "needs_key",
            "has_key": bool(kling_key),
            "key_field": "kling_api_key",
            "signup_url": "https://klingai.com/"
        },
        "google_veo": {
            "id": "google_veo",
            "name": "Google Flow (Veo / Veo Lite)",
            "description": "โมเดลระดับท็อปของ Google แสงเงา Cinematic วิดีโอสินค้าตรงปกพร้อมใช้ทันที",
            "is_free": True,
            "status": "ready" if bool(os.environ.get("GEMINI_API_KEY")) else "needs_key",
            "has_key": bool(os.environ.get("GEMINI_API_KEY")),
            "key_field": "google_veo_key",
            "badge": "Google Flow Studio",
            "sub_models": [
                {"id": "veo_standard", "name": "Google Veo (เน้นภาพสวย แสงเงาคมชัด 4K)"},
                {"id": "veo_lite", "name": "Google Veo Lite (เน้นเจนเร็ว ทันใจ)"}
            ]
        }
    }


class AIVideoBridge:
    """ตัวเชื่อมต่อและประมวลผล Image-to-Video จากโมเดลภายนอก"""

    @staticmethod
    def generate_with_luma(image_path: str, prompt: str, output_path: str) -> bool:
        cfg = get_ai_models_config()
        api_key = cfg.get("luma_api_key") or os.environ.get("LUMAAI_API_KEY")
        if not api_key:
            raise ValueError("ยังไม่ได้ระบุ LUMAAI_API_KEY ในการตั้งค่า")

        # สำหรับ Luma API เราสามารถใช้ Cloud Image URL หรือ Base64 Data URI
        import base64
        with open(image_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{b64_img}"

        url = "https://api.lumalabs.ai/dream-machine/v1/generations"
        payload = {
            "prompt": f"Commercial product video, {prompt}, vertical 9:16, 4k cinematic motion, high quality advertisement",
            "keyframes": {
                "frame0": {
                    "type": "image",
                    "url": data_uri
                }
            },
            "aspect_ratio": "9:16",
            "loop": False
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            gen_id = resp_data.get("id")

        if not gen_id:
            raise RuntimeError(f"Luma API didn't return generation ID: {resp_data}")

        # Poll status
        check_url = f"https://api.lumalabs.ai/dream-machine/v1/generations/{gen_id}"
        check_req = urllib.request.Request(check_url, headers={"Authorization": f"Bearer {api_key}"})

        for _ in range(30):  # รอสูงสุด 150 วินาที
            time.sleep(5)
            with urllib.request.urlopen(check_req, timeout=15) as poll_resp:
                st = json.loads(poll_resp.read().decode("utf-8"))
                state = st.get("state")
                if state == "completed":
                    video_url = st.get("assets", {}).get("video")
                    if video_url:
                        urllib.request.urlretrieve(video_url, output_path)
                        return True
                elif state == "failed":
                    raise RuntimeError(f"Luma generation failed: {st.get('failure_reason')}")

        raise TimeoutError("Luma generation timed out")

    @staticmethod
    def generate_with_minimax(image_path: str, prompt: str, output_path: str) -> bool:
        cfg = get_ai_models_config()
        api_key = cfg.get("minimax_api_key") or os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("ยังไม่ได้ระบุ MINIMAX_API_KEY ในการตั้งค่า")

        import base64
        with open(image_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{b64_img}"

        url = "https://api.minimax.chat/v1/video_generation"
        payload = {
            "model": "video-01",
            "prompt": f"Commercial product video, {prompt}, product in vivid motion, 9:16 vertical, advertising lighting",
            "first_frame_image": data_uri
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            task_id = resp_data.get("task_id")

        if not task_id:
            raise RuntimeError(f"MiniMax API didn't return task_id: {resp_data}")

        check_url = f"https://api.minimax.chat/v1/query/video_generation?task_id={task_id}"
        check_req = urllib.request.Request(check_url, headers={"Authorization": f"Bearer {api_key}"})

        for _ in range(30):
            time.sleep(5)
            with urllib.request.urlopen(check_req, timeout=15) as poll_resp:
                st = json.loads(poll_resp.read().decode("utf-8"))
                status = st.get("status")
                if status == "Success":
                    file_id = st.get("file_id")
                    # ดาวน์โหลดไฟล์ผลลัพธ์
                    dl_url = f"https://api.minimax.chat/v1/files/retrieve?file_id={file_id}"
                    dl_req = urllib.request.Request(dl_url, headers={"Authorization": f"Bearer {api_key}"})
                    with urllib.request.urlopen(dl_req, timeout=30) as dl_resp:
                        dl_data = json.loads(dl_resp.read().decode("utf-8"))
                        download_url = dl_data.get("file", {}).get("download_url")
                        if download_url:
                            urllib.request.urlretrieve(download_url, output_path)
                            return True
                elif status == "Fail":
                    raise RuntimeError(f"MiniMax generation failed: {st.get('error_message')}")

        raise TimeoutError("MiniMax generation timed out")

    @staticmethod
    def generate_with_google_flow(image_path: str, prompt: str, output_path: str, is_lite: bool = False, duration: int = 5) -> bool:
        """
        สร้างวิดีโอด้วย Google Flow (Veo / Veo Lite) ผ่าน Gemini Omni Video Engine บนเว็บโดยตรง
        """
        import sys
        script_dir = r"C:\Users\non_n\.gemini\config\plugins\gemini-api\skills\gemini-omni-flash-api\scripts\video"
        if script_dir not in sys.path:
            sys.path.append(script_dir)
        import generate_video

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            from src.ai_video_engine import get_ai_models_config
            cfg = get_ai_models_config()
            api_key = cfg.get("google_veo_key")

        if not api_key:
            raise ValueError("ยังไม่ได้ระบุ GEMINI_API_KEY หรือ GOOGLE_VEO_KEY")

        os.environ["GEMINI_API_KEY"] = api_key

        model_name = "gemini-omni-1.1-flash"
        resolution = "360p" if is_lite else "720p"

        generate_video.generate_video_via_interactions(
            prompt=f"<FIRST_FRAME> Commercial 3D product showcase of {prompt}, cinematic studio lighting, smooth camera movement, 9:16 vertical",
            model=model_name,
            first_frame=image_path,
            aspect_ratio="9:16",
            duration=duration,
            resolution=resolution,
            output_path=output_path,
            timeout=300
        )
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
