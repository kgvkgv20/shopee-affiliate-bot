"""
discord_sender.py
-----------------
ส่งวิดีโอและแคปชันเข้า Discord อัตโนมัติผ่าน Discord Webhook
ข้อดี: ตั้งค่าง่ายที่สุดในโลก ไม่ต้องสร้าง Bot แค่ก๊อปปี้ Webhook URL มาวาง
วิดีโอจะเด้งเข้าห้องแชท Discord ในมือถือ กดเล่นและกดเซฟลงเครื่องได้ทันที
"""
import os
import logging
import requests
from src.gemini_generator import VideoContent
from src.video_creator import VideoResult

logger = logging.getLogger(__name__)


class DiscordSender:
    """
    ส่งคลิปวิดีโอ .mp4 และแคปชันเข้าห้องแชท Discord ผ่าน Webhook
    """

    def __init__(self):
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("ต้องกำหนด DISCORD_WEBHOOK_URL ใน .env")

    def send_video(
        self,
        video_result: VideoResult,
        content: VideoContent,
        affiliate_link: str,
    ) -> bool:
        """
        ส่งไฟล์วิดีโอ .mp4 พร้อมแคปชันและลิงก์สินค้าเข้า Discord
        """
        video_path = video_result.video_path
        if not os.path.exists(video_path):
            logger.error(f"❌ ไม่พบไฟล์วิดีโอ: {video_path}")
            return False

        message_text = (
            f"🎬 **Shopee Video พร้อมโพสต์!**\n"
            f"📦 **สินค้า:** {content.product_name}\n"
            f"🛒 **ลิงก์สินค้า:** {affiliate_link}\n\n"
            f"📝 **แคปชัน (คัดลอกไปโพสต์):**\n"
            f"```{content.caption}\n\n{content.hashtag_string}```\n"
            f"⚠️ *อย่าลืมติ๊ก 'ระบุว่าเป็นเนื้อหา AI' ก่อนกดโพสต์ใน Shopee Video นะครับ*"
        )

        try:
            with open(video_path, "rb") as f:
                files = {
                    "file": (os.path.basename(video_path), f, "video/mp4")
                }
                data = {
                    "content": message_text
                }
                resp = requests.post(self.webhook_url, data=data, files=files, timeout=30)
                if resp.status_code in [200, 204]:
                    logger.info("  ✅ ส่งวิดีโอไปยัง Discord สำเร็จ!")
                    return True
                else:
                    logger.error(f"  ❌ ส่ง Discord ไม่สำเร็จ ({resp.status_code}): {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"  ❌ เกิดข้อผิดพลาดในการส่ง Discord: {e}")
            return False
