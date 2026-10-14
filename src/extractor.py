import cv2
import PyPDF2
import re
import pytesseract
from pathlib import Path


def extract_text_from_image(image_path):
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Gambar tidak dapat dibaca: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Struk SROIE relatif kecil; pembesaran membantu Tesseract membaca karakter.
    enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    full_text = pytesseract.image_to_string(enlarged, config="--oem 3 --psm 4")

    # OCR seluruh struk kadang menggabungkan angka pada baris total. Baca ulang
    # area jumlah di bagian bawah struk dengan mode tata letak yang berbeda.
    height, width = gray.shape
    total_area = gray[
        int(height * 0.603):int(height * 0.726),
        int(width * 0.389):int(width * 0.983),
    ]
    enlarged_total_area = cv2.resize(
        total_area, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC
    )
    total_area_text = pytesseract.image_to_string(
        enlarged_total_area, config="--oem 3 --psm 6"
    )
    return f"{full_text}\n{total_area_text}"


def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    return text


def _parse_amount(raw_amount):
    """Ubah nominal dengan titik/koma desimal menjadi float."""
    amount = re.sub(r"[^\d,.]", "", raw_amount)
    if not amount:
        return None

    if "," in amount and "." in amount:
        # Pemisah yang paling kanan dianggap desimal; yang lain pemisah ribuan.
        decimal_separator = "," if amount.rfind(",") > amount.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        amount = amount.replace(thousands_separator, "")
        amount = amount.replace(decimal_separator, ".")
    elif "," in amount:
        # Pada struk, nilai seperti 33,92 memakai koma sebagai desimal.
        last_group = amount.rsplit(",", 1)[1]
        if len(last_group) in (1, 2):
            amount = amount.replace(",", ".")
        else:
            amount = amount.replace(",", "")
    elif amount.count(".") > 1:
        last_group = amount.rsplit(".", 1)[1]
        if len(last_group) in (1, 2):
            amount = amount.replace(".", "", amount.count(".") - 1)
        else:
            amount = amount.replace(".", "")

    try:
        return float(amount)
    except ValueError:
        return None


def extract_entities(text):
    # SROIE memakai tanggal seperti 25/12/2018 atau 18-11-18.
    date_match = re.search(
        r"(?<!\d)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})(?!\d)", text
    )

    # Dahulukan baris Total; abaikan Subtotal, Rounded Total, dan Total Sales.
    total_lines = []
    for line in text.splitlines():
        normalized_line = line.strip()
        if re.search(r"\btotal\b", normalized_line, re.IGNORECASE):
            excluded_total = re.search(
                r"sub\s*total|rounded\s+total|total\s+sales|total\s+gst",
                normalized_line,
                re.IGNORECASE,
            )
            if excluded_total:
                continue
            total_lines.append(normalized_line)

    amount_pattern = re.compile(
        r"\btotal(?:\s*amount)?\b"
        r"\s*(?:\(?(?:RM|MYR)\)?)?\s*[:;=\-]?"
        r"\s*(?:RM|MYR|Rp|\$)?\s*([\d][\d.,]*)",
        re.IGNORECASE,
    )
    price_matches = [
        match for line in total_lines if (match := amount_pattern.search(line))
    ]
    # Hasil OCR area total ditambahkan di bagian akhir; bila ada, dahulukan.
    price_match = price_matches[-1] if price_matches else None

    # Pertama cari nama berlabel; jika tidak ada, gunakan nama legal perusahaan
    # yang lazim muncul tanpa label pada struk SROIE.
    name_match = re.search(
        r"(?:Name|Kepada|Company|Store)\s*:\s*([^\r\n]+)",
        text,
        re.IGNORECASE,
    )
    if name_match is None:
        company_match = re.search(
            r"^\s*([^\r\n]+?\b(?:SDN\.?\s*BHD\.?|BERHAD|LTD\.?|LIMITED|INC\.?|CORP\.?))\s*$",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
        name = company_match.group(1).strip() if company_match else None
    else:
        name = name_match.group(1).strip()

    return {
        "date": date_match.group(0) if date_match else None,
        "total_price": _parse_amount(price_match.group(1)) if price_match else None,
        "name": name,
    }


# Blok uji sementara: uji OCR gambar, pembacaan PDF, dan ekstraksi entitas.
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    image_path = project_root / "data" / "10Train" / "X00016469612.jpg"
    pdf_path = project_root / "data" / "pdf_test" / "invoice_dummy.pdf"

    print(f"File JPG yang diuji: {image_path}")
    if not image_path.is_file():
        print("File JPG tidak ditemukan. Periksa kembali lokasi data/10Train.")
    else:
        try:
            image_text = extract_text_from_image(str(image_path))
            print("\n=== TEKS OCR GAMBAR ===")
            print(image_text if image_text.strip() else "(OCR tidak menemukan teks.)")
            print("\n=== ENTITAS DARI GAMBAR ===")
            print(extract_entities(image_text))
        except pytesseract.TesseractNotFoundError:
            print(
                "Aplikasi Tesseract tidak ditemukan. Pasang Tesseract dan "
                "pastikan lokasinya dikenali oleh PATH Windows."
            )

    print(f"\nFile PDF yang diuji: {pdf_path}")
    if not pdf_path.is_file():
        print("PDF dummy tidak ditemukan di data/pdf_test.")
    else:
        pdf_text = extract_text_from_pdf(str(pdf_path))
        print("\n=== TEKS HASIL EKSTRAKSI PDF ===")
        print(
            pdf_text
            if pdf_text.strip()
            else "(PDF tidak memiliki teks yang terbaca.)"
        )
        print("\n=== ENTITAS DARI PDF ===")
        print(extract_entities(pdf_text))
