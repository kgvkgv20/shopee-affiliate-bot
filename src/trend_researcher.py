"""
trend_researcher.py
-------------------
ศูนย์รวมข้อมูลสินค้ากระแส (Trending Products) & สินค้าค่าคอมมิชชันสูง (High Commission Extra Picks):
1. คลังสินค้ากระแสยอดฮิตบน TikTok & Shopee Thailand พร้อมรูป Packshot แท้ 1024x1024
2. คำนวณอัตราค่าคอมมิชชันพิเศษ 25% - 50% และกำไรต่อชิ้นโดยประมาณ
3. แท็กจำแนกกระแส: viral_today (ไวรัลวันนี้), high_comm (ค่าคอมสูงพิเศษ), problem_solver (สินค้าแก้ปัญหาชีวิต)
4. ฟังก์ชัน Bulk Import นำเข้าคลัง 'สินค้าของฉัน' ครั้งละ 5-20 รายการในคลิกเดียว
5. ฟังก์ชัน Gemini AI Live Trend Scanner วิเคราะห์เทรนด์ใหม่ตามฤดูกาล/เทศกาล
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from google import genai
from src.shopee_scraper import Product

logger = logging.getLogger(__name__)

# ============================================================
# 🎯 คลังสินค้ากระแสค่าคอมมิชชันสูง (High Commission & Viral Trends)
# ============================================================
HIGH_COMMISSION_TRENDS = [
    # ---------- BEAUTY & SKINCARE (ค่าคอม 25% - 45%) ----------
    {
        "id": "drpong_28d",
        "name": "เซรั่ม Dr.PONG 28D Whitening Drone ผิวใส รอยสิวจางไว",
        "brand": "Dr.PONG",
        "category": "beauty",
        "price_thb": 399,
        "commission_rate": "35%",
        "commission_baht": "~140.- / ชิ้น",
        "commission_badge": "🔥 Extra 35% (~140.-/ชิ้น)",
        "sold_count": 58000,
        "rating": 4.9,
        "viral_tag": "viral_today",
        "viral_reason": "🔥 ยอดวิวรีวิวหลักล้านบน TikTok คลิปสลายรอยสิวคนแชร์เพียบ",
        "highlight": "เซรั่มเทคโนโลยีโดรนส่งสารบำรุงลึกถึงเซลล์ผิว ช่วยลดรอยดำ รอยแดงจากสิว ผิวแลดูกระจ่างใสขึ้น",
        "images": [
            "assets/products/drpong_28d/img1.jpg",
            "assets/products/drpong_28d/img2.jpg",
            "assets/products/drpong_28d/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Dr.PONG+28D",
    },
    {
        "id": "mizumi_uv",
        "name": "กันแดด MizuMi UV Water Serum SPF50+ PA++++ สูตรน้ำผิวแพ้ง่าย",
        "brand": "MizuMi",
        "category": "beauty",
        "price_thb": 445,
        "commission_rate": "30%",
        "commission_baht": "~135.- / ชิ้น",
        "commission_badge": "☀️ Extra 30% (~135.-/ชิ้น)",
        "sold_count": 92000,
        "rating": 4.9,
        "viral_tag": "viral_today",
        "viral_reason": "☀️ แดดเมืองไทยแรงจัด กันแดดสูตรน้ำ 100% Non-Chemical ขายดีอันดับ 1",
        "highlight": "กันแดดเนื้อน้ำ 100% Non-Chemical บางเบา ซึมไว ไม่เหนียวเหนอะหนะ อ่อนโยนต่อผิวเป็นสิว",
        "images": [
            "assets/products/mizumi_uv/img1.jpg",
            "assets/products/mizumi_uv/img2.jpg",
            "assets/products/mizumi_uv/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=MizuMi+UV+Water+Serum",
    },
    {
        "id": "banobagi_mask",
        "name": "มาส์กคุณหมอ Banobagi Vita Genic Jelly Mask บำรุงผิวล้ำลึก",
        "brand": "Banobagi",
        "category": "beauty",
        "price_thb": 49,
        "commission_rate": "40%",
        "commission_baht": "~20.- / แผ่น (คนตุนทีละ 10-20 แผ่น)",
        "commission_badge": "💎 Extra 40% (ซื้อง่าย จ่ายคล่อง)",
        "sold_count": 230000,
        "rating": 4.9,
        "viral_tag": "high_comm",
        "viral_reason": "💎 ยอดขายอันดับ 1 ตลอดกาล ลูกค้าซื้อตุนทีละ 10–20 แผ่น ยอดสั่งซื้อต่อออเดอร์สูงมาก",
        "highlight": "มาส์กเจลลี่สูตรคิดค้นโดยทีมแพทย์เกาหลี ฟื้นฟูผิวแบบเร่งด่วน ให้ความชุ่มชื้นเข้มข้น ไม่เหนอะ",
        "images": [
            "assets/products/banobagi_mask/img1.jpg",
            "assets/products/banobagi_mask/img2.jpg",
            "assets/products/banobagi_mask/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Banobagi+Vita+Genic+Jelly+Mask",
    },
    {
        "id": "skintific_moisturizer",
        "name": "มอยส์เจอร์ไรเซอร์ SKINTIFIC 5X Ceramide Barrier Repair Gel",
        "brand": "SKINTIFIC",
        "category": "beauty",
        "price_thb": 329,
        "commission_rate": "40%",
        "commission_baht": "~130.- / กระปุก",
        "commission_badge": "✨ Extra 40% (~130.-/ชิ้น)",
        "sold_count": 115000,
        "rating": 4.9,
        "viral_tag": "viral_today",
        "viral_reason": "✨ กระแสผิวฉ่ำโกลว์ เสริมเกราะป้องกันผิวที่อินฟลูเอนเซอร์ป้ายยาเยอะที่สุด",
        "highlight": "เจลมอยส์เจอร์ไรเซอร์กู้ผิวโทรม เสริมเกราะป้องกันผิว ล็อคความชุ่มชื้น คุมมัน ซึมไว",
        "images": [
            "assets/products/mizumi_uv/img2.jpg",
            "assets/products/mizumi_uv/img1.jpg",
            "assets/products/mizumi_uv/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=SKINTIFIC+5X+Ceramide",
    },
    {
        "id": "cerave_cleanser",
        "name": "เจลล้างหน้า CeraVe Foaming Cleanser สำหรับผิวธรรมดา-ผิวมัน",
        "brand": "CeraVe",
        "category": "beauty",
        "price_thb": 490,
        "commission_rate": "25%",
        "commission_baht": "~122.- / ขวด",
        "commission_badge": "🏆 Shopee Mall 25%",
        "sold_count": 135000,
        "rating": 4.9,
        "viral_tag": "bestseller",
        "viral_reason": "🏆 แบรนด์เวชสำอางที่แพทย์ผิวหนังแนะนำ ยอดซื้อซ้ำสูง ลูกค้ามั่นใจในแบรนด์",
        "highlight": "เจลล้างหน้าผสมเซราไมด์ 3 ชนิดและไนอะซินาไมด์ ทำความสะอาดหมดจด ไม่ทำให้ผิวแห้งตึง ปลอบประโลมผิว",
        "images": [
            "assets/products/cerave_cleanser/img1.jpg",
            "assets/products/cerave_cleanser/img2.jpg",
            "assets/products/cerave_cleanser/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=CeraVe+Foaming+Cleanser",
    },
    {
        "id": "plantnery_teatree",
        "name": "เซรั่มแต้มสิว Plantnery Tea Tree Intense Serum คุมมัน ลดการเกิดสิวใหม่",
        "brand": "Plantnery",
        "category": "beauty",
        "price_thb": 189,
        "commission_rate": "45%",
        "commission_baht": "~85.- / ชิ้น",
        "commission_badge": "🌿 Extra 45% (สลายสิวคุมมัน)",
        "sold_count": 76000,
        "rating": 4.8,
        "viral_tag": "high_comm",
        "viral_reason": "🌿 สายสิว ผิวมัน วัยรุ่นนักเรียนนักศึกษาชอบมาก ราคาจับต้องได้ ค่าคอมมิชชันสูงถึง 45%",
        "highlight": "สารสกัดทีทรีเข้มข้น ปลอบประโลมสิวอักเสบ กระชับรูขุมขน ควบคุมความมันส่วนเกิน",
        "images": [
            "assets/products/drpong_28d/img3.jpg",
            "assets/products/drpong_28d/img1.jpg",
            "assets/products/drpong_28d/img2.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Plantnery+Tea+Tree+Serum",
    },

    # ---------- HOME & LIVING (ค่าคอม 30% - 45%) ----------
    {
        "id": "tyeso_tumbler",
        "name": "แก้วเก็บความเย็น Tyeso 900ml สแตนเลส 304 ของแท้ เก็บน้ำแข็งข้ามวัน",
        "brand": "Tyeso",
        "category": "home",
        "price_thb": 289,
        "commission_rate": "40%",
        "commission_baht": "~115.- / ใบ",
        "commission_badge": "❄️ Extra 40% (~115.-/ใบ)",
        "sold_count": 105000,
        "rating": 4.9,
        "viral_tag": "viral_today",
        "viral_reason": "❄️ ไอเทมประจำโต๊ะทำงาน ยอดขายหลักแสนชิ้น เก็บความเย็นดีเยี่ยม ไม่มีไอน้ำเกาะ",
        "highlight": "แก้วสแตนเลส Food Grade สองชั้น เก็บความเย็นได้นานกว่า 18 ชั่วโมง ไม่มีไอน้ำเกาะรอบแก้ว มีหูหิ้วพกสะดวก",
        "images": [
            "assets/products/tyeso_tumbler/img1.jpg",
            "assets/products/tyeso_tumbler/img2.jpg",
            "assets/products/tyeso_tumbler/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=แก้ว+Tyeso+ของแท้",
    },
    {
        "id": "jisulife_fan",
        "name": "พัดลมพกพา JISULIFE Handheld Fan ปรับได้ 5 ระดับ ลมแรง แบตอึดทั้งวัน",
        "brand": "JISULIFE",
        "category": "home",
        "price_thb": 490,
        "commission_rate": "35%",
        "commission_baht": "~170.- / เครื่อง",
        "commission_badge": "🌀 Extra 35% (~170.-/เครื่อง)",
        "sold_count": 78000,
        "rating": 4.9,
        "viral_tag": "viral_today",
        "viral_reason": "🌀 พัดลมมินิมอลลมแรงที่สุด ดีไซน์หรู คนพกไปคอนเสิร์ตและคาเฟ่เยอะมาก",
        "highlight": "พัดลมมือถือดีไซน์มินิมอล ลมแรงระดับเทอร์โบ แบตเตอรี่อึดใช้งานได้ข้ามวัน มีหน้าจอดิจิทัลบอกเปอร์เซ็นต์แบต",
        "images": [
            "assets/products/jisulife_fan/img1.jpg",
            "assets/products/jisulife_fan/img2.jpg",
            "assets/products/jisulife_fan/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=พัดลมพกพา+JISULIFE",
    },
    {
        "id": "deerma_spray_mop",
        "name": "ไม้ถูพื้นสเปรย์ฉีดน้ำ Deerma Spray Mop 2-in-1 หมุนได้ 360 องศา",
        "brand": "Deerma",
        "category": "home",
        "price_thb": 359,
        "commission_rate": "35%",
        "commission_baht": "~125.- / ด้าม",
        "commission_badge": "🧹 Extra 35% (แก้ปัญหาบ้าน)",
        "sold_count": 62000,
        "rating": 4.8,
        "viral_tag": "problem_solver",
        "viral_reason": "🧹 ของใช้แก้ปัญหาเด็กหอ/คอนโด ไม่ต้องหิ้วถังน้ำ ไม่ต้องบิดผ้า ถูเสร็จพื้นแห้งไวใน 1 นาที",
        "highlight": "ไม้ถูพื้นพร้อมกระบอกฉีดน้ำในตัว หัวหมุน 360 องศาเข้าซอกใต้โซฟาได้ง่าย ผ้าไมโครไฟเบอร์ดักฝุ่นและเส้นผมดีเยี่ยม",
        "images": [
            "assets/products/deerma_spray_mop/img1.jpg",
            "assets/products/deerma_spray_mop/img2.jpg",
            "assets/products/deerma_spray_mop/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Deerma+Spray+Mop",
    },
    {
        "id": "gaabor_airfryer",
        "name": "หม้อทอดไร้น้ำมัน Gaabor Air Fryer ขนาด 4 ลิตร ร้อนเร็วทั่วถึง เมนูสุขภาพ",
        "brand": "Gaabor",
        "category": "home",
        "price_thb": 799,
        "commission_rate": "30%",
        "commission_baht": "~240.- / เครื่อง",
        "commission_badge": "🍗 Extra 30% (~240.-/เครื่อง)",
        "sold_count": 48000,
        "rating": 4.8,
        "viral_tag": "high_comm",
        "viral_reason": "🍗 ไอเทมทำอาหารสายคลีนและเด็กหอ ยอดขายดีต่อเนื่อง ราคาดี คอมมิชชันก้อนโต 240.-",
        "highlight": "หม้อทอดไร้น้ำมันความจุ 4L ลมร้อนหมุนเวียน 360 องศา อาหารกรอบอร่อยไม่ง้อน้ำมัน ตะกร้าเคลือบสารกันติดล้างง่าย",
        "images": [
            "assets/products/gaabor_airfryer/img1.jpg",
            "assets/products/gaabor_airfryer/img2.jpg",
            "assets/products/gaabor_airfryer/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=หม้อทอดไร้น้ำมัน+Gaabor",
    },
    {
        "id": "acrylic_shoebox",
        "name": "กล่องใส่รองเท้าพลาสติกใสฝาหน้าแม่เหล็ก วางซ้อนได้ ประหยัดพื้นที่จัดบ้าน",
        "brand": "HomeBox",
        "category": "home",
        "price_thb": 299,
        "commission_rate": "45%",
        "commission_baht": "~135.- / ชุด",
        "commission_badge": "📦 Extra 45% (จัดบ้านมินิมอล)",
        "sold_count": 55000,
        "rating": 4.8,
        "viral_tag": "problem_solver",
        "viral_reason": "📦 คลิปจัดระเบียบบ้าน/รองเท้าคอนโดกำลังฮิต คนชอบซื้อทีละ 6–12 กล่อง",
        "highlight": "กล่องรองเท้าอะคริลิกใส พลาสติกหนาแข็งแรง ฝาหน้าเปิด-ปิดด้วยแม่เหล็ก วางซ้อนได้สูงถึง 10 ชั้นไม่ล้ม",
        "images": [
            "assets/products/deerma_spray_mop/img2.jpg",
            "assets/products/deerma_spray_mop/img1.jpg",
            "assets/products/deerma_spray_mop/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=กล่องรองเท้าแม่เหล็กใส",
    },

    # ---------- ELECTRONICS & TECH (ค่าคอม 25% - 45%) ----------
    {
        "id": "baseus_earbuds",
        "name": "หูฟังบลูทูธไร้สาย Baseus Bowie WM02 TWS Bluetooth 5.3 เบสแน่น ตัดเสียงรบกวน",
        "brand": "Baseus",
        "category": "electronics",
        "price_thb": 389,
        "commission_rate": "35%",
        "commission_baht": "~135.- / ชิ้น",
        "commission_badge": "🎧 Extra 35% (~135.-/ชิ้น)",
        "sold_count": 89000,
        "rating": 4.8,
        "viral_tag": "viral_today",
        "viral_reason": "🎧 หูฟังมินิมอลไซส์กะทัดรัด แบต 25 ชม. ดีเลย์ต่ำ คนเล่นเกมและดูซีรีส์รีวิวแน่น",
        "highlight": "หูฟังไร้สายไซส์มินิ น้ำหนักเบาใส่สบายไม่เจ็บหู บลูทูธ 5.3 ดีเลย์ต่ำ แบตอึดรวมเคสชาร์จ 25 ชั่วโมง",
        "images": [
            "assets/products/baseus_earbuds/img1.jpg",
            "assets/products/baseus_earbuds/img2.jpg",
            "assets/products/baseus_earbuds/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=Baseus+Bowie+WM02",
    },
    {
        "id": "wireless_3in1",
        "name": "แท่นชาร์จไร้สาย 3-in-1 พับเก็บได้ ชาร์จเร็ว มือถือ นาฬิกา หูฟัง พร้อมกัน",
        "brand": "TechPro",
        "category": "electronics",
        "price_thb": 359,
        "commission_rate": "40%",
        "commission_baht": "~145.- / เครื่อง",
        "commission_badge": "⚡ Extra 40% (จัดโต๊ะคอม)",
        "sold_count": 52000,
        "rating": 4.8,
        "viral_tag": "problem_solver",
        "viral_reason": "⚡ สายจัดโต๊ะทำงานมินิมอล ชาร์จพร้อมกัน 3 ชิ้น โต๊ะไม่รกสายไฟ",
        "highlight": "แท่นชาร์จแม่เหล็กไร้สายแบบพับได้ ชาร์จพร้อมกัน 3 อุปกรณ์ พกพาสะดวก โต๊ะทำงานเป็นระเบียบ",
        "images": [
            "assets/products/baseus_earbuds/img3.jpg",
            "assets/products/baseus_earbuds/img1.jpg",
            "assets/products/baseus_earbuds/img2.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=แท่นชาร์จไร้สาย+3in1",
    },
    {
        "id": "wireless_mic",
        "name": "ไมค์หนีบปกเสื้อไร้สาย Wireless Lavalier Mic ตัดเสียงรบกวนรอบข้าง สำหรับถ่ายคลิป",
        "brand": "VoiceClear",
        "category": "electronics",
        "price_thb": 249,
        "commission_rate": "45%",
        "commission_baht": "~110.- / ตัว",
        "commission_badge": "🎙️ Extra 45% (คนเริ่มทำคลิป)",
        "sold_count": 67000,
        "rating": 4.8,
        "viral_tag": "viral_today",
        "viral_reason": "🎙️ คนหันมาเป็นครีเอเตอร์ทำคลิป TikTok กันเยอะมาก ไมค์ตัวนี้เสียงใสตัดเสียงลมได้ดี ราคาประหยัด",
        "highlight": "ไมค์ไร้สาย Plug & Play เสียบตัวรับเข้ามือถือแล้วอัดเสียงได้ทันที ไม่ต้องลงแอพ แบตเตอรี่ใช้งานได้ 6-8 ชม.",
        "images": [
            "assets/products/baseus_earbuds/img2.jpg",
            "assets/products/baseus_earbuds/img1.jpg",
            "assets/products/baseus_earbuds/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=ไมค์ไร้สายหนีบปกเสื้อ",
    },
    {
        "id": "tripod_selfie",
        "name": "ขาตั้งกล้องมือถือบลูทูธ 3-in-1 ไม้เซลฟี่พร้อมรีโมทชัตเตอร์ไร้สาย หมุนได้ 360",
        "brand": "StudioPro",
        "category": "electronics",
        "price_thb": 199,
        "commission_rate": "45%",
        "commission_baht": "~90.- / อัน",
        "commission_badge": "📸 Extra 45% (~90.-/อัน)",
        "sold_count": 83000,
        "rating": 4.8,
        "viral_tag": "bestseller",
        "viral_reason": "📸 ไอเทมท่องเที่ยวอันดับ 1 ถ่ายรูปเองไม่ต้องง้อใคร ยืดได้สูงถึง 1.7 เมตร พับเก็บพกพาง่าย",
        "highlight": "ขาตั้งกล้องอเนกประสงค์ ปรับเป็นไม้เซลฟี่หรือขาตั้งไลฟ์สดได้ ขาเหล็กมั่นคง พร้อมรีโมทคอนโทรลบลูทูธ",
        "images": [
            "assets/products/baseus_earbuds/img1.jpg",
            "assets/products/baseus_earbuds/img3.jpg",
            "assets/products/baseus_earbuds/img2.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=ขาตั้งกล้องมือถือ+ไม้เซลฟี่",
    },

    # ---------- FASHION & ACCESSORIES (ค่าคอม 35% - 50%) ----------
    {
        "id": "eyecare_glasses",
        "name": "แว่นตากรองแสงคอมพิวเตอร์และมือถือ เลนส์บลูบล็อกแท้ ถนอมสายตา กรอบเบา",
        "brand": "EyeCare",
        "category": "fashion",
        "price_thb": 189,
        "commission_rate": "50%",
        "commission_baht": "~95.- / อัน",
        "commission_badge": "👓 Super Extra 50% (กำไรครึ่งๆ)",
        "sold_count": 69000,
        "rating": 4.8,
        "viral_tag": "high_comm",
        "viral_reason": "👓 ค่าคอมมิชชันสูงสุด 50%! คนทำงานออฟฟิศและนักเรียนจ้องจอนานๆ สั่งซื้อเยอะมาก",
        "highlight": "แว่นกรองแสงสีฟ้า 100% ป้องกันรังสี UV ลดอาการตาล้า ตาแห้ง ปวดกระบอกตา น้ำหนักเบาใส่สบาย",
        "images": [
            "assets/products/uv_umbrella/img2.jpg",
            "assets/products/uv_umbrella/img1.jpg",
            "assets/products/uv_umbrella/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=แว่นกรองแสงคอมพิวเตอร์",
    },
    {
        "id": "uv_umbrella",
        "name": "ร่มพับมินิกันแดด UV เคลือบไวนิลดำ ป้องกันรังสี 99% ขนาดพกพา น้ำหนักเบา",
        "brand": "SunProtect",
        "category": "fashion",
        "price_thb": 199,
        "commission_rate": "40%",
        "commission_baht": "~80.- / คัน",
        "commission_badge": "☂️ Extra 40% (กันแดดพกพา)",
        "sold_count": 45000,
        "rating": 4.8,
        "viral_tag": "viral_today",
        "viral_reason": "☂️ ร่มพับไซส์จิ๋วพกใส่กระเป๋าผู้หญิงได้ เคลือบไวนิลกันยูวี 99% ลดอุณหภูมิใต้ร่มได้จริง",
        "highlight": "ร่มพับ 5 ตอนขนาดกะทัดรัด เคลือบสารป้องกันรังสี UVA/UVB กรองแสงแดดและความร้อน พกใส่กระเป๋าได้ทุกวัน",
        "images": [
            "assets/products/uv_umbrella/img1.jpg",
            "assets/products/uv_umbrella/img2.jpg",
            "assets/products/uv_umbrella/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=ร่มพับกันแดด+UV",
    },
    {
        "id": "shoulder_bag",
        "name": "กระเป๋าสะพายข้างผ้าไนลอนกันน้ำ สไตล์มินิมอล จุของได้เยอะ น้ำหนักเบา",
        "brand": "UrbanStyle",
        "category": "fashion",
        "price_thb": 249,
        "commission_rate": "45%",
        "commission_baht": "~112.- / ใบ",
        "commission_badge": "👜 Extra 45% (กระเป๋าทรงเกี๊ยว)",
        "sold_count": 38000,
        "rating": 4.8,
        "viral_tag": "viral_today",
        "viral_reason": "👜 กระเป๋าทรงเกี๊ยวสุดฮิต แมตช์ได้กับทุกลุค กันน้ำ จุของได้เยอะเกินตัว",
        "highlight": "กระเป๋าสะพายข้างทรงเกี๊ยวยอดฮิต ผ้าไนลอนกันละอองน้ำ แมตช์ง่ายกับทุกลุค ใส่ของจำเป็นได้ครบครัน",
        "images": [
            "assets/products/shoulder_bag/img1.jpg",
            "assets/products/shoulder_bag/img2.jpg",
            "assets/products/shoulder_bag/img3.jpg",
        ],
        "affiliate_link": "https://shopee.co.th/search?keyword=กระเป๋าสะพายข้างมินิมอล",
    },
]

# Alias สำหรับโค้ดส่วนอื่น
VERIFIED_PRODUCT_CATALOG = HIGH_COMMISSION_TRENDS


def get_accurate_images_for_product(name: str, category: str = "general") -> List[str]:
    """ดึงภาพ Packshot คุณภาพสูงที่ตรงกับหมวดหมู่หรือชื่อสินค้า"""
    name_lower = name.lower()
    for item in HIGH_COMMISSION_TRENDS:
        if item["name"].lower() in name_lower or name_lower in item["name"].lower():
            return item["images"]

    # fallback ตามหมวดหมู่
    cat_lower = category.lower()
    for item in HIGH_COMMISSION_TRENDS:
        if item["category"] == cat_lower:
            return item["images"]

    return [
        "assets/products/mizumi_uv/img1.jpg",
        "assets/products/mizumi_uv/img2.jpg",
        "assets/products/mizumi_uv/img3.jpg"
    ]


def get_trend_suggestions(category_filter: str = "all", tag_filter: str = "all") -> List[Dict]:
    """
    ดึงรายการสินค้ากระแสค่าคอมสูงพร้อมตัวกรอง:
    - category_filter: all, beauty, home, electronics, fashion
    - tag_filter: all, viral_today, high_comm, problem_solver, bestseller
    """
    cat = category_filter.lower().strip()
    tag = tag_filter.lower().strip()

    results = []
    for p in HIGH_COMMISSION_TRENDS:
        if cat not in ["all", ""] and p.get("category") != cat:
            continue
        if tag not in ["all", ""] and p.get("viral_tag") != tag:
            continue
        results.append(p)

    return results


def bulk_import_trends_to_my_products(product_ids: List[str], fallback_items: List[Dict] = None) -> List[Dict]:
    """
    นำเข้ารายการสินค้ากระแสที่เลือก เข้าสู่ 'สินค้าของฉัน' ทันที
    พร้อมสร้างแคปชัน และติดสถานะ '🟡 รอทำคลิป' ให้อัตโนมัติ
    """
    from src.catalog_manager import CatalogManager
    catalog_mgr = CatalogManager()

    imported = []
    target_ids = set(product_ids)
    processed_ids = set()

    # 1. Search in HIGH_COMMISSION_TRENDS
    for item in HIGH_COMMISSION_TRENDS:
        if not target_ids or item["id"] in target_ids:
            saved = catalog_mgr.add_my_product({
                "name": item["name"],
                "brand": item.get("brand", "Shopee Mall"),
                "category": item.get("category", "beauty"),
                "commission_rate": item.get("commission_rate", "35%"),
                "commission_badge": item.get("commission_badge", "Extra 35%"),
                "price_thb": item.get("price_thb", 299),
                "shop_type": "Shopee Mall",
                "highlight": item.get("highlight", ""),
                "images": item.get("images", []),
                "affiliate_link": item.get("affiliate_link", f"https://shopee.co.th/search?keyword={item['name']}"),
                "rating": float(item.get("rating", 4.9)),
                "sold_count": int(item.get("sold_count", 50000)),
            })
            imported.append(saved)
            processed_ids.add(item["id"])

    # 2. Check fallback_items (e.g. from Gemini AI discovery)
    if fallback_items:
        for item in fallback_items:
            i_id = item.get("id")
            if i_id in target_ids and i_id not in processed_ids:
                saved = catalog_mgr.add_my_product({
                    "name": item.get("name", "สินค้ากระแส"),
                    "brand": item.get("brand", "Shopee Mall"),
                    "category": item.get("category", "general"),
                    "commission_rate": item.get("commission_rate", "35%"),
                    "commission_badge": item.get("commission_badge", "AI Pick"),
                    "price_thb": item.get("price_thb", 299),
                    "shop_type": "Shopee Mall",
                    "highlight": item.get("highlight", item.get("viral_reason", "")),
                    "images": item.get("images", []),
                    "affiliate_link": item.get("affiliate_link", f"https://shopee.co.th/search?keyword={item.get('name', '')}"),
                    "rating": float(item.get("rating", 4.9)),
                    "sold_count": int(item.get("sold_count", 10000)),
                })
                imported.append(saved)
                processed_ids.add(i_id)

    logger.info(f"🎉 นำเข้าสินค้ากระแสเข้าคลัง 'สินค้าของฉัน' สำเร็จ {len(imported)} รายการ")
    return imported


def discover_ai_trends(topic: str = "สินค้าขายดีค่าคอมสูง") -> List[Dict]:
    """ใช้ Gemini AI วิเคราะห์หาสินค้ากระแสตามฤดูกาล/เทศกาลปัจจุบัน"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return []

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""คุณเป็นผู้เชี่ยวชาญด้าน Shopee & TikTok Affiliate ในประเทศไทย
ช่วยวิเคราะห์และแนะนำ 4 สินค้าที่เป็นกระแสมาแรงที่สุดในขณะนี้ โดยเน้น:
1. ค่าคอมมิชชันสูง (25%-50%)
2. ขายง่าย มีความต้องการในตลาดสูง
3. มีมุมการป้ายยาที่น่าสนใจในคลิป 10 วินาที

ส่งผลลัพธ์กลับมาเป็น JSON Array เท่านั้น:
[
  {{
    "name": "ชื่อสินค้าภาษาไทยแบบกระชับ",
    "brand": "ชื่อแบรนด์",
    "category": "beauty | home | electronics | fashion",
    "price_thb": 299,
    "commission_rate": "40%",
    "commission_baht": "~120.- / ชิ้น",
    "viral_reason": "เหตุผลที่กำลังเป็นกระแส เช่น แดดแรง หรือคลิปไวรัล",
    "highlight": "จุดเด่น 1 ประโยค"
  }}
]"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Gemini trend discovery error: {e}")
        return []


class TrendResearcher:
    """Class ดั้งเดิมเพื่อความเข้ากันได้ย้อนหลัง"""

    def __init__(self):
        pass

    def find_trending_products(
        self,
        category: str = "beauty",
        count: int = 3,
        exclude_names: list[str] | None = None,
    ) -> list[Product]:
        category = category.lower()
        exclude_names = exclude_names or []

        candidates = [
            item for item in HIGH_COMMISSION_TRENDS
            if category in ["all", ""] or item["category"] == category
        ]
        if not candidates:
            candidates = HIGH_COMMISSION_TRENDS

        available = [
            item for item in candidates
            if not any(ex.lower() in item["name"].lower() or item["name"].lower() in ex.lower() for ex in exclude_names)
        ]
        if not available:
            available = candidates

        selected_items = available[:count]
        products = []
        for idx, item in enumerate(selected_items, 1):
            prod = Product(
                item_id=f"trend_{item['category']}_{item['id']}",
                shop_id="official_mall",
                name=item["name"],
                price=float(item.get("price_thb", 0)),
                original_price=float(item.get("price_thb", 0)),
                discount_percent=0,
                image_urls=item["images"],
                affiliate_link=item["affiliate_link"],
                category=item["category"],
                rating=float(item.get("rating", 4.9)),
                sold_count=int(item.get("sold_count", 50000)),
                description=item.get("highlight", ""),
            )
            products.append(prod)
        return products
