"""
ดึงเอกสารประกาศ ก.ล.ต. ตัวอย่างสำหรับ Compliance RAG Assistant
เก็บลง data/sample_docs/ พร้อม manifest.json บันทึก metadata ของแต่ละไฟล์
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict

import requests

OUTPUT_DIR = Path("data/sample_docs")
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compliance-rag-assistant data collection script)"
}


@dataclass
class DocSource:
    filename: str
    url: str
    title: str
    issuer: str       
    doc_type: str         
    notes: str

SOURCES: list[DocSource] = [
    DocSource(
        filename="sec_9563s_consolidated.pdf",
        url="https://publish.sec.or.th/nrs/9563s.pdf",
        title="การคำนวณและการรายงานการคำนวณเงินกองทุนของผู้ประกอบธุรกิจ (ฉบับประมวล)",
        issuer="ก.ล.ต.",
        doc_type="consolidated",
        notes="ฉบับรวมการแก้ไขทั้งหมด ใช้เป็น ground truth ของฉบับปัจจุบัน",
    ),
    DocSource(
        filename="sec_10426_amendment4.pdf",
        url="https://publish.sec.or.th/nrs/10426p_r.pdf",
        title="ประกาศ กธ. 30/2567 การดำรงเงินกองทุนของผู้ประกอบธุรกิจ (ฉบับที่ 4)",
        issuer="ก.ล.ต.",
        doc_type="amendment",
        notes="แก้ไข กธ. 26/2563 — ใช้ทดสอบ citation ข้ามฉบับ",
    ),
]


def download_file(source: DocSource) -> bool:
    dest = OUTPUT_DIR / source.filename
    if dest.exists():
        print(f"  [skip] {source.filename} มีอยู่แล้ว")
        return True

    try:
        resp = requests.get(source.url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"  [ok]   {source.filename} ({len(resp.content) // 1024} KB)")
        return True
    except requests.RequestException as e:
        print(f"  [fail] {source.filename} — {e}")
        return False


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"กำลังดึงเอกสาร {len(SOURCES)} ไฟล์ → {OUTPUT_DIR}/\n")

    results = []
    for source in SOURCES:
        ok = download_file(source)
        results.append({**asdict(source), "downloaded": ok})
        time.sleep(1) 

    MANIFEST_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    ok_count = sum(r["downloaded"] for r in results)
    print(f"\nเสร็จแล้ว: {ok_count}/{len(SOURCES)} ไฟล์")
    print(f"Manifest บันทึกไว้ที่ {MANIFEST_PATH}")

    if ok_count < len(SOURCES):
        print(
            "\n  บางไฟล์ดึงไม่ได้ — sec.or.th อาจบล็อก hotlink ตรง "
            "ลองเปิดผ่านหน้าเว็บ sec.or.th ก่อนแล้วดาวน์โหลดด้วยมือแทน"
        )


if __name__ == "__main__":
    main()