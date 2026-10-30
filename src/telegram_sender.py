"""
telegram_sender.py
------------------
ส่งวิดีโอ + caption + hashtag ผ่าน Telegram Bot

ผู้ใช้รับวิดีโอใน Telegram → forward ไปโพสต์ Shopee เองได้เลย
(ประหยัดเวลา 80% เหลือแค่ 30 วิ/คลิป)
"""
import os
import asyncio
import logging
from pathlib import Path
from telegram import Bot, InputMediaVideo
from telegram.constants import ParseMode
from src.video_creator import VideoResult
from src.gemini_generator import VideoContent

logger = logging.getLogger(__name__)


class TelegramSender:
    """
    ส่งวิดีโอไปยัง Telegram

    Setup:
    1. เปิด Telegram → ค้นหา @BotFather
    2. /newbot → ตั้งชื่อ → รับ Token
    3. ส่งข้อความใดก็ได้ให้ bot
    4. เปิด https://api.telegram.org/bot{TOKEN}/getUpdates
       → หา "chat": {"id": XXXX}  ← นี่คือ CHAT_ID
    """

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        if not self.token or not self.chat_id:
            raise ValueError(
                "ต้องกำหนด TELEGRAM_BOT_TOKEN และ TELEGRAM_CHAT_ID ใน .env\n"
                "ดู README.md สำหรับวิธีสร้าง Bot"
            )
        self.bot = Bot(token=self.token)

    async def send_video_async(
        self,
        video_result: VideoResult,
        content: VideoContent,
        affiliate_link: str,
    ) -> bool:
        """
        ส่งวิดีโอพร้อม caption ไปยัง Telegram

        Returns:
            True ถ้าส่งสำเร็จ
        """
        try:
            # ===== สร้าง Caption (Markdown) =====
            caption = self._build_caption(content, affiliate_link)

            # ===== ส่งวิดีโอ =====
            video_path = Path(video_result.video_path)
            thumb_path = Path(video_result.thumbnail_path)

            with open(video_path, "rb") as video_file:
                thumb_data = open(thumb_path, "rb") if thumb_path.exists() else None
                await self.bot.send_video(
                    chat_id=self.chat_id,
                    video=video_file,
                    thumbnail=thumb_data,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    supports_streaming=True,
                    width=720,
                    height=1280,
                )
                if thumb_data:
                    thumb_data.close()

            logger.info(f"✅ ส่งวิดีโอไปยัง Telegram สำเร็จ: {video_result.product_name[:40]}")

            # ===== ส่ง instruction แยก =====
            await self.send_posting_guide(content)
            return True

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def send_posting_guide(self, content: VideoContent):
        """ส่งคำแนะนำการโพสต์แยกต่างหาก"""
        guide = (
            "📋 *วิธีโพสต์ใน Shopee*\n\n"
            "1️⃣ บันทึกวิดีโอด้านบน\n"
            "2️⃣ เปิด Shopee → Live/Video\n"
            "3️⃣ เลือกวิดีโอ → วาง caption ด้านล่าง\n"
            "4️⃣ ✅ โพสต์เลย\\!\n\n"
            f"📌 *ชื่อวิดีโอ:*\n`{self._escape_md(content.video_title)}`\n\n"
            f"🏷️ *Hashtags:*\n`{self._escape_md(content.hashtag_string)}`"
        )
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=guide,
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    async def send_daily_summary(self, total: int, success: int):
        """ส่งสรุปผลประจำวัน"""
        msg = (
            "🤖 *Shopee Bot — สรุปประจำวัน*\n\n"
            f"📦 สินค้าทั้งหมด: {total}\n"
            f"✅ สร้างสำเร็จ: {success}\n"
            f"❌ ล้มเหลว: {total - success}\n\n"
            "โพสต์วิดีโอด้านบนใน Shopee ได้เลย\\!"
        )
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    def _build_caption(self, content: VideoContent, affiliate_link: str) -> str:
        """สร้าง caption สำหรับ Telegram (Markdown V2)"""
        # Key points
        points_text = "\n".join(
            f"✨ {self._escape_md(p)}" for p in content.key_points[:3]
        )

        caption = (
            f"🔥 *{self._escape_md(content.video_title)}*\n\n"
            f"{points_text}\n\n"
            f"💰 {self._escape_md(content.call_to_action)}\n\n"
            f"🛒 [ซื้อเลย]({affiliate_link})\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"{self._escape_md(content.hashtag_string[:300])}"
        )
        return caption[:1024]  # Telegram caption limit

    @staticmethod
    def _escape_md(text: str) -> str:
        """Escape Markdown V2 special characters"""
        special = r"_*[]()~`>#+-=|{}.!"
        for ch in special:
            text = text.replace(ch, f"\\{ch}")
        return text

    def send_video(self, video_result: VideoResult, content: VideoContent, affiliate_link: str) -> bool:
        """Sync wrapper สำหรับ send_video_async"""
        return asyncio.run(self.send_video_async(video_result, content, affiliate_link))
