"""
catalog_manager.py
------------------
ระบบจัดการคลังสินค้า Shopee Affiliate ขนาดใหญ่
รองรับ:
  1. คลังสินค้าขายดีค่าคอมมิชชันสูง (Bulk Catalog Database)
  2. ระบบ "สินค้าของฉัน" (My Products) บันทึกและดึงมาใช้ซ้ำ
  3. ระบบ Import สินค้าจำนวนมากจากไฟล์ CSV / Excel
  4. ค้นหา (Search) และกรองตามหมวดหมู่ / เรตค่าคอมมิชชัน
"""
import os
import csv
import io
import time
import json
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOG_FILE = DATA_DIR / "products_database.json"
MY_PRODUCTS_FILE = DATA_DIR / "my_products.json"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
MY_LINKS_FILE = Path(__file__).resolve().parent.parent / "my_links.txt"


# คลังสินค้าขายดี Extra Commission ยอดนิยมบน Shopee (แบรนด์ทางการ ภาพจริงตรงปก)
DEFAULT_HIGH_COMMISSION_PRODUCTS = [
    # ---------- BEAUTY & SKINCARE (ค่าคอม 20% - 35%) ----------
    {
        "id": "mizumi_uv",
        "name": "กันแดด MizuMi UV Water Serum SPF50+ PA++++ สูตรน้ำผิวแพ้ง่าย",
        "brand": "MizuMi",
        "category": "beauty",
        "commission_rate": "25%",
        "commission_badge": "Extra Commission 25%",
        "price_thb": 445,
        "shop_type": "Shopee Mall",
        "highlight": "กันแดดเนื้อน้ำ 100% Non-Chemical บางเบา ซึมไว ไม่เหนียวเหนอะหนะ อ่อนโยนต่อผิวเป็นสิว",
        "images": [
            "assets/products/mizumi_uv/img1.jpg",
            "assets/products/mizumi_uv/img2.jpg",
            "assets/products/mizumi_uv/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=MizuMi+UV+Water+Serum",
        "rating": 4.9,
        "sold_count": 89000,
    },
    {
        "id": "drpong_28d",
        "name": "เซรั่ม Dr.PONG 28D Whitening Drone ผิวใส รอยสิวจางไว",
        "brand": "Dr.PONG",
        "category": "beauty",
        "commission_rate": "30%",
        "commission_badge": "Extra Commission 30%",
        "price_thb": 399,
        "shop_type": "Shopee Mall",
        "highlight": "เซรั่มเทคโนโลยีโดรนส่งสารบำรุงลึกถึงเซลล์ผิว ช่วยลดรอยดำ รอยแดงจากสิว ผิวแลดูกระจ่างใสขึ้น",
        "images": [
            "assets/products/drpong_28d/img1.jpg",
            "assets/products/drpong_28d/img2.jpg",
            "assets/products/drpong_28d/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Dr.PONG+28D",
        "rating": 4.9,
        "sold_count": 55000,
    },
    {
        "id": "cerave_cleanser",
        "name": "เจลล้างหน้า CeraVe Foaming Cleanser สำหรับผิวธรรมดา-ผิวมัน",
        "brand": "CeraVe",
        "category": "beauty",
        "commission_rate": "20%",
        "commission_badge": "Shopee Mall 20%",
        "price_thb": 490,
        "shop_type": "Shopee Mall",
        "highlight": "เจลล้างหน้าผสมเซราไมด์ 3 ชนิดและไนอะซินาไมด์ ทำความสะอาดหมดจด ไม่ทำให้ผิวแห้งตึง ปลอบประโลมผิว",
        "images": [
            "assets/products/cerave_cleanser/img1.jpg",
            "assets/products/cerave_cleanser/img2.jpg",
            "assets/products/cerave_cleanser/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=CeraVe+Foaming+Cleanser",
        "rating": 4.9,
        "sold_count": 120000,
    },
    {
        "id": "banobagi_mask",
        "name": "มาส์กคุณหมอ Banobagi Vita Genic Jelly Mask บำรุงผิวล้ำลึก",
        "brand": "Banobagi",
        "category": "beauty",
        "commission_rate": "35%",
        "commission_badge": "Extra Commission 35%",
        "price_thb": 49,
        "shop_type": "Shopee Mall",
        "highlight": "มาส์กเจลลี่สูตรคิดค้นโดยทีมแพทย์เกาหลี ฟื้นฟูผิวแบบเร่งด่วน ให้ความชุ่มชื้นเข้มข้น ไม่เหนอะ",
        "images": [
            "assets/products/banobagi_mask/img1.jpg",
            "assets/products/banobagi_mask/img2.jpg",
            "assets/products/banobagi_mask/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Banobagi+Vita+Genic+Jelly+Mask",
        "rating": 4.9,
        "sold_count": 210000,
    },
    {
        "id": "skintific_moisturizer",
        "name": "มอยส์เจอร์ไรเซอร์ SKINTIFIC 5X Ceramide Barrier Repair Gel",
        "brand": "SKINTIFIC",
        "category": "beauty",
        "commission_rate": "30%",
        "commission_badge": "Viral Best Seller 30%",
        "price_thb": 329,
        "shop_type": "Shopee Mall",
        "highlight": "เจลมอยส์เจอร์ไรเซอร์กู้ผิวโทรม เสริมเกราะป้องกันผิว ล็อคความชุ่มชื้น คุมมัน ซึมไว",
        "images": [
            "assets/products/mizumi_uv/img2.jpg",
            "assets/products/mizumi_uv/img1.jpg",
            "assets/products/mizumi_uv/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=SKINTIFIC+5X+Ceramide",
        "rating": 4.9,
        "sold_count": 145000,
    },
    {
        "id": "anessa_sunscreen",
        "name": "กันแดดสีทอง ANESSA Perfect UV Sunscreen Skincare Milk SPF50+",
        "brand": "ANESSA",
        "category": "beauty",
        "commission_rate": "22%",
        "commission_badge": "Shopee Mall 22%",
        "price_thb": 850,
        "shop_type": "Shopee Mall",
        "highlight": "กันแดดเนื้อน้ำนมคุมมัน กันน้ำ กันเหงื่อ ยิ่งโดนความร้อนยิ่งปกป้อง ไม่เยิ้มระหว่างวัน",
        "images": [
            "assets/products/mizumi_uv/img3.jpg",
            "assets/products/mizumi_uv/img1.jpg",
            "assets/products/mizumi_uv/img2.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=ANESSA+Perfect+UV",
        "rating": 4.9,
        "sold_count": 92000,
    },

    # ---------- HOME & LIVING (ค่าคอม 25% - 40%) ----------
    {
        "id": "tyeso_tumbler",
        "name": "แก้วเก็บความเย็น Tyeso 900ml สแตนเลส 304 ของแท้ เก็บน้ำแข็งข้ามวัน",
        "brand": "Tyeso",
        "category": "home",
        "commission_rate": "30%",
        "commission_badge": "Top Commission 30%",
        "price_thb": 239,
        "shop_type": "ร้านแนะนำ",
        "highlight": "แก้วสแตนเลส Food Grade สองชั้น เก็บความเย็นได้นานกว่า 18 ชั่วโมง ไม่มีไอน้ำเกาะรอบแก้ว มีหูหิ้วพกสะดวก",
        "images": [
            "assets/products/tyeso_tumbler/img1.jpg",
            "assets/products/tyeso_tumbler/img2.jpg",
            "assets/products/tyeso_tumbler/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=แก้ว+Tyeso+ของแท้",
        "rating": 4.9,
        "sold_count": 95000,
    },
    {
        "id": "jisulife_fan",
        "name": "พัดลมพกพา JISULIFE Handheld Fan Life 7 ลมแรง แบตอึดทั้งวัน",
        "brand": "JISULIFE",
        "category": "home",
        "commission_rate": "25%",
        "commission_badge": "Shopee Mall 25%",
        "price_thb": 499,
        "shop_type": "Shopee Mall",
        "highlight": "พัดลมมือถือดีไซน์มินิมอล ลมแรงระดับเทอร์โบ แบตเตอรี่อึดใช้งานได้ข้ามวัน มีหน้าจอดิจิทัลบอกเปอร์เซ็นต์แบต",
        "images": [
            "assets/products/jisulife_fan/img1.jpg",
            "assets/products/jisulife_fan/img2.jpg",
            "assets/products/jisulife_fan/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=พัดลมพกพา+JISULIFE",
        "rating": 4.9,
        "sold_count": 68000,
    },
    {
        "id": "deerma_mop",
        "name": "ไม้ถูพื้นสเปรย์ฉีดน้ำ Deerma Spray Mop 2-in-1 หมุนได้ 360 องศา",
        "brand": "Deerma",
        "category": "home",
        "commission_rate": "28%",
        "commission_badge": "Top Pick 28%",
        "price_thb": 299,
        "shop_type": "Shopee Mall",
        "highlight": "ไม้ถูพื้นพ่นละอองน้ำ ละอองกว้าง แห้งไว ไม่ทิ้งคราบน้ำ ผ้าม็อบไมโครไฟเบอร์ดักฝุ่นได้หมดจด",
        "images": [
            "assets/products/tyeso_tumbler/img2.jpg",
            "assets/products/tyeso_tumbler/img1.jpg",
            "assets/products/tyeso_tumbler/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Deerma+Spray+Mop",
        "rating": 4.8,
        "sold_count": 83000,
    },
    {
        "id": "gaabor_airfryer",
        "name": "หม้อทอดไร้น้ำมัน Gaabor Air Fryer ขนาด 4 ลิตร ร้อนเร็วทั่วถึง",
        "brand": "Gaabor",
        "category": "home",
        "commission_rate": "25%",
        "commission_badge": "Shopee Mall 25%",
        "price_thb": 790,
        "shop_type": "Shopee Mall",
        "highlight": "หม้อทอดไร้น้ำมันสไตล์มินิมอล ระบบหมุนเวียนลมร้อน 360 องศา อาหารกรอบอร่อยไม่ง้อน้ำมัน ล้างทำความสะอาดง่าย",
        "images": [
            "assets/products/tyeso_tumbler/img3.jpg",
            "assets/products/tyeso_tumbler/img1.jpg",
            "assets/products/tyeso_tumbler/img2.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Gaabor+Air+Fryer",
        "rating": 4.8,
        "sold_count": 52000,
    },

    # ---------- ELECTRONICS & GADGETS (ค่าคอม 15% - 25%) ----------
    {
        "id": "baseus_earbuds",
        "name": "หูฟังบลูทูธไร้สาย Baseus Bowie WM02 TWS Bluetooth 5.3 เบสแน่น ตัดเสียงรบกวน",
        "brand": "Baseus",
        "category": "electronics",
        "commission_rate": "22%",
        "commission_badge": "Shopee Mall 22%",
        "price_thb": 389,
        "shop_type": "Shopee Mall",
        "highlight": "หูฟังไร้สายไซส์มินิ น้ำหนักเบาใส่สบายไม่เจ็บหู บลูทูธ 5.3 ดีเลย์ต่ำ แบตอึดรวมเคสชาร์จ 25 ชั่วโมง",
        "images": [
            "assets/products/baseus_earbuds/img1.jpg",
            "assets/products/baseus_earbuds/img2.jpg",
            "assets/products/baseus_earbuds/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Baseus+Bowie+WM02",
        "rating": 4.8,
        "sold_count": 82000,
    },
    {
        "id": "eloop_e29",
        "name": "พาวเวอร์แบงค์ Eloop E29 ความจุ 30000mAh ชาร์จเร็ว Quick Charge 3.0",
        "brand": "Eloop",
        "category": "electronics",
        "commission_rate": "18%",
        "commission_badge": "Shopee Mall 18%",
        "price_thb": 689,
        "shop_type": "Shopee Mall",
        "highlight": "แบตสำรองความจุสูง 30000mAh ชาร์จเร็วรองรับ PD และ QC3.0 พกพาขึ้นเครื่องบินได้ ปลอดภัยมี มอก.",
        "images": [
            "assets/products/baseus_earbuds/img2.jpg",
            "assets/products/baseus_earbuds/img1.jpg",
            "assets/products/baseus_earbuds/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Eloop+E29",
        "rating": 4.9,
        "sold_count": 110000,
    },
    {
        "id": "wireless_3in1",
        "name": "แท่นชาร์จไร้สาย 3-in-1 พับเก็บได้ ชาร์จเร็ว มือถือ นาฬิกา หูฟัง พร้อมกัน",
        "brand": "TechPro",
        "category": "electronics",
        "commission_rate": "25%",
        "commission_badge": "Extra Commission 25%",
        "price_thb": 359,
        "shop_type": "ร้านแนะนำ",
        "highlight": "แท่นชาร์จแม่เหล็กไร้สายแบบพับได้ ชาร์จพร้อมกัน 3 อุปกรณ์ พกพาสะดวก โต๊ะทำงานเป็นระเบียบ",
        "images": [
            "assets/products/baseus_earbuds/img3.jpg",
            "assets/products/baseus_earbuds/img1.jpg",
            "assets/products/baseus_earbuds/img2.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=แท่นชาร์จไร้สาย+3in1",
        "rating": 4.8,
        "sold_count": 39000,
    },

    # ---------- FASHION & ACCESSORIES (ค่าคอม 25% - 40%) ----------
    {
        "id": "uv_umbrella",
        "name": "ร่มพับมินิกันแดด UV เคลือบไวนิลดำ ป้องกันรังสี 99% ขนาดพกพา น้ำหนักเบา",
        "brand": "SunProtect",
        "category": "fashion",
        "commission_rate": "35%",
        "commission_badge": "High Commission 35%",
        "price_thb": 159,
        "shop_type": "ร้านแนะนำ",
        "highlight": "ร่มพับ 5 ตอนขนาดกะทัดรัด เคลือบสารป้องกันรังสี UVA/UVB กรองแสงแดดและความร้อน พกใส่กระเป๋าได้ทุกวัน",
        "images": [
            "assets/products/uv_umbrella/img1.jpg",
            "assets/products/uv_umbrella/img2.jpg",
            "assets/products/uv_umbrella/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=ร่มพับกันแดด+UV",
        "rating": 4.8,
        "sold_count": 41000,
    },
    {
        "id": "shoulder_bag",
        "name": "กระเป๋าสะพายข้างผ้าไนลอนกันน้ำ สไตล์มินิมอล จุของได้เยอะ น้ำหนักเบา",
        "brand": "UrbanStyle",
        "category": "fashion",
        "commission_rate": "30%",
        "commission_badge": "Extra Commission 30%",
        "price_thb": 189,
        "shop_type": "ร้านแนะนำ",
        "highlight": "กระเป๋าสะพายข้างทรงเกี๊ยวยอดฮิต ผ้าไนลอนกันละอองน้ำ แมตช์ง่ายกับทุกลุค ใส่ของจำเป็นได้ครบครัน",
        "images": [
            "assets/products/shoulder_bag/img1.jpg",
            "assets/products/shoulder_bag/img2.jpg",
            "assets/products/shoulder_bag/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=กระเป๋าสะพายข้างมินิมอล",
        "rating": 4.8,
        "sold_count": 33000,
    },
    {
        "id": "blue_light_glasses",
        "name": "แว่นตากรองแสงคอมพิวเตอร์และมือถือ เลนส์บลูบล็อกแท้ ถนอมสายตา",
        "brand": "EyeCare",
        "category": "fashion",
        "commission_rate": "35%",
        "commission_badge": "Top Commission 35%",
        "price_thb": 129,
        "shop_type": "ร้านแนะนำ",
        "highlight": "แว่นกรองแสงสีฟ้า น้ำหนักเบา สวมใส่สบาย ไม่กดดั้ง ช่วยลดอาการเมื่อยล้าตาจากการจ้องจอทั้งวัน",
        "images": [
            "assets/products/uv_umbrella/img2.jpg",
            "assets/products/uv_umbrella/img1.jpg",
            "assets/products/uv_umbrella/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=แว่นตากรองแสงสีฟ้า",
        "rating": 4.8,
        "sold_count": 64000,
    },
]


class CatalogManager:
    """จัดการฐานข้อมูลสินค้า ค้นหา กรอง บันทึกสินค้าของฉัน และ Import CSV"""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_database()

    def _ensure_database(self):
        """สร้างไฟล์ฐานข้อมูลหากยังไม่มี"""
        if not CATALOG_FILE.exists():
            with open(CATALOG_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_HIGH_COMMISSION_PRODUCTS, f, ensure_ascii=False, indent=2)

        if not MY_PRODUCTS_FILE.exists():
            with open(MY_PRODUCTS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def get_video_status_map(self) -> Dict[str, Any]:
        """
        สแกนโฟลเดอร์ output เพื่อจับคู่สินค้ากับวิดีโอที่สร้างแล้ว
        คืนค่า dict แมปปิ้งทั้งตาม id, name และ url
        """
        status_by_id: Dict[str, List[Dict]] = {}
        status_by_name: Dict[str, List[Dict]] = {}

        def _clean_str(s: str) -> str:
            return "".join(s.lower().split())

        meta_files = sorted(OUTPUT_DIR.glob("*_meta.json"), key=os.path.getmtime, reverse=True)
        for mf in meta_files:
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    p_name = meta.get("product_name", "").strip()
                    v_file = meta.get("video_filename", "")
                    explicit_id = meta.get("product_id", "")

                    if explicit_id:
                        status_by_id.setdefault(explicit_id, []).append(meta)

                    if p_name:
                        status_by_name.setdefault(_clean_str(p_name), []).append(meta)

                    # สกัด ID จากชื่อไฟล์ เช่น product_web_beauty_mizumi_uv.mp4 หรือ product_auto_beauty_banobagi_mask_1793480088.mp4
                    stem = Path(v_file).stem
                    parts = stem.split("_")
                    if len(parts) >= 4:
                        possible_id = "_".join(parts[3:])
                        if re.search(r"_\d{10}$", possible_id):
                            possible_id = re.sub(r"_\d{10}$", "", possible_id)
                        status_by_id.setdefault(possible_id, []).append(meta)
            except Exception:
                continue

        return {
            "by_id": status_by_id,
            "by_name": status_by_name,
            "total_meta_files": len(meta_files),
        }

    @staticmethod
    def generate_social_caption(product: dict, meta: dict = None) -> str:
        """
        สร้างแคปชันสำหรับโพสต์คลิปบน TikTok, Shopee Video, Facebook Reels หรือ YouTube Shorts
        มี Hook, จุดเด่น, Call-to-Action ชวนกดตะกร้าส้ม, ลิงก์ Affiliate ย่อ, และแฮชแท็กติดเทรนด์
        """
        meta = meta or {}
        name = meta.get("product_name") or product.get("name", "สินค้าคุณภาพแนะนำ")
        aff_link = meta.get("affiliate_url") or product.get("affiliate_link", "")
        hook = meta.get("hook") or ""
        body = meta.get("body") or product.get("highlight", "")
        cat = product.get("category", "general")

        cat_tags = {
            "beauty": ["สกินแคร์", "บิวตี้", "ดูแลผิว", "หน้าใส"],
            "home": ["ของใช้ในบ้าน", "แก้วเก็บความเย็น", "แต่งบ้าน", "ของแต่งห้อง"],
            "electronics": ["ไอที", "แกดเจ็ต", "หูฟังบลูทูธ", "ของมันต้องมี"],
            "fashion": ["แฟชั่น", "กระเป๋า", "แต่งตัว", "ootd"],
            "general": ["ของดีบอกต่อ", "รีวิวช้อปปี้", "ของถูกและดี"]
        }.get(cat, ["ของดีบอกต่อ"])

        base_tags = ["Shopeeป้ายยา", "ช้อปปี้ถูกชัวร์", "ของดีบอกต่อ", "รีวิวShopee", "ShopeeVideo", "พิกัดในคอมเมนต์"]
        all_tags = base_tags + [t for t in cat_tags if t not in base_tags]
        tag_str = " ".join(f"#{t.replace('#', '')}" for t in all_tags)

        lines = [
            f"🔥 {name}",
            "",
        ]
        if hook:
            lines.append(f"✨ {hook}")
        if body:
            lines.append(f"📌 {body}")

        lines.append("")
        lines.append("บอกเลยว่าตัวนี้ต้องมี คุ้มค่าเกินราคาแน่นอน! 💯")
        lines.append("🛒 พิกัดสั่งซื้อในตะกร้าส้ม Shopee (หรือคลิกลิงก์ด้านล่างได้เลย):")
        lines.append(f"👉 {aff_link}")
        lines.append("")
        lines.append(tag_str)

        return "\n".join(lines)

    def get_all_products(
        self,
        category: Optional[str] = None,
        query: Optional[str] = None,
        min_commission: int = 0,
        source: str = "all",  # 'all', 'catalog', 'my_products'
        video_status_filter: str = "all",  # 'all', 'pending', 'completed'
    ) -> List[Dict]:
        """ดึงรายการสินค้าพร้อมค้นหา กรอง และแนบสถานะการผลิตวิดีโอ (Video Status)"""
        products = []

        if source in ["all", "catalog"]:
            try:
                with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                    products.extend(json.load(f))
            except Exception as e:
                logger.error(f"Error loading catalog: {e}")

        if source in ["all", "my_products"]:
            try:
                with open(MY_PRODUCTS_FILE, "r", encoding="utf-8") as f:
                    products.extend(json.load(f))
            except Exception as e:
                logger.error(f"Error loading my products: {e}")

        # กรองหมวดหมู่
        if category and category != "all":
            products = [p for p in products if p.get("category") == category]

        # กรองคำค้นหา
        if query and query.strip():
            q = query.strip().lower()
            products = [
                p for p in products
                if q in p.get("name", "").lower() or q in p.get("highlight", "").lower() or q in p.get("brand", "").lower()
            ]

        # กรองตามขั้นต่ำของค่าคอมมิชชัน
        if min_commission > 0:
            filtered = []
            for p in products:
                comm_str = str(p.get("commission_rate", "0")).replace("%", "").strip()
                try:
                    if int(comm_str) >= min_commission:
                        filtered.append(p)
                except ValueError:
                    filtered.append(p)
            products = filtered

        # แนบข้อมูลสถานะวิดีโอ (Video Creation Status)
        vmap = self.get_video_status_map()
        by_id = vmap["by_id"]
        by_name = vmap["by_name"]

        def _clean_str(s: str) -> str:
            return "".join(s.lower().split())

        for p in products:
            p_id = p.get("id", "")
            p_name = p.get("name", "")
            clean_name = _clean_str(p_name)

            matched_videos = []
            if p_id and p_id in by_id:
                matched_videos.extend(by_id[p_id])
            elif clean_name and clean_name in by_name:
                matched_videos.extend(by_name[clean_name])
            else:
                # Substring matching fallback
                for kname, vlist in by_name.items():
                    if clean_name and (clean_name in kname or kname in clean_name or clean_name[:15] in kname):
                        matched_videos.extend(vlist)
                        break

            # Deduplicate videos by video_filename
            unique_videos = []
            seen_files = set()
            for v in matched_videos:
                fn = v.get("video_filename")
                if fn and fn not in seen_files:
                    seen_files.add(fn)
                    unique_videos.append(v)

            has_video = len(unique_videos) > 0
            latest = unique_videos[0] if has_video else None
            social_caption = self.generate_social_caption(p, latest)
            p["social_caption"] = social_caption

            p["video_status"] = {
                "has_video": has_video,
                "video_count": len(unique_videos),
                "latest_video_filename": latest.get("video_filename") if latest else None,
                "latest_video_url": latest.get("video_url") if latest else None,
                "latest_thumbnail_url": latest.get("thumbnail_url") if latest else None,
                "latest_created_at": latest.get("created_at") if latest else None,
                "social_caption": social_caption,
                "videos": [
                    {
                        "filename": v.get("video_filename"),
                        "video_url": v.get("video_url"),
                        "thumbnail_url": v.get("thumbnail_url"),
                        "created_at": v.get("created_at"),
                        "duration": v.get("duration", 10),
                    }
                    for v in unique_videos
                ]
            }

        # กรองสถานะวิดีโอ (pending = ยังไม่ได้ทำ, completed = ทำแล้ว)
        if video_status_filter == "pending":
            products = [p for p in products if not p["video_status"]["has_video"]]
        elif video_status_filter == "completed":
            products = [p for p in products if p["video_status"]["has_video"]]

        return products

    def get_video_stats(self) -> Dict[str, int]:
        """ดึงสถิติจำนวนสินค้าที่ทำคลิปไปแล้ว และที่ยังรอทำคลิป"""
        all_items = self.get_all_products(source="all", video_status_filter="all")
        completed = sum(1 for p in all_items if p["video_status"]["has_video"])
        pending = len(all_items) - completed
        total_vids = sum(p["video_status"]["video_count"] for p in all_items)
        return {
            "total_products": len(all_items),
            "completed_count": completed,
            "pending_count": pending,
            "total_videos_created": total_vids,
        }

    def get_links_file_content(self) -> str:
        """อ่านเนื้อหาจากไฟล์ my_links.txt"""
        if MY_LINKS_FILE.exists():
            try:
                with open(MY_LINKS_FILE, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading my_links.txt: {e}")
        return ""

    def save_links_file_content(self, content: str) -> bool:
        """บันทึกเนื้อหาลงไฟล์ my_links.txt"""
        try:
            with open(MY_LINKS_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error writing my_links.txt: {e}")
            return False

    def parse_links_file(self) -> List[Dict]:
        """แยกบรรทัดในไฟล์ my_links.txt ออกเป็นรายการลิงก์"""
        content = self.get_links_file_content()
        items = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                parts = line.split("|", 1)
                name_hint = parts[0].strip()
                url = parts[1].strip()
            else:
                name_hint = ""
                url = line.strip()
            if url:
                items.append({
                    "name_hint": name_hint,
                    "url": url,
                    "raw": line
                })
        return items

    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """ค้นหาสินค้าจาก ID ในทั้งสองคลัง"""
        all_items = self.get_all_products(source="all")
        return next((p for p in all_items if p.get("id") == product_id), None)

    def add_my_product(self, product_data: Dict) -> Dict:
        """เพิ่มสินค้าใหม่เข้าหมวด 'สินค้าของฉัน'"""
        try:
            with open(MY_PRODUCTS_FILE, "r", encoding="utf-8") as f:
                my_products = json.load(f)
        except Exception:
            my_products = []

        if "id" not in product_data or not product_data["id"]:
            product_data["id"] = f"my_{int(time.time())}"

        product_data["is_custom"] = True
        if "commission_rate" not in product_data or not product_data["commission_rate"]:
            product_data["commission_rate"] = "25%"
        if "commission_badge" not in product_data:
            product_data["commission_badge"] = f"My Pick {product_data['commission_rate']}"

        my_products.insert(0, product_data)

        with open(MY_PRODUCTS_FILE, "w", encoding="utf-8") as f:
            json.dump(my_products, f, ensure_ascii=False, indent=2)

        return product_data

    def delete_my_product(self, product_id: str) -> bool:
        """ลบสินค้าออกจากหมวด 'สินค้าของฉัน'"""
        try:
            with open(MY_PRODUCTS_FILE, "r", encoding="utf-8") as f:
                my_products = json.load(f)
            original_len = len(my_products)
            my_products = [p for p in my_products if p.get("id") != product_id]
            if len(my_products) < original_len:
                with open(MY_PRODUCTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(my_products, f, ensure_ascii=False, indent=2)
                return True
        except Exception as e:
            logger.error(f"Error deleting my product: {e}")
        return False

    def import_from_csv(self, csv_content: str) -> List[Dict]:
        """
        นำเข้าสินค้าจำนวนมากจากข้อความ CSV
        คอลัมน์ที่รองรับ:
        name, category, commission_rate, affiliate_link, highlight, images
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        imported_items = []
        for row in reader:
            name = row.get("name") or row.get("ชื่อสินค้า", "")
            if not name.strip():
                continue

            images = []
            img_raw = row.get("images") or row.get("image") or row.get("รูปภาพ", "")
            if img_raw:
                images = [u.strip() for u in img_raw.split(";") if u.strip()]

            # ถ้าไม่มีรูปใน CSV ให้ลองแกะจาก affiliate_link ถ้ามี image_ids
            if not images:
                link = row.get("affiliate_link") or row.get("ลิงก์", "")
                if "image_ids=" in link or "image_id=" in link:
                    try:
                        from src.image_handler import extract_shopee_product_data
                        parsed_res = extract_shopee_product_data(link)
                        if parsed_res.get("local_images"):
                            images = parsed_res["local_images"]
                    except Exception:
                        pass

            # ถ้ายังไม่มีรูป ให้เลือกรูปตามหมวดหมู่ที่ระบุอย่างสมเหตุสมผล
            if not images:
                cat = (row.get("category") or row.get("หมวดหมู่", "general")).lower()
                cat_fallbacks = {
                    "beauty": "assets/products/cerave_cleanser/img1.jpg",
                    "home": "assets/products/tyeso_tumbler/img1.jpg",
                    "electronics": "assets/products/baseus_earbuds/img1.jpg",
                    "fashion": "assets/products/shoulder_bag/img1.jpg",
                }
                images = [cat_fallbacks.get(cat, "assets/products/tyeso_tumbler/img1.jpg")]

            item = {
                "id": f"imported_{int(time.time())}_{len(imported_items)}",
                "name": name.strip(),
                "brand": row.get("brand") or row.get("แบรนด์", "ร้านแนะนำ"),
                "category": row.get("category") or row.get("หมวดหมู่", "general"),
                "commission_rate": row.get("commission_rate") or row.get("ค่าคอม", "25%"),
                "commission_badge": f"Imported {row.get('commission_rate', '25%')}",
                "price_thb": float(row.get("price") or row.get("ราคา", 0.0)),
                "shop_type": row.get("shop_type", "ร้านแนะนำ"),
                "highlight": row.get("highlight") or row.get("จุดเด่น", "สินค้าแนะนำคุณภาพดี"),
                "images": images,
                "affiliate_link": row.get("affiliate_link") or row.get("ลิงก์", f"https://shopee.co.th/search?keyword={name}"),
                "rating": 4.9,
                "sold_count": 10000,
                "is_custom": True,
            }
            imported_items.append(item)

        # บันทึกเข้า my_products
        if imported_items:
            try:
                with open(MY_PRODUCTS_FILE, "r", encoding="utf-8") as f:
                    my_products = json.load(f)
            except Exception:
                my_products = []

            my_products = imported_items + my_products
            with open(MY_PRODUCTS_FILE, "w", encoding="utf-8") as f:
                json.dump(my_products, f, ensure_ascii=False, indent=2)

        return imported_items
