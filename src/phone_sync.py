"""
phone_sync.py
-------------
ระบบเชื่อมต่อมือถือ Android กับคอมพิวเตอร์ผ่าน ADB (Android Debug Bridge)
สำหรับการทำ Shopee Affiliate แบบ Hands-free:
1. ตรวจสอบการเชื่อมต่อมือถือ Android (สาย USB หรือ Wi-Fi ADB)
2. ผลักไฟล์วิดีโอ .mp4 เข้าคลังภาพของมือถือ (/sdcard/DCIM/Camera/) อัตโนมัติ
3. สั่ง Android Media Scanner ให้อัปเดตวิดีโอขึ้นอันดับ 1 ในแกลเลอรี่ทันที
4. ก๊อปปี้แคปชัน + ลิงก์ตะกร้าส้มเข้า Clipboard ในมือถือ
5. สั่งปลุกหน้าจอ และเปิดแอป Shopee (Shopee Video) พร้อมกดโพสต์ได้เลยในคลิกเดียว!
"""

import os
import re
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ค้นหา adb.exe จากหลายๆ path มาตรฐานบน Windows
ADB_CANDIDATE_PATHS = [
    "adb",  # ใน PATH
    r"C:\Users\non_n\AppData\Local\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
    r"C:\platform-tools\adb.exe",
    r"C:\Program Files\platform-tools\adb.exe",
]


class PhoneSyncManager:
    """จัดการการเชื่อมต่อและส่งไฟล์ไปยังมือถือ Android ผ่าน ADB"""

    def __init__(self):
        self.adb_path = self._find_adb()

    def _find_adb(self) -> Optional[str]:
        """ค้นหา path ของ adb.exe"""
        # ลองเช็คจาก which / PATH ก่อน
        which_adb = shutil.which("adb")
        if which_adb:
            return which_adb

        for candidate in ADB_CANDIDATE_PATHS:
            if os.path.exists(candidate):
                return candidate
        return None

    def is_adb_available(self) -> bool:
        """ตรวจสอบว่ามี adb.exe พร้อมใช้งานหรือไม่"""
        if not self.adb_path:
            self.adb_path = self._find_adb()
        return bool(self.adb_path and os.path.exists(self.adb_path))

    def _run_adb(self, args: List[str], timeout: int = 20) -> subprocess.CompletedProcess:
        """รันคำสั่ง adb พร้อม return ผลลัพธ์"""
        if not self.is_adb_available():
            raise FileNotFoundError("ไม่พบ adb.exe บนระบบ")

        cmd = [self.adb_path] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )

    def get_connected_devices(self) -> List[Dict[str, Any]]:
        """
        ดึงรายชื่อมือถือ Android ทั้งหมดที่เชื่อมต่ออยู่
        Returns: list ของ dict { id, model, product, status, is_ready }
        """
        if not self.is_adb_available():
            return []

        try:
            res = self._run_adb(["devices", "-l"], timeout=8)
            if res.returncode != 0:
                logger.warning(f"ADB devices error: {res.stderr}")
                return []

            devices = []
            lines = res.stdout.strip().split("\n")
            for line in lines[1:]:  # ข้ามบรรทัดแรก "List of devices attached"
                line = line.strip()
                if not line or line.startswith("*"):
                    continue

                parts = line.split()
                if len(parts) >= 2:
                    dev_id = parts[0]
                    state = parts[1]

                    # สกัดชื่อรุ่น เช่น model:SM_S918B หรือ device:dm3q
                    model = "Android Phone"
                    for p in parts[2:]:
                        if p.startswith("model:"):
                            model = p.replace("model:", "").replace("_", " ")
                        elif p.startswith("device:") and model == "Android Phone":
                            model = p.replace("device:", "")

                    devices.append({
                        "id": dev_id,
                        "state": state,
                        "model": model,
                        "is_ready": (state == "device"),
                        "status_label": "พร้อมเชื่อมต่อ" if state == "device" else ("รออนุญาต USB Debugging บนมือถือ" if state == "unauthorized" else state)
                    })

            return devices
        except Exception as e:
            logger.error(f"Error checking adb devices: {e}")
            return []

    def push_video_to_phone(
        self,
        local_video_path: str,
        caption: str = "",
        open_shopee: bool = True,
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ผลักไฟล์วิดีโอเข้ามือถือ Android:
        1. ส่งไฟล์เข้า /sdcard/DCIM/Camera/ (หรือ /sdcard/Movies/)
        2. กระตุ้น Media Scanner ให้อัปเดตขึ้นคลังภาพทันที
        3. ก๊อปปี้แคปชันเข้า Clipboard ในมือถือ
        4. ปลุกหน้าจอ และเปิดแอป Shopee (Shopee Video)
        """
        if not self.is_adb_available():
            return {
                "success": False,
                "message": "ไม่พบโปรแกรม ADB บนคอมพิวเตอร์"
            }

        devices = self.get_connected_devices()
        ready_devices = [d for d in devices if d["is_ready"]]

        if not ready_devices:
            if devices:
                return {
                    "success": False,
                    "message": "ตรวจพบมือถือแล้ว แต่ยังไม่ได้กด 'อนุญาต (Allow USB Debugging)' บนหน้าจอมือถือของคุณ กรุณากดอนุญาตบนหน้าจอมือถือ",
                    "device": devices[0]
                }
            return {
                "success": False,
                "message": "ไม่พบมือถือ Android ที่เชื่อมต่อ กรุณาเสียบสาย USB และเปิดโหมด 'USB Debugging' ในเมนูผู้พัฒนา (Developer Options) บนมือถือ"
            }

        target_dev = ready_devices[0]
        dev_args = ["-s", device_id] if device_id else ["-s", target_dev["id"]]

        local_path = Path(local_video_path)
        if not local_path.exists():
            return {
                "success": False,
                "message": f"ไม่พบไฟล์วิดีโอบนเครื่อง: {local_video_path}"
            }

        filename = local_path.name
        # ปลายทางในมือถือ แนะนำให้ใส่โฟลเดอร์ Camera หรือ Movies
        remote_dest = f"/sdcard/DCIM/Camera/{filename}"

        try:
            # 1. adb push
            logger.info(f"📲 กำลังผลักไฟล์ {filename} ไปยังมือถือ {target_dev['model']}...")
            push_res = self._run_adb(dev_args + ["push", str(local_path.resolve()), remote_dest], timeout=60)
            if push_res.returncode != 0:
                # ลอง fallback ไปโฟลเดอร์ /sdcard/Movies/
                remote_dest = f"/sdcard/Movies/{filename}"
                push_res = self._run_adb(dev_args + ["push", str(local_path.resolve()), remote_dest], timeout=60)
                if push_res.returncode != 0:
                    return {
                        "success": False,
                        "message": f"ไม่สามารถส่งไฟล์ไปยังมือถือได้: {push_res.stderr.strip()}"
                    }

            # 2. บรอดแคสต์ Media Scanner ให้แกลเลอรี่รับรู้ไฟล์ใหม่ทันที
            logger.info("🔄 กำลังอัปเดต Media Gallery ในมือถือ...")
            self._run_adb(
                dev_args + [
                    "shell", "am", "broadcast",
                    "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                    "-d", f"file://{remote_dest}"
                ],
                timeout=10
            )

            # 3. เซ็ตข้อความลง Clipboard บนมือถือ (ถ้ามีแคปชัน)
            if caption:
                try:
                    # ป้องกันการติด escape character
                    clean_caption = caption.replace('"', '\\"').replace("`", "\\`")
                    # ส่งผ่าน service call clipboard หรือเขียนลงไฟล์ในมือถือ
                    self._run_adb(dev_args + ["shell", "cmd", "clipboard", "set", "text", f'"{clean_caption}"'], timeout=8)
                except Exception as e:
                    logger.debug(f"Clipboard set via cmd error: {e}")

            # 4. ปลุกหน้าจอมือถือ (KEYCODE_WAKEUP = 224)
            try:
                self._run_adb(dev_args + ["shell", "input", "keyevent", "224"], timeout=5)
            except Exception:
                pass

            # 5. เปิดแอป Shopee ทันที (ถ้าเปิดโหมด open_shopee)
            if open_shopee:
                logger.info("🚀 สั่งมือถือเปิดแอป Shopee...")
                # ลองเปิดแบบ deep link เข้า shopee://video หรือเปิด launcher Shopee
                shopee_res = self._run_adb(
                    dev_args + ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "shopee://video", "com.shopee.th"],
                    timeout=8
                )
                if shopee_res.returncode != 0 or "Error" in shopee_res.stdout:
                    # ถ้า deep link ไม่ติด ให้เปิดแอป Shopee โดยตรง
                    self._run_adb(
                        dev_args + ["shell", "monkey", "-p", "com.shopee.th", "-c", "android.intent.category.LAUNCHER", "1"],
                        timeout=8
                    )

            return {
                "success": True,
                "message": f"ส่งวิดีโอเข้าคลังภาพมือถือ {target_dev['model']} สำเร็จ! วิดีโออยู่บนสุดในแกลเลอรี่ พร้อมเปิดแอป Shopee แล้ว",
                "device": target_dev,
                "remote_path": remote_dest,
                "filename": filename
            }

        except Exception as e:
            logger.error(f"Push to phone failed: {e}")
            return {
                "success": False,
                "message": f"เกิดข้อผิดพลาดในการเชื่อมต่อมือถือ: {str(e)}"
            }

    def trigger_shopee_app(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """สั่งเปิดแอป Shopee บนมือถือเพื่อทดสอบการเชื่อมต่อ"""
        if not self.is_adb_available():
            return {"success": False, "message": "ไม่พบ ADB บนระบบ"}

        devices = self.get_connected_devices()
        ready = [d for d in devices if d["is_ready"]]
        if not ready:
            return {"success": False, "message": "ไม่พบมือถือ Android ที่พร้อมใช้งาน (กรุณาเสียบสาย USB และอนุญาต USB Debugging)"}

        dev = ready[0]
        dev_args = ["-s", device_id] if device_id else ["-s", dev["id"]]

        try:
            # ปลุกจอ
            self._run_adb(dev_args + ["shell", "input", "keyevent", "224"], timeout=5)
            # เปิด Shopee
            self._run_adb(
                dev_args + ["shell", "monkey", "-p", "com.shopee.th", "-c", "android.intent.category.LAUNCHER", "1"],
                timeout=8
            )
            return {
                "success": True,
                "message": f"สั่งเปิดแอป Shopee บนมือถือ {dev['model']} สำเร็จ!",
                "device": dev
            }
        except Exception as e:
            return {"success": False, "message": str(e)}


phone_sync_mgr = PhoneSyncManager()
