import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # โหลดค่าจาก .env เข้า os.environ ก่อนใช้งานอะไร

from src.ingestion.pdf_parser import PDFParser
from src.ingestion.chunker import SemanticChunker
from src.ingestion.schemas import DocumentMetadata
from src.retrieval.embedder import LocalSentenceTransformerEmbedder
from src.retrieval.vector_store import QdrantVectorStore
from src.generation.generator import ComplianceAnswerGenerator

DATA_DIR = Path("data/sample_docs")
MANIFEST_PATH = DATA_DIR / "manifest.json"
EMBEDDING_DIM = 1024 
def load_manifest() -> list[dict]:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=== Compliance RAG Assistant — Full Pipeline Demo ===\n")

    print("[1/5] โหลด embedding model (BAAI/bge-m3)...")
    embedder = LocalSentenceTransformerEmbedder()

    print("[2/5] เชื่อมต่อ Qdrant...")
    store = QdrantVectorStore()
    store.create_collection_if_not_exists(vector_size=EMBEDDING_DIM)

    print("[3/5] Ingest เอกสารจาก data/sample_docs/ ...")
    manifest = load_manifest()
    chunker = SemanticChunker()

    all_chunks = []
    for entry in manifest:
        if not entry.get("downloaded"):
            continue

        file_path = DATA_DIR / entry["filename"]
        if not file_path.exists():
            print(f"  [skip] ไม่พบไฟล์ {file_path}")
            continue

        doc_id = file_path.stem
        metadata = DocumentMetadata(
            document_id=doc_id,
            title=entry.get("title", doc_id),
            source=entry["filename"],
            publisher=entry.get("issuer"),
        )

        parser = PDFParser(str(file_path))
        document = parser.parse(metadata)
        chunks = chunker.chunk_document(document)

        texts = [c.text for c in chunks]
        embeddings = embedder.embed_documents(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        all_chunks.extend(chunks)
        print(f"  [ok] {entry['filename']} → {len(chunks)} chunks")

    store.upsert_chunks(all_chunks)
    print(f"\n  รวมทั้งหมด {len(all_chunks)} chunks ถูกเก็บเข้า Qdrant แล้ว")

    print("\n[4/5] ทดสอบค้นหา...")
    query = "การดำรงเงินกองทุนของผู้ประกอบธุรกิจฉบับปัจจุบันคือฉบับไหน?"
    print(f'  คำถาม: "{query}"\n')

    query_vector = embedder.embed_text(query)
    results = store.search_similar(query_vector, top_k=3)

    if not results:
        print("  ไม่พบผลลัพธ์ — เช็คว่า upsert_chunks ทำงานสำเร็จหรือไม่")
        return

    for i, r in enumerate(results, start=1):
        payload = r["payload"]
        print(f"  --- chunk ที่ {i} (ความเกี่ยวข้อง = {r['score']:.3f}) ---")
        print(f"  แหล่งที่มา: {payload['document_id']} หน้า {payload['page_number']}")
        snippet = payload["text"][:150].replace("\n", " ")
        print(f"  เนื้อหา: {snippet}...\n")

    print("[5/5] ให้ Claude สรุปคำตอบจาก chunk ที่เจอ...")
    generator = ComplianceAnswerGenerator()
    result = generator.generate_answer(question=query, retrieved_chunks=results)

    print("\n" + "=" * 60)
    print("คำตอบ:")
    print("=" * 60)
    print(result["answer"])
    print("\n--- แหล่งอ้างอิง ---")
    for ref_num, src in result["sources"].items():
        section = f" ({src['section_title']})" if src.get("section_title") else ""
        print(f"  [{ref_num}] {src['document_id']} หน้า {src['page_number']}{section}")


if __name__ == "__main__":
    main()