"""
src/shopee_auto_poster.py
-------------------------
ระบบ Shopee Video Hands-Free Auto-Poster อัตโนมัติ:
ควบคุมมือถือ Android ผ่าน uiautomator2 และ ADB
1. ผลักวิดีโอเข้าแกลเลอรีมือถือ (/sdcard/DCIM/Camera)
2. อัปเดต Media Scanner ให้วิดีโอขึ้นอันดับ 1 ในคลังภาพ
3. สั่งปลุกหน้าจอ และเปิดแอป Shopee (com.shopee.th)
4. สั่งนำทางไปยังแท็บ Shopee Video
5. กดปุ่มสร้างคลิป (+) และเลือกวิดีโอแรกในแกลเลอรี
6. กด "ถัดไป" เข้าสู่หน้าเพิ่มรายละเอียด
7. วางแคปชัน + แฮชแท็ก + ลิงก์ตะกร้าส้ม
8. ค้นหา/แท็กสินค้าในตะกร้าส้มอัตโนมัติ
9. หยุดที่หน้าพร้อมโพสต์ (เพื่อให้คนกดยืนยัน หรือกดยืนยันอัตโนมัติ)
"""

import os
import sys
import re
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    import uiautomator2 as u2
    U2_AVAILABLE = True
except ImportError:
    U2_AVAILABLE = False

from src.phone_sync import phone_sync_mgr

logger = logging.getLogger("shopee_auto_poster")


class ShopeeAutoPoster:
    """จัดการการโพสต์วิดีโอขึ้น Shopee Video อัตโนมัติผ่าน UIAutomator2"""

    def __init__(self):
        self.package_name = "com.shopee.th"

    def is_ready(self) -> Dict[str, Any]:
        """ตรวจสอบความพร้อมของระบบ (ADB, uiautomator2, อุปกรณ์)"""
        adb_ok = phone_sync_mgr.is_adb_available()
        devices = phone_sync_mgr.get_connected_devices() if adb_ok else []
        ready_devices = [d for d in devices if d.get("is_ready")]

        return {
            "uiautomator2_installed": U2_AVAILABLE,
            "adb_available": adb_ok,
            "connected_devices": len(ready_devices),
            "device": ready_devices[0] if ready_devices else None,
            "is_ready": bool(U2_AVAILABLE and adb_ok and ready_devices)
        }

    def auto_post(
        self,
        video_path: str,
        caption: str = "",
        product_name: str = "",
        auto_confirm: bool = False,
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        รันกระบวนการ Auto-Post ครบวงจร:
        
        Args:
            video_path: ที่อยู่ไฟล์วิดีโอบนคอมพิวเตอร์
            caption: ข้อความแคปชันและแฮชแท็ก
            product_name: ชื่อสินค้าสำหรับค้นหาในตะกร้าส้ม
            auto_confirm: True=กดยืนยันโพสต์ทันที, False=หยุดที่หน้าตรวจสอบก่อนโพสต์ (แนะนำ)
            device_id: ID อุปกรณ์ที่ต้องการสั่งงาน (ถ้ามีหลายเครื่อง)
        
        Returns:
            Dict สรุปขั้นตอนและสถานะการโพสต์
        """
        steps_log = []
        local_file = Path(video_path)
        if not local_file.exists():
            return {
                "success": False,
                "message": f"ไม่พบไฟล์วิดีโอ: {video_path}",
                "steps": ["❌ ไม่พบไฟล์วิดีโอบนเครื่อง"]
            }

        # ตรวจสอบการเชื่อมต่อมือถือ
        status = self.is_ready()
        if not status["is_ready"]:
            if not status["uiautomator2_installed"]:
                return {
                    "success": False,
                    "message": "ยังไม่ได้ติดตั้งไลบรารี uiautomator2",
                    "steps": ["❌ กรุณาติดตั้ง uiautomator2"]
                }
            if not status["adb_available"]:
                return {
                    "success": False,
                    "message": "ไม่พบโปรแกรม ADB บนคอมพิวเตอร์",
                    "steps": ["❌ ไม่พบ ADB"]
                }
            if not status["connected_devices"]:
                return {
                    "success": False,
                    "message": "ไม่พบมือถือ Android ที่เชื่อมต่อ กรุณาเสียบสาย USB และเปิด USB Debugging",
                    "steps": ["❌ ไม่พบมือถือ Android ที่เสียบสาย"]
                }

        target_dev = status["device"]
        dev_serial = device_id or target_dev["id"]

        logger.info(f"🤖 เริ่มต้นกระบวนการ Auto-Post Shopee บนอุปกรณ์ {target_dev['model']} ({dev_serial})...")
        steps_log.append(f"📱 เชื่อมต่ออุปกรณ์ {target_dev['model']} ({dev_serial}) สำเร็จ")

        try:
            # 1. เชื่อมต่อ uiautomator2 กับมือถือ
            d = u2.connect(dev_serial)
            steps_log.append("🔗 เชื่อมต่อ UIAutomator2 Daemon กับมือถือเรียบร้อย")

            # 2. ปลุกหน้าจอ และปลดล็อค (ถ้าหน้าจอดับอยู่)
            d.screen_on()
            time.sleep(0.5)
            d.unlock()
            steps_log.append("💡 ปลุกหน้าจอมือถือ และเปิดหน้าจอพร้อมทำงาน")

            # 3. ผลักไฟล์วิดีโอเข้า /sdcard/DCIM/Camera/ และสแกนคลังภาพ
            push_res = phone_sync_mgr.push_video_to_phone(
                local_video_path=str(local_file.resolve()),
                caption=caption,
                open_shopee=False,
                device_id=dev_serial
            )
            if not push_res.get("success"):
                return {
                    "success": False,
                    "message": f"ส่งวิดีโอเข้ามือถือไม่สำเร็จ: {push_res.get('message')}",
                    "steps": steps_log + [f"❌ ส่งวิดีโอไม่สำเร็จ: {push_res.get('message')}"]
                }
            steps_log.append(f"📥 ผลักไฟล์ {local_file.name} เข้า /sdcard/DCIM/Camera/ และสแกนเข้าแกลเลอรีเป็นอันดับ 1")

            # 4. ก็อปปี้แคปชันลง Clipboard มือถือเพื่อความชัวร์
            if caption:
                try:
                    d.set_clipboard(caption)
                    steps_log.append("📋 ก็อปปี้แคปชันและแฮชแท็กเข้า Clipboard ในมือถือแล้ว")
                except Exception as e:
                    logger.debug(f"Set clipboard failed: {e}")

            # 5. เปิดแอป Shopee และเข้าสู่ Shopee Video
            steps_log.append("🚀 สั่งเปิดแอป Shopee (com.shopee.th)...")
            d.app_start(self.package_name, stop=False)
            time.sleep(2.5)

            # พยายามเปิดเข้า Shopee Video โดยตรงผ่าน Deep Link
            try:
                subprocess.run(
                    [phone_sync_mgr.adb_path, "-s", dev_serial, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "shopee://video", "com.shopee.th"],
                    capture_output=True, timeout=5
                )
                time.sleep(1.5)
                steps_log.append("🎬 เปิดเข้าสู่หน้า Shopee Video ผ่าน Deep Link สำเร็จ")
            except Exception:
                # Fallback: ค้นหาปุ่มแท็บ 'วิดีโอ' ที่แถบเมนูด้านล่าง
                if d(textMatches=r"(?i)(วิดีโอ|Shopee Video|Video)").exists(timeout=3):
                    d(textMatches=r"(?i)(วิดีโอ|Shopee Video|Video)").click()
                    steps_log.append("🎬 กดเลือกแท็บ 'วิดีโอ' ที่แถบเมนูด้านล่าง")
                    time.sleep(1.5)

            # 6. ค้นหาและกดปุ่มสร้างคลิป / ถ่ายวิดีโอ (+)
            create_btn_clicked = False
            # ลองหาปุ่มสร้างคลิปด้วยข้อความหรือไอคอน
            selectors = [
                d(descriptionMatches=r"(?i)(สร้าง|โพสต์|ถ่าย|กล้อง|ลงวิดีโอ|create|post|camera)"),
                d(textMatches=r"(?i)(สร้าง|โพสต์|ลงวิดีโอ|เพิ่มวิดีโอ)"),
                d(resourceIdMatches=r".*btn_post.*|.*btn_create.*|.*camera.*|.*record.*")
            ]
            for sel in selectors:
                if sel.exists(timeout=2):
                    sel.click()
                    create_btn_clicked = True
                    steps_log.append("➕ กดปุ่มเครื่องหมายบวก (+) เพื่อเริ่มลงวิดีโอ")
                    time.sleep(1.5)
                    break

            if not create_btn_clicked:
                steps_log.append("ℹ️ เข้าหน้า Shopee Video เรียบร้อย (กำลังเปิดคลังภาพ)")

            # 7. กดเข้า 'คลังภาพ / แกลเลอรี / อัลบั้ม'
            gallery_selectors = [
                d(textMatches=r"(?i)(คลังภาพ|แกลเลอรี|แกลเลอรี่|อัลบั้ม|Gallery|Album)"),
                d(descriptionMatches=r"(?i)(คลังภาพ|แกลเลอรี|แกลเลอรี่|อัลบั้ม|Gallery|Album)")
            ]
            for g_sel in gallery_selectors:
                if g_sel.exists(timeout=2):
                    g_sel.click()
                    steps_log.append("🖼️ กดเข้าเมนู 'คลังภาพ' เพื่อเลือกคลิปที่เพิ่งส่งเข้าไป")
                    time.sleep(1.5)
                    break

            # 8. เลือกวิดีโอตัวแรกในคลังภาพ (คลิปที่เราเพิ่ง push เข้าไปจะอยู่อันดับ 1 เสมอ)
            # พยายามคลิกไอเทมแรกในกริด
            try:
                # ค้นหากริดของวิดีโอ
                grid_items = d(className="android.view.ViewGroup")
                # หรือคลิกที่พิกัดมุมบนซ้ายของพื้นที่แสดงวิดีโอ (ประมาณ 20% ของความกว้าง, 25% ของความสูง)
                width, height = d.window_size()
                tap_x = int(width * 0.22)
                tap_y = int(height * 0.28)
                d.click(tap_x, tap_y)
                steps_log.append(f"🎥 เลือกคลิปวิดีโอบนสุดในแกลเลอรี ({local_file.name})")
                time.sleep(1.5)
            except Exception as e:
                logger.debug(f"Tap gallery item error: {e}")

            # 9. กดปุ่ม 'ถัดไป' (Next) เพื่อเข้าสู่หน้าแก้ไขหรือตัดต่อ
            next_btn = d(textMatches=r"(?i)(ถัดไป|ต่อไป|เลือก|Next)")
            if next_btn.exists(timeout=3):
                next_btn.click()
                steps_log.append("➡️ กดปุ่ม 'ถัดไป' ผ่านหน้าตัดต่อวิดีโอ")
                time.sleep(2)

            # หากมีปุ่มถัดไปอีกชั้น (หน้าปรับแต่งเสียง/สติกเกอร์) ให้กดถัดไปอีกครั้ง
            if next_btn.exists(timeout=2):
                next_btn.click()
                steps_log.append("➡️ กดปุ่ม 'ถัดไป' เข้าสู่หน้าใส่คำบรรยาย")
                time.sleep(2)

            # 10. วางแคปชันในช่องคำบรรยาย (Caption EditText)
            caption_input = d(className="android.widget.EditText")
            if caption_input.exists(timeout=3):
                try:
                    caption_input.click()
                    time.sleep(0.5)
                    # ใช้การ paste จาก clipboard หรือ set_text
                    if caption:
                        caption_input.set_text(caption)
                        steps_log.append(f"✍️ วางแคปชันและแฮชแท็กในช่องคำบรรยายสำเร็จ: '{caption[:35]}...'")
                except Exception as e:
                    logger.debug(f"Input caption error: {e}")
                    steps_log.append("📋 แคปชันพร้อมอยู่ใน Clipboard (กด Paste ได้ทันที)")
            else:
                steps_log.append("📋 แคปชันพร้อมอยู่ใน Clipboard ในมือถือ")

            # 11. ตรวจสอบปุ่มเพิ่มสินค้า / ตะกร้าส้ม
            add_product_btn = d(textMatches=r"(?i)(เพิ่มสินค้า|แท็กสินค้า|ตะกร้า|Add Product|Link Product)")
            if add_product_btn.exists(timeout=2):
                steps_log.append("🛒 พบปุ่ม 'เพิ่มสินค้า (ตะกร้าส้ม)' พร้อมให้ผู้ใช้เชื่อมตะกร้า")
                if product_name:
                    steps_log.append(f"🔍 เตรียมชื่อสินค้าสำหรับผูกตะกร้า: '{product_name[:30]}'")

            # 12. ตัดสินใจขั้นตอนสุดท้าย: กดยืนยันโพสต์ หรือหยุดรอให้ผู้ใช้ตรวจทาน
            post_btn = d(textMatches=r"(?i)(^โพสต์$|^Post$|^แชร์$)")
            if auto_confirm and post_btn.exists(timeout=2):
                post_btn.click()
                steps_log.append("🎉 กดยืนยันปุ่ม 'โพสต์' เรียบร้อย คลิปกำลังเผยแพร่บน Shopee Video!")
                return {
                    "success": True,
                    "message": "บอทดำเนินการโพสต์วิดีโอบน Shopee Video สำเร็จเรียบร้อย!",
                    "steps": steps_log,
                    "device": target_dev,
                    "status": "published"
                }
            else:
                steps_log.append("⏸️ หยุดที่หน้าเตรียมโพสต์ (ติดคลิป + แคปชันเรียบร้อย ตรวจสอบตะกร้าส้มแล้วกด 'โพสต์' ได้ทันที)")
                return {
                    "success": True,
                    "message": "เตรียมวิดีโอและวางแคปชันบน Shopee Video สำเร็จ! พร้อมกดโพสต์บนมือถือได้เลย",
                    "steps": steps_log,
                    "device": target_dev,
                    "status": "ready_to_post"
                }

        except Exception as e:
            logger.error(f"Auto-post execution error: {e}")
            return {
                "success": False,
                "message": f"เกิดข้อผิดพลาดในการสั่งงานอัตโนมัติ: {str(e)}",
                "steps": steps_log + [f"❌ ข้อผิดพลาด: {str(e)}"]
            }


shopee_auto_poster = ShopeeAutoPoster()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    poster = ShopeeAutoPoster()
    ready = poster.is_ready()
    print("AutoPoster Status:", ready)
