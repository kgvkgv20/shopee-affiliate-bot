"""
telegram_sender.py
------------------
ส่งวิดีโอ + caption + hashtag ผ่าน Telegram Bot
ผู้ใช้รับวิดีโอใน Telegram → บันทึกลงมือถือ แล้วโพสต์ Shopee Video ได้ทันทีใน 30 วินาที
"""
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional
from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class TelegramSender:
    """
    ส่งวิดีโอไปยัง Telegram
    Setup:
    1. เปิด Telegram → ค้นหา @BotFather
    2. /newbot → ตั้งชื่อ → รับ Token
    3. ส่งข้อความใดก็ได้ให้ bot หรือกด Start
    4. เปิด https://api.telegram.org/bot{TOKEN}/getUpdates
       → หา "chat": {"id": XXXX}  ← นี่คือ CHAT_ID
    """

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = str(chat_id or os.getenv("TELEGRAM_CHAT_ID", ""))
        self.bot = Bot(token=self.token) if self.token else None

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id and self.bot)

    async def send_test_message(self, message: str = "🎉 บอท Shopee Affiliate เชื่อมต่อ Telegram สำเร็จแล้ว!") -> bool:
        """ส่งข้อความทดสอบการเชื่อมต่อ"""
        if not self.is_configured():
            logger.warning("Telegram Bot is not configured")
            return False
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
            )
            return True
        except Exception as e:
            logger.error(f"Telegram test message error: {e}")
            raise e

    async def send_direct_video(
        self,
        video_path: str,
        caption: str,
        thumbnail_path: Optional[str] = None,
        title: Optional[str] = None,
        hashtags: Optional[str] = None,
        affiliate_url: Optional[str] = None,
    ) -> bool:
        """
        ส่งวิดีโอจากไฟล์ตรง พร้อมแคปชันและไกด์โพสต์ Shopee
        """
        if not self.is_configured():
            raise ValueError("กรุณาระบุ Telegram Bot Token และ Chat ID")

        v_file = Path(video_path)
        if not v_file.exists():
            raise FileNotFoundError(f"ไม่พบไฟล์วิดีโอ: {video_path}")

        try:
            # 1. ข้อความใน Caption ใต้วิดีโอ
            clean_caption = caption[:1000] if caption else (title or "คลิปแนะนำสินค้า Shopee")
            if affiliate_url and affiliate_url not in clean_caption:
                clean_caption += f"\n\n🛒 พิกัด: {affiliate_url}"

            with open(v_file, "rb") as video_file:
                thumb_data = None
                if thumbnail_path and Path(thumbnail_path).exists():
                    thumb_data = open(thumbnail_path, "rb")

                await self.bot.send_video(
                    chat_id=self.chat_id,
                    video=video_file,
                    thumbnail=thumb_data,
                    caption=clean_caption,
                    supports_streaming=True,
                    width=720,
                    height=1280,
                )

                if thumb_data:
                    thumb_data.close()

            # 2. ส่งข้อความแยกเพื่อให้ก๊อปปี้แคปชันและแฮชแท็กได้ง่ายๆ
            guide_text = (
                "📱 *Shopee Video Guide*\n\n"
                "1️⃣ กดบันทึกวิดีโอด้านบนลงมือถือ\n"
                "2️⃣ เปิดแอป Shopee → โพสต์คลิปใน Shopee Video\n"
                "3️⃣ ก๊อปปี้ข้อความด้านล่างไปวางในช่องแคปชัน\n"
                "4️⃣ แนบสินค้าในตะกร้าส้ม แล้วกดโพสต์ได้เลย! 🛒\n\n"
                "━━━━━━━━━━━━━━━\n"
                f"📌 *ข้อความแคปชันสำหรับโพสต์:*\n`{clean_caption}`\n\n"
            )
            if hashtags:
                guide_text += f"🏷️ *Hashtags:*\n`{hashtags}`"

            await self.bot.send_message(
                chat_id=self.chat_id,
                text=guide_text,
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.info(f"✅ ส่งวิดีโอ {v_file.name} เข้า Telegram เรียบร้อยแล้ว")
            return True

        except Exception as e:
            logger.error(f"Error sending video to Telegram: {e}")
            raise e
