"""
Generation Service - รับคำถาม + chunk ที่ retrieve มาได้
แล้วให้ Claude สร้างคำตอบ พร้อม citation ที่ตรวจสอบย้อนกลับได้ ตาม design decision 
ใน docs/architecture.md 
"""

import os
from typing import List, Dict, Any, Optional

import anthropic


SYSTEM_PROMPT = """คุณคือผู้ช่วยตอบคำถามด้าน compliance/finance สำหรับสถาบันการเงิน
กฎเหล็กที่ต้องทำตามทุกครั้ง:
 
1. ตอบจาก "บริบท" ที่ให้มาเท่านั้น ห้ามใช้ความรู้ภายนอกหรือเดา
2. ทุกข้อเท็จจริงที่ตอบ ต้องระบุ citation เป็น [เลขอ้างอิง] ต่อท้ายประโยคเสมอ
   เช่น "ต้องดำรงเงินกองทุนไม่ต่ำกว่า 4.5%"
3. ถ้าบริบทที่ให้มาไม่มีข้อมูลเพียงพอที่จะตอบคำถาม ให้ตอบตรงๆ ว่า
   "ไม่พบข้อมูลที่เกี่ยวข้องในเอกสารที่มี" ห้ามเดาหรือแต่งคำตอบขึ้นมาเอง
4. ตอบเป็นภาษาไทย กระชับ ตรงประเด็น เหมาะกับผู้ใช้งานสาย compliance
"""
 
 
class ComplianceAnswerGenerator:
    """สร้างคำตอบแบบ grounded generation จาก chunk ที่ retrieve มาได้"""
 
    def __init__(self, model: str = "claude-sonnet-4-6", api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = model
 
    @staticmethod
    def _build_context(retrieved_chunks: List[Dict[str, Any]]) -> str:
        """แปลงผลลัพธ์จาก vector_store.search_similar() ให้เป็น context พร้อมเลขอ้างอิง"""
        parts = []
        for i, item in enumerate(retrieved_chunks, start=1):
            payload = item["payload"]
            source_line = f"[{i}] เอกสาร: {payload['document_id']} หน้า {payload['page_number']}"
            if payload.get("section_title"):
                source_line += f" ({payload['section_title']})"
            parts.append(f"{source_line}\n{payload['text']}")
        return "\n\n---\n\n".join(parts)
 
    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        max_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """
        สร้างคำตอบจากคำถาม + chunk ที่เจอ
 
        คืนค่า dict ที่มี:
            - answer: คำตอบที่ Claude สร้าง
            - sources: mapping เลขอ้างอิง → ข้อมูล source จริง (ใช้ทำ footnote ในหน้า UI)
        """
        if not retrieved_chunks:
            return {
                "answer": "ไม่พบข้อมูลที่เกี่ยวข้องในเอกสารที่มี",
                "sources": {},
            }
 
        context = self._build_context(retrieved_chunks)
        user_message = f"บริบทจากเอกสาร:\n\n{context}\n\n---\n\nคำถาม: {question}"
 
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
 
        answer_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
 
        sources = {
            str(i): {
                "document_id": item["payload"]["document_id"],
                "page_number": item["payload"]["page_number"],
                "section_title": item["payload"].get("section_title"),
            }
            for i, item in enumerate(retrieved_chunks, start=1)
        }
 
        return {"answer": answer_text, "sources": sources}