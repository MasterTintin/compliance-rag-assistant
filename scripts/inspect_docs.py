
import json
import sys
from pathlib import Path
 
# เพิ่ม root ของโปรเจกต์เข้า sys.path เพื่อให้ import "src.xxx" เจอ
# ไม่ว่าจะรัน script นี้จากโฟลเดอร์ไหนก็ตาม
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
 
from src.ingestion.pdf_parser import PDFParser
from src.ingestion.schemas import DocumentMetadata
 
DATA_DIR = Path("data/sample_docs")
MANIFEST_PATH = DATA_DIR / "manifest.json"
OUTPUT_DIR = Path("data/extracted_text")
 
 
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
 
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
 
    for entry in manifest:
        if not entry.get("downloaded"):
            continue
 
        file_path = DATA_DIR / entry["filename"]
        if not file_path.exists():
            print(f"[skip] ไม่พบไฟล์ {file_path}")
            continue
 
        metadata = DocumentMetadata(
            document_id=file_path.stem,
            title=entry.get("title", file_path.stem),
            source=entry["filename"],
        )
 
        parser = PDFParser(str(file_path))
        document = parser.parse(metadata)
 
        out_path = OUTPUT_DIR / f"{file_path.stem}.txt"
        out_path.write_text(document.raw_content, encoding="utf-8")
        print(f"[ok] {entry['filename']} → {out_path} ({len(document.raw_content)} ตัวอักษร)")
 
 
if __name__ == "__main__":
    main()