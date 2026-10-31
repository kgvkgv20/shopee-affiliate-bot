"""
tts_generator.py
----------------
สร้างเสียงพากย์ภาษาไทยสมจริง (Thai Neural TTS) ด้วย Edge TTS (ฟรี 100% ไม่ต้องใช้ API Key)
รองรับเสียงผู้หญิง (Premwadee) และเสียงผู้ชาย (Niwat)
"""
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# รายชื่อเสียงภาษาไทย Neural
VOICE_MAP = {
    "female": "th-TH-PremwadeeNeural",  # เสียงผู้หญิง สดใส ป้ายยาเป็นกันเอง
    "male": "th-TH-NiwatNeural",        # เสียงผู้ชาย อบอุ่น น่าเชื่อถือ
}


async def _async_generate_tts(text: str, output_file: str, voice: str):
    import edge_tts
    # ปรับความเร็วเล็กน้อย +5% เพื่อความกระชับทันใจสำหรับวิดีโอ 10 วินาที
    communicate = edge_tts.Communicate(text, voice, rate="+5%")
    await communicate.save(output_file)


def generate_voiceover(text: str, output_file: str, voice_type: str = "female") -> Optional[str]:
    """
    แปลงข้อความสคริปต์เป็นไฟล์เสียงพากย์ .mp3 ภาษาไทย

    Args:
        text: ข้อความภาษาไทย (ความยาว 1-2 ประโยคสำหรับคลิป 10 วินาที)
        output_file: path ไฟล์ .mp3 ที่ต้องการบันทึก
        voice_type: 'female' หรือ 'male'

    Returns:
        output_file ถ้าสำเร็จ, None ถ้าล้มเหลว
    """
    if not text or not text.strip():
        return None

    voice = VOICE_MAP.get(voice_type, VOICE_MAP["female"])
    try:
        # ตัดคำให้กระชับ ไม่เกิน 120 ตัวอักษร เพื่อให้พูดจบใน 8-9 วินาที
        clean_text = text.strip()[:120]
        # รัน asyncio loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # ถ้าอยู่ใน FastAPI async event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, _async_generate_tts(clean_text, output_file, voice)).result()
            else:
                loop.run_until_complete(_async_generate_tts(clean_text, output_file, voice))
        except RuntimeError:
            asyncio.run(_async_generate_tts(clean_text, output_file, voice))

        if os.path.exists(output_file) and os.path.getsize(output_file) > 500:
            logger.info(f"🎤 สร้างเสียงพากย์ AI สำเร็จ: {output_file} (เสียง: {voice_type})")
            return output_file
    except Exception as e:
        logger.warning(f"⚠️ สร้างเสียงพากย์ TTS ไม่สำเร็จ: {e}")

    return None
