"""
routine_manager.py
------------------
จัดการระบบการทำงานแบบ Routine อัตโนมัติ:
1. หมุนเวียนหมวดหมู่สินค้าอัตโนมัติ (Beauty -> Home -> Electronics -> Fashion)
2. บันทึกประวัติสินค้าที่เคยทำแล้ว ป้องกันการสร้างคลิปซ้ำซ้อน
3. รายงานสรุปสถานะการผลิตคลิปแบบต่อเนื่อง
"""
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_FILE = "output/routine_history.json"
DEFAULT_CATEGORIES = ["beauty", "home", "electronics", "fashion"]


class RoutineManager:
    """
    ควบคุมรอบการรันและป้องกันการทำสินค้าซ้ำ
    """

    def __init__(self, history_file: str = HISTORY_FILE):
        self.history_file = Path(history_file)
        self.categories = DEFAULT_CATEGORIES
        self.data = self._load_data()

    def _load_data(self) -> dict:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"⚠️ โหลด history ไม่สำเร็จ ({e}) — สร้างข้อมูลเริ่มต้นใหม่")

        return {
            "category_index": 0,
            "total_runs": 0,
            "total_videos_created": 0,
            "last_run_time": None,
            "created_products": [],
        }

    def _save_data(self):
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ ไม่สามารถบันทึก history ได้: {e}")

    def get_next_category(self) -> str:
        """
        ดึงหมวดหมู่ถัดไปตามรอบการหมุนเวียน (Beauty -> Home -> Electronics -> Fashion)
        """
        idx = self.data.get("category_index", 0) % len(self.categories)
        return self.categories[idx]

    def advance_category(self):
        """
        ขยับรอบหมวดหมู่ไปยังหมวดถัดไปสำหรับการรันครั้งต่อไป
        """
        idx = (self.data.get("category_index", 0) + 1) % len(self.categories)
        self.data["category_index"] = idx
        self._save_data()

    def get_excluded_names(self, days: int = 14) -> list[str]:
        """
        ดึงรายชื่อสินค้าที่เคยผลิตคลิปไปแล้วในช่วง N วันที่ผ่านมา เพื่อไม่ให้ทำซ้ำ
        """
        cutoff = datetime.now() - timedelta(days=days)
        excluded = []
        for item in self.data.get("created_products", []):
            try:
                item_date = datetime.fromisoformat(item["timestamp"])
                if item_date > cutoff:
                    excluded.append(item.get("name", ""))
            except Exception:
                excluded.append(item.get("name", ""))
        return [name for name in excluded if name]

    def record_video(self, product_name: str, category: str, video_path: str):
        """
        บันทึกสินค้าที่ทำคลิปสำเร็จลงในประวัติ
        """
        record = {
            "name": product_name,
            "category": category,
            "video_path": video_path,
            "timestamp": datetime.now().isoformat(),
        }
        self.data.setdefault("created_products", []).append(record)
        self.data["total_videos_created"] = self.data.get("total_videos_created", 0) + 1
        self._save_data()

    def record_run_completion(self):
        """
        บันทึกว่าการรันรอบนี้เสร็จสิ้นเรียบร้อย
        """
        self.data["total_runs"] = self.data.get("total_runs", 0) + 1
        self.data["last_run_time"] = datetime.now().isoformat()
        self._save_data()

    def get_summary(self) -> str:
        """
        สรุปภาพรวมของ Routine
        """
        total_runs = self.data.get("total_runs", 0)
        total_vids = self.data.get("total_videos_created", 0)
        last_run = self.data.get("last_run_time", "ยังไม่เคยรัน")
        next_cat = self.get_next_category()
        return (
            f"📊 สถิติ Routine:\n"
            f"   - รันแล้วทั้งหมด: {total_runs} รอบ\n"
            f"   - ผลิตวิดีโอแล้ว: {total_vids} คลิป\n"
            f"   - ล่าสุดเมื่อ: {last_run}\n"
            f"   - หมวดหมู่รอบถัดไป: {next_cat.upper()}"
        )
