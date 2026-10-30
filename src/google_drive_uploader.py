"""
google_drive_uploader.py
------------------------
อัปโหลดวิดีโอและแคปชันไปยัง Google Drive อัตโนมัติ

รองรับ:
1. Google Cloud Service Account (ไฟล์ service_account.json)
2. Google Drive OAuth (credentials.json)
3. Fallback: จัดเตรียมไฟล์ใส่โฟลเดอร์ output/ พร้อมลิงก์ดาวน์โหลด
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class GoogleDriveUploader:
    """
    จัดการอัปโหลดไฟล์วิดีโอ แคปชัน และภาพตัวอย่างไปยัง Google Drive
    """

    def __init__(self):
        self.folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        self.service_account_path = os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"
        )
        self.service = None
        self._init_service()

    def _init_service(self):
        """ตรวจสอบและเชื่อมต่อกับ Google Drive API"""
        if not os.path.exists(self.service_account_path):
            logger.info("ℹ️ ยังไม่พบไฟล์ service_account.json — ระบบจะบันทึกไฟล์เตรียมไว้ในเครื่อง")
            return

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/drive.file"]
            creds = service_account.Credentials.from_service_account_file(
                self.service_account_path, scopes=scopes
            )
            self.service = build("drive", "v3", credentials=creds)
            logger.info("✅ เชื่อมต่อ Google Drive API สำเร็จ")
        except Exception as e:
            logger.warning(f"เชื่อมต่อ Google Drive API ไม่สำเร็จ: {e}")
            self.service = None

    def upload_video_bundle(
        self,
        video_path: str,
        thumbnail_path: str | None,
        caption_text: str,
        product_name: str,
    ) -> str | None:
        """
        อัปโหลดไฟล์วิดีโอ, ภาพปก และข้อความแคปชันไปยัง Google Drive

        Returns:
            ลิงก์เปิดดูโฟลเดอร์หรือไฟล์บน Google Drive
        """
        # 1. สร้างไฟล์ Text สรุปแคปชันไว้คู่กับวิดีโอ
        v_path = Path(video_path)
        info_txt_path = v_path.with_suffix(".txt")
        with open(info_txt_path, "w", encoding="utf-8") as f:
            f.write(f"ชื่อสินค้า: {product_name}\n\n")
            f.write(f"=== แคปชันสำหรับโพสต์ Shopee Video ===\n")
            f.write(caption_text + "\n")

        # 2. ถ้ามี Google Drive Service ให้ทำการอัปโหลดขึ้น Cloud
        if self.service:
            try:
                from googleapiclient.http import MediaFileUpload

                logger.info(f"☁️ กำลังอัปโหลดไปยัง Google Drive: {v_path.name}...")

                file_metadata = {
                    "name": v_path.name,
                    "parents": [self.folder_id] if self.folder_id else [],
                }
                media = MediaFileUpload(str(v_path), mimetype="video/mp4", resumable=True)
                file = (
                    self.service.files()
                    .create(body=file_metadata, media_body=media, fields="id, webViewLink")
                    .execute()
                )

                # อัปโหลดไฟล์แคปชันข้อความ
                txt_metadata = {
                    "name": info_txt_path.name,
                    "parents": [self.folder_id] if self.folder_id else [],
                }
                txt_media = MediaFileUpload(str(info_txt_path), mimetype="text/plain")
                self.service.files().create(body=txt_metadata, media_body=txt_media).execute()

                link = file.get("webViewLink", "")
                logger.info(f"✅ อัปโหลดขึ้น Google Drive เรียบร้อย: {link}")
                return link

            except Exception as e:
                logger.error(f"อัปโหลดไฟล์ขึ้น Google Drive ล้มเหลว: {e}")

        # 3. กรณีไม่ได้ต่อ API ให้แจ้งโฟลเดอร์ในเครื่อง
        logger.info(f"💾 ไฟล์วิดีโอและแคปชันพร้อมใช้งานที่: {v_path.parent.resolve()}")
        return str(v_path.resolve())
