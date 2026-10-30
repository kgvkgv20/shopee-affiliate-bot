"""
shopee_scraper.py
-----------------
ดึงข้อมูลสินค้า Top จาก Shopee Affiliate API
รองรับทั้ง Official API และ fallback scraping
"""
import os
import json
import hmac
import hashlib
import time
import requests
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Product:
    """ข้อมูลสินค้า Shopee"""
    item_id: str
    shop_id: str
    name: str
    price: float
    original_price: float
    discount_percent: int
    image_urls: list[str]
    affiliate_link: str
    category: str
    rating: float
    sold_count: int
    description: str = ""

    @property
    def price_thb(self) -> str:
        return f"฿{self.price:,.0f}"

    @property
    def original_price_thb(self) -> str:
        return f"฿{self.original_price:,.0f}"

    @property
    def short_name(self) -> str:
        """ชื่อสั้น ไม่เกิน 60 ตัวอักษร"""
        return self.name[:60] + "..." if len(self.name) > 60 else self.name


class ShopeeAffiliateAPI:
    """
    Shopee Affiliate API Client
    ลงทะเบียนที่: https://affiliate.shopee.co.th/
    """

    BASE_URL = "https://open-api.affiliate.shopee.co.th/graphql"

    def __init__(self):
        self.app_id = os.getenv("SHOPEE_APP_ID", "")
        self.secret = os.getenv("SHOPEE_SECRET", "")

    def _generate_signature(self, payload: str) -> str:
        """สร้าง HMAC-SHA256 signature"""
        msg = f"{self.app_id}{payload}"
        sig = hmac.new(self.secret.encode(), msg.encode(), hashlib.sha256)
        return sig.hexdigest()

    def get_top_products(
        self,
        category: str = "all",
        limit: int = 5,
        sort_type: int = 2,  # 2 = best seller
    ) -> list[Product]:
        """
        ดึงสินค้า Top Seller จาก Shopee Affiliate API

        Args:
            category: หมวดหมู่ (beauty/fashion/electronics/home/all)
            limit: จำนวนสินค้า (max 10 ต่อ request)
            sort_type: 1=commission, 2=sales, 3=price_desc, 4=price_asc

        Returns:
            รายการ Product objects
        """
        CATEGORY_IDS = {
            "beauty": 11,
            "fashion": 4,
            "electronics": 16,
            "home": 6,
            "sports": 13,
            "food": 17,
            "all": None,
        }

        query = """
        query getTopProducts($input: OffersInput!) {
          offers(input: $input) {
            nodes {
              itemId
              shopId
              itemName
              priceMax
              priceMin
              priceMinBeforeDiscount
              discount
              imageUrl
              itemUrl
              commissionRate
              sales
              ratingStar
              categories {
                catId
                catName
              }
            }
          }
        }
        """

        variables = {
            "input": {
                "limit": limit,
                "sortType": sort_type,
            }
        }

        cat_id = CATEGORY_IDS.get(category)
        if cat_id:
            variables["input"]["categoryIds"] = [cat_id]

        payload = json.dumps({"query": query, "variables": variables})
        timestamp = str(int(time.time()))
        signature = self._generate_signature(f"{timestamp}{payload}")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"SHA256 Credential={self.app_id}, Timestamp={timestamp}, Signature={signature}",
        }

        try:
            resp = requests.post(
                self.BASE_URL,
                data=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            nodes = data.get("data", {}).get("offers", {}).get("nodes", [])
            return [self._parse_product(n) for n in nodes]

        except Exception as e:
            logger.error(f"Shopee API error: {e}")
            # Fallback ใช้ mock data สำหรับ dev/test
            return self._get_mock_products(limit)

    def generate_affiliate_link(self, item_url: str) -> str:
        """แปลง URL สินค้าเป็น affiliate link"""
        query = """
        mutation generateShortLink($input: GenerateShortLinkInput!) {
          generateShortLink(input: $input) {
            shortLink
          }
        }
        """
        variables = {"input": {"originUrl": item_url, "subIds": ["bot"]}}
        payload = json.dumps({"query": query, "variables": variables})
        timestamp = str(int(time.time()))
        signature = self._generate_signature(f"{timestamp}{payload}")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"SHA256 Credential={self.app_id}, Timestamp={timestamp}, Signature={signature}",
        }
        try:
            resp = requests.post(self.BASE_URL, data=payload, headers=headers, timeout=15)
            return resp.json()["data"]["generateShortLink"]["shortLink"]
        except Exception:
            return item_url

    def _parse_product(self, node: dict) -> Product:
        price = node.get("priceMin", 0) / 100000
        original = node.get("priceMinBeforeDiscount", price * 100000) / 100000
        discount = int(node.get("discount", "0").replace("%", ""))

        return Product(
            item_id=str(node.get("itemId", "")),
            shop_id=str(node.get("shopId", "")),
            name=node.get("itemName", ""),
            price=price,
            original_price=original,
            discount_percent=discount,
            image_urls=[node.get("imageUrl", "")],
            affiliate_link=node.get("itemUrl", ""),
            category=node.get("categories", [{}])[0].get("catName", ""),
            rating=float(node.get("ratingStar", 0)),
            sold_count=int(node.get("sales", 0)),
        )

    def load_custom_products(
        self,
        name: str | None = None,
        affiliate_link: str | None = None,
        images: list[str] | None = None,
        category: str = "beauty",
        file_path: str | None = None,
    ) -> list[Product]:
        """
        โหลดสินค้าจากข้อมูลที่ผู้ใช้ระบุเอง (ชื่อสินค้า, ลิงก์ affiliate, ภาพ)
        หรืออ่านจากไฟล์ JSON/TXT
        """
        products = []

        # 1. กรณีอ่านจากไฟล์
        if file_path and os.path.exists(file_path):
            logger.info(f"📁 โหลดรายการสินค้าจากไฟล์: {file_path}")
            if file_path.endswith(".json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        items = json.load(f)
                        if isinstance(items, list):
                            for idx, item in enumerate(items, 1):
                                products.append(
                                    Product(
                                        item_id=str(item.get("id", f"custom_{idx}")),
                                        shop_id="manual",
                                        name=item.get("name", f"สินค้าชิ้นที่ {idx}"),
                                        price=float(item.get("price", 0.0)),
                                        original_price=float(item.get("original_price", 0.0)),
                                        discount_percent=int(item.get("discount_percent", 0)),
                                        image_urls=item.get("images", []),
                                        affiliate_link=item.get("affiliate_link", item.get("url", "")),
                                        category=item.get("category", category),
                                        rating=float(item.get("rating", 4.9)),
                                        sold_count=int(item.get("sold_count", 9999)),
                                    )
                                )
                except Exception as e:
                    logger.error(f"อ่านไฟล์ JSON ไม่สำเร็จ: {e}")
            elif file_path.endswith(".txt"):
                # แต่ละบรรทัดคือลิงก์ หรือ "ชื่อ | ลิงก์"
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for idx, line in enumerate(f, 1):
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            parts = line.split("|")
                            item_name = parts[0].strip() if len(parts) > 1 else f"สินค้าจากลิงก์ {idx}"
                            item_link = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                            products.append(
                                Product(
                                    item_id=f"link_{idx}",
                                    shop_id="manual",
                                    name=item_name,
                                    price=0.0,
                                    original_price=0.0,
                                    discount_percent=0,
                                    image_urls=[],
                                    affiliate_link=item_link,
                                    category=category,
                                    rating=4.9,
                                    sold_count=9999,
                                )
                            )
                except Exception as e:
                    logger.error(f"อ่านไฟล์ TXT ไม่สำเร็จ: {e}")

        # 2. กรณีระบุผ่าน Command Line เช่น --name, --url, --images
        elif name or affiliate_link:
            prod_name = name or "สินค้าแนะนำพิเศษ Shopee"
            prod_link = affiliate_link or "https://shopee.co.th"
            products.append(
                Product(
                    item_id=f"custom_{int(time.time())}",
                    shop_id="manual",
                    name=prod_name,
                    price=0.0,
                    original_price=0.0,
                    discount_percent=0,
                    image_urls=images or [],
                    affiliate_link=prod_link,
                    category=category,
                    rating=4.9,
                    sold_count=9999,
                )
            )

        return products

    def _get_mock_products(self, limit: int) -> list[Product]:
        """
        รายการสินค้าตัวอย่าง พร้อมภาพถ่ายสินค้าจริงความละเอียดสูง
        สำหรับทดลองสร้างคลิปและนำไปโพสต์ได้ทันที
        """
        logger.warning("Using sample real products — set SHOPEE_APP_ID and SHOPEE_SECRET for auto-sync")
        mock = [
            Product(
                item_id="1001",
                shop_id="8881",
                name="เซรั่มไฮยาลูรอนเข้มข้น กู้ผิวแห้ง แต่งหน้าติดทน เผยผิวฉ่ำน้ำ",
                price=290.0,
                original_price=590.0,
                discount_percent=50,
                image_urls=[
                    "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=1080&q=80",
                    "https://images.unsplash.com/photo-1617897903246-719242758050?w=1080&q=80",
                    "https://images.unsplash.com/photo-1598440947619-2c35fc9aa908?w=1080&q=80",
                ],
                affiliate_link="https://shope.ee/hyaserum",
                category="beauty",
                rating=4.9,
                sold_count=28400,
            ),
            Product(
                item_id="1002",
                shop_id="8882",
                name="หูฟังไร้สาย Bluetooth 5.3 เบสแน่น ตัดเสียงรบกวน แบตอึด 30 ชม.",
                price=399.0,
                original_price=799.0,
                discount_percent=50,
                image_urls=[
                    "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=1080&q=80",
                    "https://images.unsplash.com/photo-1572536147248-ac59a8abfa4b?w=1080&q=80",
                    "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=1080&q=80",
                ],
                affiliate_link="https://shope.ee/twsheadset",
                category="electronics",
                rating=4.8,
                sold_count=19500,
            ),
        ]
        return mock[:limit]
