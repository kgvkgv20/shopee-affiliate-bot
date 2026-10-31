import os
import sys
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def create_excel_template():
    template_dir = Path("data/templates")
    template_dir.mkdir(parents=True, exist_ok=True)
    
    xlsx_path = template_dir / "shopee_products_template.xlsx"
    csv_path = template_dir / "shopee_products_template.csv"
    
    wb = openpyxl.Workbook()
    
    # ---------------- Sheet 1: รายการสินค้า (Products) ----------------
    ws1 = wb.active
    ws1.title = "รายการสินค้าสำหรับทำคลิป"
    
    headers = [
        "ชื่อสินค้า (จำเป็น)",
        "ลิงก์ Shopee หรือ ลิงก์ Affiliate (จำเป็น)",
        "หมวดหมู่ (beauty/home/electronics/fashion/general)",
        "จุดเด่นสินค้า / ข้อความช่วยเขียนบท (ไม่บังคับ)",
        "ค่าคอมมิชชัน % (ไม่บังคับ)",
        "ลิงก์รูปภาพที่ 1 (ไม่บังคับ)",
        "ลิงก์รูปภาพที่ 2 (ไม่บังคับ)",
        "ลิงก์รูปภาพที่ 3 (ไม่บังคับ)",
    ]
    
    # Sample Rows
    samples = [
        [
            "กันแดด MizuMi UV Water Serum SPF50+ PA++++",
            "https://s.shopee.co.th/sample_mizumi_uv",
            "beauty",
            "กันแดดเนื้อน้ำสูตรอ่อนโยน ไม่เหนอะหนะ คุมมัน ไม่เป็นคราบ ผิวแพ้ง่ายใช้ได้",
            "30%",
            "",
            "",
            ""
        ],
        [
            "แก้วเก็บความเย็น Tyeso 900ml สแตนเลส 304 ฝา 2in1",
            "https://s.shopee.co.th/sample_tyeso_cup",
            "home",
            "เก็บความเย็นได้นานกว่า 18 ชม. น้ำไม่เกาะรอบแก้ว สแตนเลสเกรดอาหาร ปลอดภัย",
            "25%",
            "",
            "",
            ""
        ],
        [
            "หูฟังบลูทูธไร้สาย Baseus Bowie WM02 ดีเลย์ต่ำ",
            "https://s.shopee.co.th/sample_baseus_wm02",
            "electronics",
            "ขนาดจิ๋วพกพาสะดวก แบตอึด 25 ชม. ดีเลย์ต่ำ 0.06 วิ เบสแน่น เสียงคมชัด",
            "20%",
            "",
            "",
            ""
        ],
        [
            "กระเป๋าผ้าแคนวาสมินิมอล มีซิปและช่องใส่ของด้านใน",
            "https://s.shopee.co.th/sample_canvas_bag",
            "fashion",
            "ผ้าแคนวาสหนาเกรดพรีเมียม จุของได้จุใจ มีซิปกันของหล่น แมตช์ง่ายทุกลุค",
            "35%",
            "",
            "",
            ""
        ],
    ]
    
    # Header Styling
    header_fill = PatternFill(start_color="EE4D2D", end_color="EE4D2D", fill_type="solid") # Shopee Orange
    header_font = Font(name="Tahoma", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Tahoma", size=10)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    # Write Headers
    ws1.append(headers)
    ws1.row_dimensions[1].height = 32
    
    for col_idx in range(1, len(headers) + 1):
        cell = ws1.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
        
    # Write Samples
    for row_idx, row_data in enumerate(samples, start=2):
        ws1.append(row_data)
        ws1.row_dimensions[row_idx].height = 26
        for col_idx in range(1, len(row_data) + 1):
            cell = ws1.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border
            if col_idx in [3, 5]: # Category & Comm
                cell.alignment = center_align
            else:
                cell.alignment = left_align

    # Column Widths
    col_widths = [45, 45, 20, 50, 16, 25, 25, 25]
    for i, w in enumerate(col_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(i)
        ws1.column_dimensions[col_letter].width = w

    # ---------------- Sheet 2: คู่มือการใช้งาน (Instructions) ----------------
    ws2 = wb.create_sheet(title="คำแนะนำการกรอกข้อมูล")
    ws2.views.sheetView[0].showGridLines = True
    
    instructions = [
        ["คู่มือการใช้งานไฟล์ Excel สำหรับนำเข้าสินค้า Shopee Affiliate", ""],
        ["", ""],
        ["หัวข้อ", "คำอธิบาย"],
        ["1. ชื่อสินค้า (จำเป็น)", "กรอกชื่อสินค้าภาษาไทยที่ต้องการให้แสดงบนคลิปและให้ AI เขียนบทพากย์"],
        ["2. ลิงก์ Shopee / Affiliate (จำเป็น)", "สามารถใส่ลิงก์ Affiliate ย่อ (เช่น https://s.shopee.co.th/xxx) หรือลิงก์เต็มของ Shopee ได้ ระบบจะดึงรูปจริง 1024x1024 ให้อัตโนมัติ"],
        ["3. หมวดหมู่สินค้า", "ระบุหมวดหมู่เพื่อการจัดกลุ่ม เช่น beauty (บิวตี้), home (ของใช้ในบ้าน), electronics (ไอที), fashion (แฟชั่น) หรือ general (ทั่วไป)"],
        ["4. จุดเด่นสินค้า", "หากเว้นว่างไว้ AI (Gemini Vision) จะดูรูปสินค้าแล้ววิเคราะห์หาจุดเด่นและเขียนบทพากย์ให้เอง 100%"],
        ["5. ค่าคอมมิชชัน %", "ระบุ % ค่าคอมมิชชันเพื่อช่วยจดจำ เช่น 20%, 35%"],
        ["6. ลิงก์รูปภาพสำรอง", "หากระบุลิงก์ Shopee ไว้แล้ว ช่องนี้สามารถเว้นว่างได้เลย ระบบจะดูดรูปจาก Shopee ให้เอง"],
        ["", ""],
        ["🚀 ขั้นตอนการนำเข้า:", ""],
        ["1. ดาวน์โหลดไฟล์นี้ไปเปิดใน Microsoft Excel หรือ Google Sheets", ""],
        ["2. กรอกรายการสินค้าที่คุณต้องการทำคลิปทีละแถว (สามารถใส่ได้ 10-100+ แถว)", ""],
        ["3. บันทึกไฟล์ (Save as .xlsx หรือ .csv)", ""],
        ["4. นำไฟล์มาอัปโหลดในระบบ Shopee Affiliate Video Maker", ""],
        ["5. สินค้าทั้งหมดจะถูกนำเข้าสู่ 'สินค้าของฉัน' และติดป้าย '🟡 รอทำคลิป' ทันที พร้อมกดปุ่ม Batch Render ได้ในคลิกเดียว!", ""],
    ]
    
    for r_idx, row in enumerate(instructions, start=1):
        ws2.append(row)
        ws2.row_dimensions[r_idx].height = 24
        for c_idx in range(1, len(row) + 1):
            cell = ws2.cell(row=r_idx, column=c_idx)
            cell.font = data_font
            cell.alignment = left_align
            if r_idx == 1:
                cell.font = Font(name="Tahoma", size=14, bold=True, color="EE4D2D")
            elif r_idx == 3:
                cell.font = Font(name="Tahoma", size=11, bold=True, color="0F172A")
                cell.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
            elif row[0].startswith("🚀"):
                cell.font = Font(name="Tahoma", size=12, bold=True, color="0F172A")

    ws2.column_dimensions["A"].width = 35
    ws2.column_dimensions["B"].width = 85

    wb.save(xlsx_path)
    print(f"✅ สร้างไฟล์ Excel สำเร็จ: {xlsx_path}")
    
    # สร้างเวอร์ชัน .CSV สำหรับคนที่สะดวกใช้ CSV
    import csv
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(samples)
    print(f"✅ สร้างไฟล์ CSV สำเร็จ: {csv_path}")


def parse_and_import_excel(file_path: str, auto_fetch_images: bool = True) -> dict:
    """
    อ่านไฟล์ Excel (.xlsx) หรือ CSV แล้วนำเข้าสินค้าเข้าสู่ 'สินค้าของฉัน' (My Products)
    พร้อมติดสถานะ 'รอทำคลิป' อัตโนมัติ

    Args:
        file_path: path ไฟล์ .xlsx หรือ .csv
        auto_fetch_images: หากสินค้าไม่มีรูปภาพให้พยายามดึงรูปจริงจาก Shopee อัตโนมัติ

    Returns:
        dict: สรุปผลการนำเข้า { success, imported_count, skipped_count, products, errors }
    """
    import csv
    from src.catalog_manager import CatalogManager
    from src.shopee_extractor import extract_shopee_product_direct

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์: {file_path}")

    rows = []
    ext = path.suffix.lower()

    if ext == ".xlsx":
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            if row and any(row):
                rows.append([str(c).strip() if c is not None else "" for c in row])
    elif ext in [".csv", ".txt"]:
        # ลองอ่านแบบ utf-8-sig ก่อน ถ้าไม่ได้ลอง cp874 (Windows Thai)
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = [r for r in reader if r and any(r)]
        except UnicodeDecodeError:
            with open(path, "r", encoding="cp874") as f:
                reader = csv.reader(f)
                rows = [r for r in reader if r and any(r)]
    else:
        raise ValueError("รองรับเฉพาะไฟล์นามสกุล .xlsx หรือ .csv เท่านั้น")

    if not rows or len(rows) < 2:
        return {
            "success": False,
            "message": "ไฟล์ไม่มีข้อมูลสินค้า (ต้องมีแถวหัวตารางและข้อมูลอย่างน้อย 1 แถว)",
            "imported_count": 0,
            "skipped_count": 0,
            "products": []
        }

    # ข้าม Header แถวแรก
    data_rows = rows[1:]
    catalog_mgr = CatalogManager()
    imported_products = []
    skipped_count = 0
    errors = []

    for idx, r in enumerate(data_rows, start=2):
        name = r[0].strip() if len(r) > 0 else ""
        url = r[1].strip() if len(r) > 1 else ""
        category = r[2].strip() if len(r) > 2 else "general"
        highlight = r[3].strip() if len(r) > 3 else ""
        commission = r[4].strip() if len(r) > 4 else "25%"

        # อ่านรูปภาพเพิ่มเติม
        images = []
        for c_idx in [5, 6, 7]:
            if len(r) > c_idx and r[c_idx].strip():
                images.append(r[c_idx].strip())

        # ตรวจสอบความถูกต้องเบื้องต้น
        if not name and not url:
            skipped_count += 1
            continue

        if not name:
            name = f"สินค้า Shopee นำเข้า #{idx}"

        # ถ้าไม่มีรูปภาพ แต่มีลิงก์ Shopee และเปิด auto_fetch_images ไว้
        if not images and url and auto_fetch_images and ("shopee.co.th" in url or "shope.ee" in url):
            try:
                extracted = extract_shopee_product_direct(url)
                if extracted.get("local_images"):
                    images = extracted["local_images"]
                elif extracted.get("cdn_urls"):
                    images = extracted["cdn_urls"]
                if extracted.get("name") and name.startswith("สินค้า Shopee นำเข้า"):
                    name = extracted["name"]
            except Exception as e:
                errors.append(f"แถวที่ {idx}: ไม่สามารถดึงรูปภาพจากลิงก์ได้ ({e})")

        product_payload = {
            "name": name,
            "affiliate_link": url,
            "category": category if category else "general",
            "highlight": highlight if highlight else "สินค้าแนะนำคุณภาพดี สั่งซื้อในตะกร้าส้มได้เลย",
            "commission_rate": commission if commission else "25%",
            "commission_badge": f"Extra Comm {commission}" if commission else "25% ค่าคอม",
            "shop_type": "Shopee",
            "images": images,
            "rating": 4.9,
            "sold_count": 10000,
        }

        try:
            saved = catalog_mgr.add_my_product(product_payload)
            imported_products.append(saved)
        except Exception as e:
            skipped_count += 1
            errors.append(f"แถวที่ {idx}: บันทึกข้อมูลล้มเหลว ({e})")

    return {
        "success": True,
        "message": f"นำเข้าสินค้าจากไฟล์สำเร็จ {len(imported_products)} รายการ (ข้าม {skipped_count} รายการ)",
        "imported_count": len(imported_products),
        "skipped_count": skipped_count,
        "products": imported_products,
        "errors": errors
    }


if __name__ == "__main__":
    create_excel_template()
