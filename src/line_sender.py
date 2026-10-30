"""
line_sender.py
--------------
ส่งแพ็กเกจวิดีโอ แคปชัน และปุ่มลิงก์สินค้าเข้า LINE (LINE Messaging API)
เมื่อมีคลิปใหม่พร้อมโพสต์ ผู้ใช้จะได้รับการแจ้งเตือนทาง LINE ทันที
พร้อมปุ่มกดที่สามารถแตะแล้วเปิดแอป Shopee ไปยังสินค้าได้โดยตรง
"""
import os
import logging
import requests
from src.gemini_generator import VideoContent
from src.video_creator import VideoResult

logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LineSender:
    """
    ส่งการแจ้งเตือนและข้อมูลวิดีโอไปยัง LINE Official Account / ผู้ใช้ ผ่าน LINE Messaging API
    """

    def __init__(self):
        self.access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        self.user_id = os.getenv("LINE_USER_ID")

        if not self.access_token or not self.user_id:
            raise ValueError("ต้องกำหนด LINE_CHANNEL_ACCESS_TOKEN และ LINE_USER_ID ใน .env")

    def send_video_package(
        self,
        video_result: VideoResult,
        content: VideoContent,
        affiliate_link: str,
        video_download_url: str | None = None,
    ) -> bool:
        """
        ส่งข้อมูลคลิป แคปชัน และปุ่มลิงก์สินค้า Shopee ไปยัง LINE

        Args:
            video_result: ผลลัพธ์วิดีโอที่สร้างเสร็จ
            content: สคริปต์ แคปชัน และแฮชแท็ก
            affiliate_link: ลิงก์สินค้า Shopee สำหรับกดแล้วเด้งเข้าแอป
            video_download_url: ลิงก์ดาวน์โหลดวิดีโอ (ถ้ามี)
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

        # ข้อความแคปชันสำหรับกดก๊อปปี้ง่ายๆ
        caption_text = (
            f"🎬 คลิป Shopee Video พร้อมโพสต์!\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 สินค้า: {content.product_name}\n\n"
            f"📝 แคปชันสำหรับโพสต์ (กดค้างเพื่อคัดลอก):\n"
            f"{content.caption}\n\n"
            f"{content.hashtag_string}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ กฎเหล็ก Shopee: อย่าลืมติ๊กเปิด \"ระบุว่าเป็นเนื้อหาที่สร้างโดย AI\" ก่อนโพสต์ทุกครั้งนะครับ"
        )

        # Flex Message การ์ดสินค้าสวยงามพร้อมปุ่มกดเด้งเข้า Shopee
        flex_card = {
            "type": "bubble",
            "hero": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🛍️ SHOPEE AFFILIATE CLIP",
                        "weight": "bold",
                        "color": "#FFFFFF",
                        "size": "sm"
                    }
                ],
                "backgroundColor": "#EE4D2D",
                "paddingAll": "12px",
                "alignItems": "center"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": content.product_name,
                        "weight": "bold",
                        "size": "md",
                        "wrap": True,
                        "color": "#333333"
                    },
                    {
                        "type": "text",
                        "text": f"ความยาว: 10 วินาที | ขนาดไฟล์: {video_result.file_size_mb:.1f} MB",
                        "size": "xs",
                        "color": "#888888",
                        "margin": "sm"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": "💡 แตะปุ่มด้านล่างเพื่อเปิดดูสินค้าใน Shopee และผูกตะกร้าส้ม",
                        "size": "xs",
                        "color": "#666666",
                        "wrap": True,
                        "margin": "md"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#EE4D2D",
                        "action": {
                            "type": "uri",
                            "label": "🛒 เปิดดูสินค้าใน Shopee",
                            "uri": affiliate_link
                        }
                    }
                ]
            }
        }

        # ถ้ามีลิงก์ดาวน์โหลดวิดีโอ ให้เพิ่มปุ่มดาวน์โหลด
        if video_download_url:
            flex_card["footer"]["contents"].append({
                "type": "button",
                "style": "secondary",
                "action": {
                    "type": "uri",
                    "label": "📥 ดาวน์โหลดวิดีโอ (.mp4)",
                    "uri": video_download_url
                }
            })

        messages = [
            {"type": "text", "text": caption_text},
            {
                "type": "flex",
                "altText": f"คลิปสินค้า Shopee: {content.product_name}",
                "contents": flex_card
            }
        ]

        payload = {
            "to": self.user_id,
            "messages": messages,
        }

        try:
            resp = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                logger.info("  ✅ ส่งแจ้งเตือนไปยัง LINE สำเร็จ!")
                return True
            else:
                logger.error(f"  ❌ ส่ง LINE ไม่สำเร็จ ({resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            logger.error(f"  ❌ เกิดข้อผิดพลาดในการส่ง LINE: {e}")
            return False
