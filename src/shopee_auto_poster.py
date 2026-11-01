"""
src/shopee_auto_poster.py
-------------------------
ระบบ Social Video Hands-Free Auto-Poster อัจฉริยะ (Shopee Video + TikTok Shop):
ควบคุมมือถือ Android ผ่าน UIAutomator2 และ ADB พร้อมฟังก์ชันความปลอดภัยระดับสูง:
1. Anti-Ban Humanizer:
   - จำลองพฤติกรรมมนุษย์ (Human Jitter)
   - สุ่มตำแหน่งแตะหน้าจอ (Random Coordinate Offset ±3-7 px)
   - สุ่มเวลาหน่วง (Randomized Realistic Delay 1.5 - 3.2s)
   - จำลองระยะเวลานิ้วแตะจอ (Touch Duration 60-140ms)
2. Dual Platform Support:
   - 🛒 Shopee Video (com.shopee.th)
   - 🎵 TikTok Shop (com.zhiliaoapp.musically)
3. Smart Media Handling:
   - ผลักวิดีโอเข้า /sdcard/DCIM/Camera
   - กระตุ้น Media Scanner ให้อยู่อันดับ 1 ในแกลเลอรี
   - ก็อปปี้แคปชัน + แฮชแท็ก + ลิงก์ตะกร้าส้มเข้า Clipboard
"""

import os
import sys
import re
import time
import random
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

logger = logging.getLogger("social_auto_poster")


class SocialAutoPoster:
    """จัดการการโพสต์วิดีโอขึ้น Shopee Video และ TikTok อัตโนมัติ พร้อมระบบจำลองพฤติกรรมมนุษย์"""

    def __init__(self):
        self.shopee_pkg = "com.shopee.th"
        self.tiktok_pkgs = ["com.zhiliaoapp.musically", "com.ss.android.ugc.trill", "com.zhiliaoapp.musically.go"]
        self.last_post_time = 0

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

    # =========================================================================
    # 🛡️ Anti-Ban Humanizer: จำลองพฤติกรรมนิ้วมือมนุษย์
    # =========================================================================

    def _human_delay(self, min_s: float = 1.4, max_s: float = 2.8):
        """หน่วงเวลาแบบสุ่มเลียนแบบสายตามนุษย์กำลังอ่านหน้าจอ"""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)

    def _human_tap(self, d, x: int, y: int, max_offset: int = 5):
        """แตะหน้าจอโดยสุ่มตำแหน่งเบี่ยงเบน ±px เล็กน้อย และจำลองระยะเวลากดนิ้ว"""
        offset_x = random.randint(-max_offset, max_offset)
        offset_y = random.randint(-max_offset, max_offset)
        final_x = max(1, x + offset_x)
        final_y = max(1, y + offset_y)

        # แตะแบบนิ้วคนจริง (Touch Down -> รอ 70-130ms -> Touch Up)
        try:
            d.touch.down(final_x, final_y)
            time.sleep(random.uniform(0.065, 0.135))
            d.touch.up(final_x, final_y)
        except Exception:
            d.click(final_x, final_y)

    def _human_click_elem(self, d, elem, timeout: float = 3.0, desc: str = "") -> bool:
        """คลิกที่องค์ประกอบ UI ด้วยตำแหน่งสุ่มเลียนแบบมนุษย์"""
        try:
            if elem.exists(timeout=timeout):
                bounds = elem.info.get("bounds", {})
                if bounds:
                    center_x = (bounds.get("left", 0) + bounds.get("right", 0)) // 2
                    center_y = (bounds.get("top", 0) + bounds.get("bottom", 0)) // 2
                    self._human_tap(d, center_x, center_y, max_offset=4)
                else:
                    elem.click()
                if desc:
                    logger.debug(f"Human clicked: {desc}")
                return True
        except Exception as e:
            logger.debug(f"Human click error for {desc}: {e}")
        return False

    # =========================================================================
    # 🛒 Shopee Video Auto-Post Routine
    # =========================================================================

    def _post_to_shopee(
        self,
        d,
        dev_serial: str,
        local_file: Path,
        caption: str,
        product_name: str,
        auto_confirm: bool,
        steps_log: List[str]
    ) -> Dict[str, Any]:
        """รันคำสั่งบอทโพสต์เข้า Shopee Video"""
        steps_log.append("🚀 สั่งเปิดแอป Shopee (com.shopee.th)...")
        d.app_start(self.shopee_pkg, stop=False)
        self._human_delay(2.2, 3.2)

        # พยายามเปิดเข้า Shopee Video โดยตรงผ่าน Deep Link
        try:
            subprocess.run(
                [phone_sync_mgr.adb_path, "-s", dev_serial, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "shopee://video", "com.shopee.th"],
                capture_output=True, timeout=5
            )
            self._human_delay(1.5, 2.5)
            steps_log.append("🎬 เปิดเข้าสู่หน้า Shopee Video สำเร็จ")
        except Exception:
            # Fallback: ค้นหาปุ่มแท็บ 'วิดีโอ' ที่แถบเมนูด้านล่าง
            vid_tab = d(textMatches=r"(?i)(วิดีโอ|Shopee Video|Video)")
            if self._human_click_elem(d, vid_tab, timeout=3, desc="Shopee Video Tab"):
                steps_log.append("🎬 กดเลือกแท็บ 'วิดีโอ' ที่แถบเมนูด้านล่าง")
                self._human_delay(1.5, 2.2)

        # ค้นหาและกดปุ่มสร้างคลิป (+)
        create_btn_clicked = False
        selectors = [
            d(descriptionMatches=r"(?i)(สร้าง|โพสต์|ถ่าย|กล้อง|ลงวิดีโอ|create|post|camera)"),
            d(textMatches=r"(?i)(สร้าง|โพสต์|ลงวิดีโอ|เพิ่มวิดีโอ)"),
            d(resourceIdMatches=r".*btn_post.*|.*btn_create.*|.*camera.*|.*record.*")
        ]
        for sel in selectors:
            if self._human_click_elem(d, sel, timeout=2, desc="Create Video Button"):
                create_btn_clicked = True
                steps_log.append("➕ กดปุ่มเครื่องหมายบวก (+) เพื่อเริ่มลงวิดีโอ (Anti-Ban Human Click)")
                self._human_delay(1.5, 2.4)
                break

        if not create_btn_clicked:
            steps_log.append("ℹ️ อยู่ในหน้า Shopee Video เรียบร้อย (กำลังเปิดคลังภาพ)")

        # กดเข้า 'คลังภาพ / แกลเลอรี'
        gallery_selectors = [
            d(textMatches=r"(?i)(คลังภาพ|แกลเลอรี|แกลเลอรี่|อัลบั้ม|Gallery|Album)"),
            d(descriptionMatches=r"(?i)(คลังภาพ|แกลเลอรี|แกลเลอรี่|อัลบั้ม|Gallery|Album)")
        ]
        for g_sel in gallery_selectors:
            if self._human_click_elem(d, g_sel, timeout=2, desc="Gallery Button"):
                steps_log.append("🖼️ กดเข้าเมนู 'คลังภาพ' เพื่อเลือกคลิป")
                self._human_delay(1.4, 2.2)
                break

        # เลือกวิดีโอตัวแรกในคลังภาพ (คลิปที่เพิ่งส่งเข้าไปจะอยู่อันดับ 1)
        width, height = d.window_size()
        tap_x = int(width * 0.22)
        tap_y = int(height * 0.28)
        self._human_tap(d, tap_x, tap_y, max_offset=5)
        steps_log.append(f"🎥 เลือกคลิปวิดีโอบนสุดในแกลเลอรี ({local_file.name})")
        self._human_delay(1.6, 2.4)

        # กดปุ่ม 'ถัดไป' (Next)
        next_btn = d(textMatches=r"(?i)(ถัดไป|ต่อไป|เลือก|Next)")
        if self._human_click_elem(d, next_btn, timeout=3, desc="Next Button"):
            steps_log.append("➡️ กดปุ่ม 'ถัดไป' ผ่านหน้าตัดต่อวิดีโอ")
            self._human_delay(2.0, 3.0)

        # หากมีปุ่มถัดไปอีกชั้น (หน้าเอฟเฟกต์/เสียง)
        if self._human_click_elem(d, next_btn, timeout=2, desc="Next Button 2"):
            steps_log.append("➡️ กดปุ่ม 'ถัดไป' เข้าสู่หน้าใส่คำบรรยาย")
            self._human_delay(1.8, 2.5)

        # วางแคปชันในช่องคำบรรยาย
        caption_input = d(className="android.widget.EditText")
        if caption_input.exists(timeout=3):
            try:
                self._human_click_elem(d, caption_input, timeout=1.5, desc="Caption Box")
                self._human_delay(0.5, 1.0)
                if caption:
                    caption_input.set_text(caption)
                    steps_log.append(f"✍️ วางแคปชันและแฮชแท็ก: '{caption[:35]}...'")
            except Exception:
                steps_log.append("📋 แคปชันพร้อมอยู่ใน Clipboard (กด Paste ได้ทันที)")
        else:
            steps_log.append("📋 แคปชันพร้อมอยู่ใน Clipboard ในมือถือ")

        # ตรวจสอบปุ่มเพิ่มสินค้า / ตะกร้าส้ม
        add_product_btn = d(textMatches=r"(?i)(เพิ่มสินค้า|แท็กสินค้า|ตะกร้า|Add Product|Link Product)")
        if add_product_btn.exists(timeout=2):
            steps_log.append("🛒 พบปุ่ม 'เพิ่มสินค้า (ตะกร้าส้ม)' พร้อมเชื่อมตะกร้า")
            if product_name:
                steps_log.append(f"🔍 เตรียมชื่อสินค้าสำหรับผูกตะกร้า: '{product_name[:30]}'")

        # กดยืนยันโพสต์ หรือหยุดรอให้ผู้ใช้ตรวจทาน
        post_btn = d(textMatches=r"(?i)(^โพสต์$|^Post$|^แชร์$)")
        if auto_confirm and post_btn.exists(timeout=2):
            self._human_delay(1.0, 2.0)
            self._human_click_elem(d, post_btn, timeout=2, desc="Confirm Post Button")
            steps_log.append("🎉 กดยืนยันปุ่ม 'โพสต์' เรียบร้อย คลิปกำลังเผยแพร่บน Shopee Video!")
            return {
                "success": True,
                "platform": "shopee",
                "message": "บอทดำเนินการโพสต์วิดีโอบน Shopee Video สำเร็จเรียบร้อย!",
                "steps": steps_log,
                "status": "published"
            }
        else:
            steps_log.append("⏸️ หยุดที่หน้าเตรียมโพสต์ (คลิป + แคปชันเรียบร้อย ตรวจสอบตะกร้าส้มแล้วกด 'โพสต์' ได้เลย)")
            return {
                "success": True,
                "platform": "shopee",
                "message": "เตรียมวิดีโอและวางแคปชันบน Shopee Video สำเร็จ! พร้อมกดโพสต์บนมือถือได้เลย",
                "steps": steps_log,
                "status": "ready_to_post"
            }

    # =========================================================================
    # 🎵 TikTok Shop Auto-Post Routine
    # =========================================================================

    def _post_to_tiktok(
        self,
        d,
        dev_serial: str,
        local_file: Path,
        caption: str,
        product_name: str,
        auto_confirm: bool,
        steps_log: List[str]
    ) -> Dict[str, Any]:
        """รันคำสั่งบอทโพสต์เข้า TikTok"""
        # ค้นหาแพ็กเกจ TikTok ที่ติดตั้งอยู่
        active_tiktok_pkg = self.tiktok_pkgs[0]
        steps_log.append("🚀 สั่งเปิดแอป TikTok (com.zhiliaoapp.musically)...")
        d.app_start(active_tiktok_pkg, stop=False)
        self._human_delay(2.5, 3.5)

        # กดปุ่มสร้างคลิป (+) ตรงกลางแถบด้านล่าง
        create_selectors = [
            d(descriptionMatches=r"(?i)(สร้าง|โพสต์|ถ่าย|กล้อง|create|record|camera|\+)"),
            d(resourceIdMatches=r".*btn_post.*|.*btn_create.*|.*tab_publish.*|.*camera.*"),
            d(textMatches=r"(?i)(สร้าง|\+)")
        ]
        create_clicked = False
        for c_sel in create_selectors:
            if self._human_click_elem(d, c_sel, timeout=2.5, desc="TikTok Create (+) Button"):
                create_clicked = True
                steps_log.append("➕ กดปุ่มเครื่องหมายบวก (+) ตรงกลางเพื่อเริ่มสร้างคลิปบน TikTok")
                self._human_delay(1.8, 2.6)
                break

        if not create_clicked:
            # Fallback: แตะตรงกลางล่างของหน้าจอ
            width, height = d.window_size()
            self._human_tap(d, int(width * 0.5), int(height * 0.94), max_offset=4)
            steps_log.append("➕ แตะปุ่มสร้างคลิปที่กึ่งกลางล่างของหน้าจอ")
            self._human_delay(1.8, 2.5)

        # กดปุ่ม "อัปโหลด" / "Upload" เพื่อเปิดคลังภาพ
        upload_selectors = [
            d(textMatches=r"(?i)(อัปโหลด|อัพโหลด|Upload|คลังภาพ|แกลเลอรี)"),
            d(descriptionMatches=r"(?i)(อัปโหลด|Upload)")
        ]
        for u_sel in upload_selectors:
            if self._human_click_elem(d, u_sel, timeout=2.5, desc="TikTok Upload Button"):
                steps_log.append("🖼️ กดปุ่ม 'อัปโหลด' เพื่อเข้าคลังภาพมือถือ")
                self._human_delay(1.5, 2.2)
                break

        # เลือกวิดีโอแรกในแกลเลอรี (คลิปที่เพิ่งส่งเข้าไป)
        width, height = d.window_size()
        tap_x = int(width * 0.22)
        tap_y = int(height * 0.26)
        self._human_tap(d, tap_x, tap_y, max_offset=4)
        steps_log.append(f"🎥 เลือกคลิปวิดีโอบนสุดในแกลเลอรี ({local_file.name})")
        self._human_delay(1.5, 2.2)

        # กดปุ่ม 'ถัดไป' (Next)
        next_btn = d(textMatches=r"(?i)(ถัดไป|ต่อไป|Next)")
        if self._human_click_elem(d, next_btn, timeout=3, desc="TikTok Next Button"):
            steps_log.append("➡️ กดปุ่ม 'ถัดไป' ผ่านหน้าตัดต่อวิดีโอ")
            self._human_delay(2.2, 3.2)

        # หากมีหน้าปรับเสียง/ฟิลเตอร์ ให้กดถัดไปอีกครั้ง
        if self._human_click_elem(d, next_btn, timeout=2, desc="TikTok Next Button 2"):
            steps_log.append("➡️ กดปุ่ม 'ถัดไป' เข้าสู่หน้าโพสต์รายละเอียด")
            self._human_delay(2.0, 2.8)

        # วางแคปชันในช่องคำบรรยายของ TikTok
        caption_box = d(className="android.widget.EditText")
        if caption_box.exists(timeout=3):
            try:
                self._human_click_elem(d, caption_box, timeout=1.5, desc="TikTok Caption Box")
                self._human_delay(0.5, 1.0)
                if caption:
                    caption_box.set_text(caption)
                    steps_log.append(f"✍️ วางแคปชัน TikTok สำเร็จ: '{caption[:35]}...'")
            except Exception:
                steps_log.append("📋 แคปชันพร้อมอยู่ใน Clipboard (กด Paste ได้ทันที)")
        else:
            steps_log.append("📋 แคปชันพร้อมอยู่ใน Clipboard ในมือถือ")

        # ตรวจสอบปุ่ม "เพิ่มลิงก์ / สินค้า (TikTok Shop Showcase)"
        add_link_btn = d(textMatches=r"(?i)(เพิ่มลิงก์|สินค้า|Add Link|Product)")
        if add_link_btn.exists(timeout=2):
            steps_log.append("🛒 พบปุ่ม 'เพิ่มสินค้า (TikTok Shop)' พร้อมให้ผูกตะกร้า")
            if product_name:
                steps_log.append(f"🔍 สินค้าเป้าหมาย: '{product_name[:30]}'")

        # กดยืนยันโพสต์ หรือหยุดรอให้ผู้ใช้ตรวจทาน
        post_btn = d(textMatches=r"(?i)(^โพสต์$|^Post$)")
        if auto_confirm and post_btn.exists(timeout=2):
            self._human_delay(1.0, 2.0)
            self._human_click_elem(d, post_btn, timeout=2, desc="TikTok Confirm Post Button")
            steps_log.append("🎉 กดยืนยันปุ่ม 'โพสต์' บน TikTok เรียบร้อย คลิปกำลังเผยแพร่!")
            return {
                "success": True,
                "platform": "tiktok",
                "message": "บอทดำเนินการโพสต์วิดีโอบน TikTok สำเร็จเรียบร้อย!",
                "steps": steps_log,
                "status": "published"
            }
        else:
            steps_log.append("⏸️ หยุดที่หน้าเตรียมโพสต์ TikTok (คลิป + แคปชันพร้อมแล้ว ตรวจสอบตะกร้าแล้วกด 'โพสต์' ได้เลย)")
            return {
                "success": True,
                "platform": "tiktok",
                "message": "เตรียมวิดีโอและวางแคปชันบน TikTok สำเร็จ! พร้อมกดโพสต์บนมือถือได้เลย",
                "steps": steps_log,
                "status": "ready_to_post"
            }

    # =========================================================================
    # 🌟 Main Entry Point: รองรับทั้ง Shopee และ TikTok
    # =========================================================================

    def auto_post(
        self,
        video_path: str,
        caption: str = "",
        product_name: str = "",
        platform: str = "shopee",
        auto_confirm: bool = False,
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        รันกระบวนการ Auto-Post ครบวงจร:
        
        Args:
            video_path: ที่อยู่ไฟล์วิดีโอบนคอมพิวเตอร์
            caption: ข้อความแคปชันและแฮชแท็ก
            product_name: ชื่อสินค้าสำหรับค้นหาในตะกร้า
            platform: 'shopee' (Shopee Video) หรือ 'tiktok' (TikTok Shop)
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

        # ตรวจสอบความปลอดภัยเรื่องระยะห่างการโพสต์ (Anti-Spam Velocity)
        now = time.time()
        if self.last_post_time > 0:
            elapsed_min = (now - self.last_post_time) / 60
            if elapsed_min < 3.0:
                steps_log.append(f"⚠️ คำแนะนำความปลอดภัย: โพสต์ล่าสุดเมื่อ {elapsed_min:.1f} นาทีที่แล้ว (เพื่อความปลอดภัยบัญชี แนะนำให้เว้น 15–30 นาทีต่อคลิป)")

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
                    "message": "ไม่พบมือถือ Android ที่เชื่อมต่อ กรุณาเสียบสาย USB หรือเชื่อมต่อผ่าน Wi-Fi ADB",
                    "steps": ["❌ ไม่พบมือถือ Android ที่เชื่อมต่อ (ทั้งสาย USB และ Wi-Fi)"]
                }

        target_dev = status["device"]
        dev_serial = device_id or target_dev["id"]

        conn_type = "ไร้สาย Wi-Fi" if target_dev.get("is_wireless") else "สาย USB"
        steps_log.append(f"📱 เชื่อมต่ออุปกรณ์ {target_dev['model']} ({conn_type}) สำเร็จ")

        try:
            # 1. เชื่อมต่อ uiautomator2 กับมือถือ
            d = u2.connect(dev_serial)
            steps_log.append("🔗 เชื่อมต่อ UIAutomator2 Daemon กับมือถือเรียบร้อย")

            # 2. ปลุกหน้าจอ และปลดล็อค (Human-like)
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

            # 4. ก็อปปี้แคปชันลง Clipboard มือถือ
            if caption:
                try:
                    d.set_clipboard(caption)
                    steps_log.append("📋 ก็อปปี้แคปชันและแฮชแท็กเข้า Clipboard ในมือถือแล้ว")
                except Exception as e:
                    logger.debug(f"Set clipboard failed: {e}")

            # 5. สลับตามแพลตฟอร์มเป้าหมาย (Shopee Video หรือ TikTok)
            selected_platform = platform.lower().strip()
            if selected_platform == "tiktok":
                steps_log.append("🎯 เลือกแพลตฟอร์ม: TikTok Shop (วิดีโอสั้นแนวตั้ง)")
                result = self._post_to_tiktok(
                    d=d,
                    dev_serial=dev_serial,
                    local_file=local_file,
                    caption=caption,
                    product_name=product_name,
                    auto_confirm=auto_confirm,
                    steps_log=steps_log
                )
            else:
                steps_log.append("🎯 เลือกแพลตฟอร์ม: Shopee Video (ตะกร้าส้ม)")
                result = self._post_to_shopee(
                    d=d,
                    dev_serial=dev_serial,
                    local_file=local_file,
                    caption=caption,
                    product_name=product_name,
                    auto_confirm=auto_confirm,
                    steps_log=steps_log
                )

            self.last_post_time = time.time()
            result["device"] = target_dev
            return result

        except Exception as e:
            logger.error(f"Auto-post execution error: {e}")
            return {
                "success": False,
                "message": f"เกิดข้อผิดพลาดในการสั่งงานอัตโนมัติ: {str(e)}",
                "steps": steps_log + [f"❌ ข้อผิดพลาด: {str(e)}"]
            }


# กำหนด Object หลัก และ Alias เพื่อความเข้ากันได้ย้อนหลัง
social_auto_poster = SocialAutoPoster()
shopee_auto_poster = social_auto_poster
ShopeeAutoPoster = SocialAutoPoster


if __name__ == "__main__":
    poster = SocialAutoPoster()
    ready = poster.is_ready()
    print("SocialAutoPoster Status:", ready)
