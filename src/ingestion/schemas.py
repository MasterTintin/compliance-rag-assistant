from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

class DocumentMetadata(BaseModel):
    """Metadata สำหรับกำกับเอกสาร Compliance แต่ละฉบับ"""
    model_config = ConfigDict(extra="allow")

    document_id: str = Field(description="Unique ID ของเอกสาร เช่น doc_sec_001")
    title: str = Field(description="ชื่อเอกสาร หรือ ชื่อประกาศกฎระเบียบ")
    source: str = Field(description="ชื่อไฟล์ต้นฉบับ")
    category: str = Field(default="general", description="หมวดหมู่ เช่น compliance, finance")
    effective_date: Optional[str] = Field(default=None, description="วันที่เริ่มมีผลบังคับใช้ (YYYY-MM-DD)")
    version: str = Field(default="1.0", description="เวอร์ชันของเอกสาร")
    publisher: Optional[str] = Field(default=None, description="หน่วยงานผู้ออกประกาศ เช่น ธปท.")

class ChunkMetadata(BaseModel):
    """Metadata ประจำ Chunk เพื่อใช้ทำ Precision Citation"""
    model_config = ConfigDict(extra="allow")

    chunk_id: str = Field(description="Unique ID ของ Chunk")
    document_id: str = Field(description="ID ของเอกสารต้นทางที่ Chunk นี้สังกัดอยู่")
    page_number: int = Field(description="เลขหน้าที่พบข้อมูล")
    section_title: Optional[str] = Field(default=None, description="ชื่อหัวข้อ/มาตรา เช่น มาตรา 12/4")
    chunk_index: int = Field(description="ลำดับของ Chunk ในเอกสาร")
    has_tables: bool = Field(default=False, description="Flag ระบุว่า Chunk นี้มีโครงสร้างตารางหรือไม่")

class Document(BaseModel):
    """Representation ของเอกสารทั้งฉบับที่ถูก Parse แล้ว"""
    metadata: DocumentMetadata
    raw_content: str = Field(description="ข้อความทั้งหมดของเอกสาร")
    tables: List[Dict[str, Any]] = Field(default_factory=list, description="ตารางทั้งหมดที่สกัดได้จากเอกสาร")

class DocumentChunk(BaseModel):
    """Representation ของ Chunk ข้อมูลที่พร้อมนำไปทำ Embedding และใส่ Vector Store"""
    text: str = Field(description="ข้อความใน Chunk ที่ตัดมาแล้ว")
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = Field(default=None, description="Vector Embedding ของข้อความ")

    def to_qdrant_payload(self) -> Dict[str, Any]:
        """แปลง Data ให้กลายเป็น Payload Format สำหรับเซฟลง Qdrant Vector DB"""
        return {
            "text": self.text,
            "chunk_id": self.metadata.chunk_id,
            "document_id": self.metadata.document_id,
            "page_number": self.metadata.page_number,
            "section_title": self.metadata.section_title or "",
            "chunk_index": self.metadata.chunk_index,
            "has_tables": self.metadata.has_tables,
        }