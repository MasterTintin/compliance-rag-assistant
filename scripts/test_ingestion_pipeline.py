import os
from pathlib import Path

from src.ingestion.schemas import DocumentMetadata
from src.ingestion.pdf_parser import PDFParser
from src.ingestion.chunker import SemanticChunker
from src.retrieval.embedder import LocalSentenceTransformerEmbedder
from src.retrieval.vector_store import QdrantVectorStore


def run_pipeline_test():
    print(" Starting End-to-End Ingestion Pipeline Test...\n")

    sample_pdf_path = Path("data/sample_compliance.pdf")
    
    sample_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    if not sample_pdf_path.exists():
        print(f"⚠️ Warning: File '{sample_pdf_path}' not found.")
        print(" Please place a sample PDF file at 'data/sample_compliance.pdf' to test with real documents.")
        return

    metadata = DocumentMetadata(
        document_id="doc_bot_001",
        title="ประกาศธนาคารแห่งประเทศไทย เรื่อง การกำกับดูแลความเสี่ยง IT",
        source="sample_compliance.pdf",
        category="compliance",
        publisher="ธปท.",
        effective_date="2026-01-01",
        version="1.0"
    )

    print(" [Step 1] Parsing PDF and extracting tables...")
    parser = PDFParser(str(sample_pdf_path))
    document = parser.parse(metadata)
    print(f" ✅ Raw content extracted: {len(document.raw_content)} characters.")

    print(" [Step 2] Splitting text into Semantic Chunks...")
    chunker = SemanticChunker(target_chunk_size=800, overlap=150)
    chunks = chunker.chunk_document(document)
    print(f" ✅ Created {len(chunks)} Document Chunks.")

    print(" [Step 3] Generating Embeddings via bge-m3 model...")
    embedder = LocalSentenceTransformerEmbedder(model_name="BAAI/bge-m3")
    texts = [c.text for c in chunks]
    embeddings = embedder.embed_documents(texts)

    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb

    print("✅ Embeddings generated successfully.")

    print(" [Step 4] Upserting Chunks & Payload into Qdrant Vector DB...")
    vector_store = QdrantVectorStore(host="localhost", port=6333, collection_name="compliance_docs")
    
    vector_store.create_collection_if_not_exists(vector_size=1024)
    vector_store.upsert_chunks(chunks)

    print("\n Pipeline Test Completed Successfully!")
    print("👉 Go check your Qdrant Dashboard at: http://localhost:6333/dashboard\n")


if __name__ == "__main__":
    run_pipeline_test()