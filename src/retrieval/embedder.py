from typing import List, Optional
import os
from sentence_transformers import SentenceTransformer

class BaseEmbedder:
    """Base Interface สำหรับ Embedding Engine"""

    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

class LocalSentenceTransformerEmbedder(BaseEmbedder):
    """Local Embedder ใช้ HuggingFace Model เหมาะกับงาน Compliance ที่ประหยัด Cost และต้องการ Privacy"""

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> List[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True, batch_size=32)
        return embeddings.tolist()