"""
main.py
-------
Orchestrator หลัก — รัน pipeline ทั้งหมด

Usage:
    python main.py                    # รันด้วยค่า default
    python main.py --category beauty  # ระบุหมวดหมู่
    python main.py --products 3       # จำนวนสินค้า
    python main.py --test             # ทดสอบด้วย mock data
"""
import os
import sys
import asyncio
import logging
import argparse
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# ป้องกัน UnicodeEncodeError บน Windows terminal
if sys.platform == "win32":
    try:
        if sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr.encoding != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# โหลด .env ก่อนทุกอย่าง
load_dotenv()

# สร้าง output dir ก่อนตั้ง FileHandler
os.makedirs("output", exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("output/run.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

from src.shopee_scraper import ShopeeAffiliateAPI, Product
from src.gemini_generator import GeminiContentGenerator
from src.video_creator import FFmpegVideoCreator
from src.telegram_sender import TelegramSender
from src.trend_researcher import TrendResearcher
from src.google_drive_uploader import GoogleDriveUploader
from src.routine_manager import RoutineManager


def parse_args():
    parser = argparse.ArgumentParser(description="Shopee Affiliate Bot")
    parser.add_argument(
        "--trend",
        "--auto",
        action="store_true",
        help="ค้นหาสินค้ากระแสขายดีบน Shopee และสร้างคลิปอัตโนมัติเต็มรูปแบบ",
    )
    parser.add_argument(
        "--routine",
        action="store_true",
        help="รันแบบ Routine อัตโนมัติ: สลับหมวดหมู่สินค้าต่อเนื่อง และป้องกันการทำสินค้าซ้ำ",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="รันวนลูปแบบต่อเนื่องไม่รู้จบ (เช่น ทุก 4 หรือ 6 ชั่วโมง)",
    )
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=4.0,
        help="ระยะเวลาพักระหว่างรอบการรันลูป (ชั่วโมง เช่น 4 หรือ 6)",
    )
    parser.add_argument(
        "--url",
        help="ลิงก์สินค้า Shopee หรือ Affiliate Link ของคุณเอง",
    )
    parser.add_argument(
        "--name",
        help="ชื่อสินค้าที่ต้องการทำคลิป (เช่น 'เซรั่ม Dr.PONG 28D')",
    )
    parser.add_argument(
        "--images",
        nargs="+",
        help="รายการไฟล์ภาพสินค้าในเครื่อง หรือ Image URLs (เช่น img1.jpg img2.jpg)",
    )
    parser.add_argument(
        "--file",
        help="ไฟล์รายการสินค้าที่ต้องการรัน (JSON หรือ TXT เช่น my_products.json)",
    )
    parser.add_argument(
        "--category",
        default=os.getenv("TARGET_CATEGORIES", "beauty").split(",")[0],
        help="หมวดหมู่สินค้า (beauty/fashion/electronics/home/all)",
    )
    parser.add_argument(
        "--products",
        type=int,
        default=int(os.getenv("PRODUCTS_PER_DAY", "3")),
        help="จำนวนสินค้าต่อรัน",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="ทดสอบด้วย mock data",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="สร้างวิดีโอแต่ไม่ส่ง Telegram",
    )
    return parser.parse_args()


async def process_product(
    product: Product,
    gemini: GeminiContentGenerator,
    creator: FFmpegVideoCreator,
    sender: TelegramSender | None,
    drive_uploader: GoogleDriveUploader | None = None,
    language: str = "th",
) -> tuple[bool, str | None]:
    """
    ประมวลผลสินค้า 1 ตัวผ่าน pipeline ทั้งหมด

    Returns:
        (True, video_path) ถ้าสำเร็จทั้งหมด
    """
    logger.info(f"🔄 เริ่มประมวลผล: {product.short_name}")

    # ===== Step 1: Gemini สร้าง Script + Hashtag =====
    logger.info("  🤖 Gemini กำลังสร้าง script...")
    content = gemini.generate_video_content(product, language=language)
    logger.info(f"  ✅ Script: {content.video_title}")
    logger.info(f"  ✅ Hashtags: {len(content.hashtags)} tags")

    # ===== Step 2: ดาวน์โหลดรูปสินค้า =====
    logger.info("  🖼️ ดาวน์โหลดรูปสินค้า...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        image_paths = creator.download_images(product, tmp_dir)

        if not image_paths:
            logger.error(f"  ❌ ไม่มีรูปสินค้า — ข้าม {product.item_id}")
            return False, None

        logger.info(f"  ✅ ได้รูป {len(image_paths)} รูป")

        # ===== Step 3: FFmpeg สร้างวิดีโอ =====
        logger.info("  🎬 FFmpeg กำลังสร้างวิดีโอ...")
        video_result = creator.create_video(product, content, image_paths)
        logger.info(f"  ✅ วิดีโอ: {video_result.video_path} ({video_result.file_size_mb:.1f} MB)")

    # ===== Step 4: อัปโหลดไปยัง Google Drive =====
    if drive_uploader:
        logger.info("  ☁️ บันทึกแพ็กเกจวิดีโอและแคปชันสำหรับ Google Drive...")
        drive_uploader.upload_video_bundle(
            video_path=video_result.video_path,
            thumbnail_path=video_result.thumbnail_path,
            caption_text=f"{content.caption}\n\n{content.hashtag_string}",
            product_name=product.name,
        )

    # ===== Step 5: ส่งไปยัง Telegram =====
    if sender:
        logger.info("  📲 ส่งไปยัง Telegram...")
        success = sender.send_video(video_result, content, product.affiliate_link)
        if success:
            logger.info("  ✅ ส่ง Telegram สำเร็จ!")
        else:
            logger.warning("  ⚠️ ส่ง Telegram ล้มเหลว แต่วิดีโออยู่ใน output/")
    else:
        logger.info(f"  💾 วิดีโออยู่ที่: {video_result.video_path}")

    return True, video_result.video_path


async def run_pipeline(args, routine_mgr: RoutineManager | None = None) -> int:
    category = args.category
    if args.routine and routine_mgr:
        category = routine_mgr.get_next_category()

    logger.info("=" * 60)
    logger.info(f"🛒 Shopee Affiliate Bot — {'[ROUTINE MODE]' if args.routine else 'เริ่มทำงาน'}")
    logger.info(f"   หมวดหมู่ประจำรอบ: {category.upper()}")
    logger.info(f"   จำนวนสินค้า: {args.products}")
    logger.info(f"   Mode: {'TEST' if args.test else 'LIVE'}")
    logger.info("=" * 60)

    # ===== Init Services =====
    try:
        shopee = ShopeeAffiliateAPI()
        gemini = GeminiContentGenerator()
        creator = FFmpegVideoCreator(output_dir="output")
        sender = None if args.no_telegram else TelegramSender()
        trend_researcher = TrendResearcher()
        drive_uploader = GoogleDriveUploader()
    except Exception as e:
        logger.error(f"❌ Init ล้มเหลว: {e}")
        return 1

    # ===== ดึงสินค้า =====
    if args.routine:
        excluded = routine_mgr.get_excluded_names() if routine_mgr else []
        logger.info(f"🔥 [ROUTINE] ค้นหาสินค้ากระแสหมวด {category} (ยกเว้นสินค้าเดิม {len(excluded)} ชิ้น)...")
        products = trend_researcher.find_trending_products(
            category=category,
            count=args.products,
            exclude_names=excluded,
        )
    elif args.trend:
        logger.info(f"🔥 ค้นหาสินค้ากระแสขายดีล่าสุดบน Shopee หมวด {category}...")
        products = trend_researcher.find_trending_products(
            category=category,
            count=args.products,
        )
    elif args.url or args.name or args.file:
        logger.info("📦 โหลดสินค้าที่คุณกำหนดเอง (--url / --name / --file)...")
        products = shopee.load_custom_products(
            name=args.name,
            affiliate_link=args.url,
            images=args.images,
            category=category,
            file_path=args.file,
        )
    elif args.test:
        products = shopee._get_mock_products(args.products)
        logger.info("  ⚠️ ใช้ตัวอย่างสินค้าจริง (--test mode)")
    else:
        logger.info(f"🔍 ดึงสินค้า Top {args.products} จาก Shopee...")
        products = shopee.get_top_products(
            category=category,
            limit=args.products,
        )

    if not products:
        logger.error("❌ ไม่พบสินค้า")
        return 1

    logger.info(f"✅ พบ {len(products)} สินค้า")

    # ===== Process แต่ละสินค้า =====
    success_count = 0
    language = os.getenv("CONTENT_LANGUAGE", "th")

    for i, product in enumerate(products, 1):
        logger.info(f"\n{'─'*50}")
        logger.info(f"📦 สินค้า {i}/{len(products)}: {product.short_name}")
        logger.info(f"   ราคา: {product.price_thb} (ลด {product.discount_percent}%)")
        logger.info(f"   Rating: {product.rating}⭐ | ขายแล้ว: {product.sold_count:,}")

        ok, vpath = await process_product(product, gemini, creator, sender, drive_uploader, language)
        if ok:
            success_count += 1
            if args.routine and routine_mgr and vpath:
                routine_mgr.record_video(product.name, category, vpath)

    # บันทึกจบ Routine รอบนี้
    if args.routine and routine_mgr:
        routine_mgr.advance_category()
        routine_mgr.record_run_completion()
        logger.info("\n" + routine_mgr.get_summary())

    # ===== สรุปผล =====
    logger.info(f"\n{'='*60}")
    logger.info(f"🎉 เสร็จสิ้น! สำเร็จ {success_count}/{len(products)} สินค้า")
    logger.info(f"   วิดีโออยู่ที่: output/")
    logger.info("=" * 60)

    # ส่งสรุปไปยัง Telegram
    if sender:
        await sender.send_daily_summary(len(products), success_count)

    return 0 if success_count == len(products) else 1


async def main():
    args = parse_args()
    routine_mgr = RoutineManager() if (args.routine or args.loop) else None

    if args.loop:
        logger.info(f"🔁 โหมดวนลูป (Loop Mode): เริ่มต้นทำงานทุกๆ {args.interval_hours} ชั่วโมง...")
        while True:
            try:
                await run_pipeline(args, routine_mgr)
            except Exception as e:
                logger.error(f"⚠️ เกิดข้อผิดพลาดในรอบนี้: {e}", exc_info=True)

            sleep_seconds = int(args.interval_hours * 3600)
            logger.info(f"\n💤 พักผ่อน... จะเริ่มรอบถัดไปในอีก {args.interval_hours} ชั่วโมง ({sleep_seconds:,} วินาที)")
            await asyncio.sleep(sleep_seconds)
    else:
        return await run_pipeline(args, routine_mgr)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
