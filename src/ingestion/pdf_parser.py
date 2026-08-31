from pathlib import Path
from typing import List, Dict, Any, Optional
import pdfplumber

from src.ingestion.schemas import Document, DocumentMetadata


class PDFParser:
    """PDF Parser ที่สกัดข้อความและแปลงตารางการเงิน ในรูป Markdown Table"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found at: {self.file_path}")

    @staticmethod
    def _table_to_markdown(table: List[List[Optional[str]]]) -> str:
        """แปลง Raw Table ให้กลายเป็น Markdown Table Format"""
        if not table or not table[0]:
            return ""

        cleaned_table = [
            [str(cell).strip().replace("\n", " ") if cell is not None else "" for cell in row]
            for row in table
        ]

        header = cleaned_table[0]
        rows = cleaned_table[1:]

        md_lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * len(header)) + " |"
        ]

        for row in rows:
            md_lines.append("| " + " | ".join(row) + " |")

        return "\n".join(md_lines)

    def parse(self, doc_metadata: DocumentMetadata) -> Document:
        """Parse เอกสาร PDF ทั้งฉบับเพื่อดึงข้อความพร้อมสกัด Metadata"""
        extracted_pages_text: List[str] = []
        all_tables: List[Dict[str, Any]] = []

        with pdfplumber.open(self.file_path) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                page_text_parts: List[str] = []
                
                tables = page.extract_tables()
                page_has_tables = False

                if tables:
                    for t_idx, table in enumerate(tables):
                        md_table = self._table_to_markdown(table)
                        if md_table:
                            page_has_tables = True
                            page_text_parts.append(f"\n[Table {t_idx + 1} on Page {page_idx}]\n{md_table}\n")
                            all_tables.append({
                                "page_number": page_idx,
                                "table_index": t_idx + 1,
                                "markdown": md_table
                            })

                text = page.extract_text()
                if text:
                    page_text_parts.append(text)

                page_content = f"--- Page {page_idx} ---\n" + "\n".join(page_text_parts)
                extracted_pages_text.append(page_content)

        full_raw_content = "\n\n".join(extracted_pages_text)

        return Document(
            metadata=doc_metadata,
            raw_content=full_raw_content,
            tables=all_tables
        )