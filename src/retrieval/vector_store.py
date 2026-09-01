from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from src.ingestion.schemas import DocumentChunk

class QdrantVectorStore:
    """Class สำหรับจัดการการเชื่อมต่อ Collection และ Indexing ข้อมูลลง Qdrant Vector DB"""

    def __init__(self, host: str = "localhost", port: int = 6333, collection_name: str = "compliance_docs"):

        self.client = QdrantClient(host=host, port=port, check_compatibility=False)
        self.collection_name = collection_name

    def create_collection_if_not_exists(self, vector_size: int = 1536):
        """สร้าง Collection ใน Qdrant หากยังไม่มี ต้องกำหนด Vector Dimension และ Payload Index"""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="document_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="page_number",
                field_schema=models.PayloadSchemaType.INTEGER,
            )

    def upsert_chunks(self, chunks: List[DocumentChunk]):
        """บันทึก DocumentChunks และ Vector Embeddings ลง Qdrant"""
        points = []
        for idx, chunk in enumerate(chunks):
            if chunk.embedding is None:
                continue

            point = PointStruct(
                id=idx, 
                vector=chunk.embedding,
                payload=chunk.to_qdrant_payload()
            )
            points.append(point)

        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

    def search_similar(
        self, 
        query_vector: List[float], 
        top_k: int = 5, 
        document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """ค้นหา Chunk ที่ใกล้เคียงที่สุด เพื่อรองรับ Metadata"""
        query_filter = None
        if document_id:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )

        search_result = self.client.query_points(
        collection_name=self.collection_name,
        query=query_vector,  
        limit=top_k,
    ).points

        results = []
        for hit in search_result:
            results.append({
                "score": hit.score,
                "payload": hit.payload
            })
        return results