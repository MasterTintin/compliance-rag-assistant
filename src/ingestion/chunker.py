import re
from typing import List, Optional
from src.ingestion.schemas import Document, DocumentChunk, ChunkMetadata

class SemanticChunker:
    """Structure-Aware Chuner ที่แบ่งข้อความตามโครงสร้างเอกสารและเลขหน้าเพื่อรักษาความหมาย"""

    def __init__(self, target_chunk_size: int = 800, overlap: int = 150):
        self.target_chunk_size = target_chunk_size
        self.overlap = overlap

    def _extract_section_title(self, text: str) -> Optional[str]:
        """ตรวจสอบ pattern ของชื่อหัวข้อหรือเลขมาตราในข้อความ"""
       
        match = re.search(r'(มาตรา\s+\d+|Section\s+\d+(\.\d+)?|ข้อ\s+\d+|Chapter\s+\d+)', text, re.IGNORECASE)
        if match:
            return match.group(0)
        return None
    
    def chunk_document(self, document: Document) -> List[DocumentChunk]:
        """แปลง Document ให้เป็น List ของ DocumentChunk พร้อม Metadata ละเอียด"""
        chunks: List[DocumentChunk] = []
        doc_id = document.metadata.document_id

        pages = document.raw_content.split("--- Page ")
        chunk_idx = 0

        for page_block in pages:
            if not page_block.strip():
                continue

            lines = page_block.strip().split("\n")
            header_line = lines[0]
            
            page_num_match = re.match(r'^(\d+)', header_line)
            page_num = int(page_num_match.group(1)) if page_num_match else 1
            
            page_text = "\n".join(lines[1:]).strip()
            if not page_text:
                continue

            has_table = "[Table " in page_text

            sub_paragraphs = page_text.split("\n\n")
            current_buffer = ""
            current_section = None

            for para in sub_paragraphs:

                found_section = self._extract_section_title(para)
                if found_section:
                    current_section = found_section

                if len(current_buffer) + len(para) <= self.target_chunk_size:
                    current_buffer += ("\n\n" + para if current_buffer else para)
                else:
                    if current_buffer.strip():
                        chunk_idx += 1
                        chunk_id = f"{doc_id}_p{page_num}_c{chunk_idx}"
                        
                        meta = ChunkMetadata(
                            chunk_id=chunk_id,
                            document_id=doc_id,
                            page_number=page_num,
                            section_title=current_section,
                            chunk_index=chunk_idx,
                            has_tables=has_table
                        )
                        chunks.append(DocumentChunk(text=current_buffer.strip(), metadata=meta))

                    current_buffer = para

            if current_buffer.strip():
                chunk_idx += 1
                chunk_id = f"{doc_id}_p{page_num}_c{chunk_idx}"
                meta = ChunkMetadata(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    page_number=page_num,
                    section_title=current_section,
                    chunk_index=chunk_idx,
                    has_tables=has_table
                )
                chunks.append(DocumentChunk(text=current_buffer.strip(), metadata=meta))

        return chunks