"""
scheduler_service.py
--------------------
ระบบจัดการตารางเวลาสร้างคลิปอัตโนมัติ (Automated Daily Scheduler):
1. ตั้งเวลาสร้างคลิปประจำวัน เช่น 10:00 น. และ 18:00 น.
2. สุ่มดึงสินค้าจาก "สินค้าของฉัน" และคลังสินค้า 25%+ อัตโนมัติ 3-5 คลิปต่อรอบ
3. ป้องกันการหยิบสินค้าซ้ำที่เคยทำไปแล้วในรอบ 14 วัน
4. สร้างสคริปต์ AI + พากย์เสียง AI + ตัดต่อวิดีโอ
5. ส่งวิดีโอพร้อมแคปชันเข้า Telegram และ Discord โดยอัตโนมัติ
"""
import os
import json
import time
import asyncio
import logging
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "data" / "scheduler_config.json"
HISTORY_PATH = PROJECT_ROOT / "data" / "scheduler_history.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "times": ["10:00", "18:00"],
    "count_per_run": 3,
    "source": "both",  # 'my_products', 'catalog', 'both'
    "template": "clean",
    "enable_voice": True,
    "voice_type": "female",
    "bgm_track": "cheerful",
    "notify_telegram": True,
    "notify_discord": True,
    "last_run_timestamp": None,
    "last_run_time_str": None,
    "total_automated_runs": 0,
    "total_videos_created": 0,
}


def get_local_ip() -> str:
    """ดึง Local LAN IP ของเครื่องคอมพิวเตอร์ เพื่อให้มือถือในวง Wi-Fi สแกน QR Code ดาวน์โหลดคลิปได้"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def load_scheduler_config() -> Dict:
    """โหลดการตั้งค่า Scheduler จากไฟล์"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config = {**DEFAULT_CONFIG, **saved}
                return config
        except Exception as e:
            logger.warning(f"Error loading scheduler config: {e}")
    return DEFAULT_CONFIG.copy()


def save_scheduler_config(new_config: Dict) -> Dict:
    """บันทึกการตั้งค่า Scheduler"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = load_scheduler_config()
    current.update(new_config)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current


def record_scheduler_run(run_result: Dict):
    """บันทึกประวัติการรันอัตโนมัติ"""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if HISTORY_PATH.exists():
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    history.insert(0, run_result)
    # เก็บประวัติไม่เกิน 50 ครั้ง
    history = history[:50]

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


class AutoSchedulerWorker:
    """Background Worker คอยตรวจสอบเวลาและรันการผลิตคลิปอัตโนมัติ"""

    def __init__(self, runner_callback=None):
        self.runner_callback = runner_callback
        self.is_running = False
        self.last_checked_minute = None

    async def start(self):
        """เริ่ม Background Loop"""
        self.is_running = True
        logger.info("⏰ Automated Scheduler background worker started")
        while self.is_running:
            try:
                await self._check_and_trigger()
            except Exception as e:
                logger.error(f"Error in scheduler worker: {e}")
            await asyncio.sleep(20)  # เช็คทุก 20 วินาที

    def stop(self):
        self.is_running = False
        logger.info("⏰ Automated Scheduler background worker stopped")

    async def _check_and_trigger(self):
        config = load_scheduler_config()
        if not config.get("enabled"):
            return

        now = datetime.now()
        current_minute_str = now.strftime("%Y-%m-%d %H:%M")
        current_time_hm = now.strftime("%H:%M")

        if self.last_checked_minute == current_minute_str:
            return  # รอบนาทีนี้ตรวจแล้ว

        scheduled_times = config.get("times", [])
        if current_time_hm in scheduled_times:
            self.last_checked_minute = current_minute_str
            logger.info(f"🎯 ถึงเวลา Scheduled Run ({current_time_hm})! กำลังเริ่มทำงานอัตโนมัติ...")
            if self.runner_callback:
                # รันงานใน async task
                asyncio.create_task(self.runner_callback(is_manual=False))
