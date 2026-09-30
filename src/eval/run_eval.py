import json
import sys
from pathlib import Path
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.ingestion.pdf_parser import PDFParser
from src.ingestion.chunker import SemanticChunker
from src.ingestion.schemas import DocumentMetadata
from src.retrieval.embedder import LocalSentenceTransformerEmbedder
from src.retrieval.vector_store import QdrantVectorStore
from src.generation.generator import ComplianceAnswerGenerator

DATA_DIR = Path("data/sample_docs")
MANIFEST_PATH = DATA_DIR / "manifest.json"
EVAL_SET_PATH = Path("data/eval_set.json")
EMBEDDING_DIM = 1024


@dataclass
class EvalResult:
    question_id: str
    question: str
    retrieval_hit: bool          
    citation_correct: bool | None 
    answer: str
    expected_answer: str | None
    notes: str = ""


def setup_pipeline() -> tuple[LocalSentenceTransformerEmbedder, QdrantVectorStore, ComplianceAnswerGenerator]:
    """Ingest เอกสารทั้งหมดเข้า Qdrant แล้วคืน component ที่พร้อมใช้ (เหมือน demo.py)"""
    embedder = LocalSentenceTransformerEmbedder()
    store = QdrantVectorStore()
    store.create_collection_if_not_exists(vector_size=EMBEDDING_DIM)

    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    chunker = SemanticChunker()
    all_chunks = []
    for entry in manifest:
        if not entry.get("downloaded"):
            continue
        file_path = DATA_DIR / entry["filename"]
        if not file_path.exists():
            continue

        metadata = DocumentMetadata(
            document_id=file_path.stem,
            title=entry.get("title", file_path.stem),
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

    store.upsert_chunks(all_chunks)
    generator = ComplianceAnswerGenerator()
    return embedder, store, generator


def check_retrieval_hit(expected_source: dict | None, retrieved_chunks: list[dict]) -> bool:
    """เช็คว่า chunk ที่ retrieve มา มีอันไหนมาจาก document ที่ ground truth คาดหวังไหม"""
    if expected_source is None:
        return True

    expected_doc = expected_source["document"].replace(".pdf", "")
    return any(
        c["payload"]["document_id"] == expected_doc for c in retrieved_chunks
    )


def check_citation_correct(expected_source: dict | None, sources: dict) -> bool | None:
    """เช็คว่า citation ที่ generator ตอบมา อ้างอิง document ที่ถูกต้องไหม"""
    if expected_source is None:
        return None 

    expected_doc = expected_source["document"].replace(".pdf", "")
    return any(src["document_id"] == expected_doc for src in sources.values())


def run_eval():
    print("=== Compliance RAG Assistant — Evaluation Harness ===\n")
    print("กำลังเตรียม pipeline (ingest เอกสาร)...")
    embedder, store, generator = setup_pipeline()

    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        eval_set = json.load(f)

    print(f"เจอคำถามทั้งหมด {len(eval_set)} ข้อ เริ่มรัน...\n")

    results: list[EvalResult] = []
    for item in eval_set:
        qid = item["id"]
        question = item["question"]
        expected_source = item.get("expected_source")

        query_vector = embedder.embed_text(question)
        retrieved = store.search_similar(query_vector, top_k=5)

        retrieval_hit = check_retrieval_hit(expected_source, retrieved)

        gen_result = generator.generate_answer(question=question, retrieved_chunks=retrieved)
        citation_correct = check_citation_correct(expected_source, gen_result["sources"])

        results.append(EvalResult(
            question_id=qid,
            question=question,
            retrieval_hit=retrieval_hit,
            citation_correct=citation_correct,
            answer=gen_result["answer"],
            expected_answer=item.get("expected_answer"),
        ))

        status = "✅" if retrieval_hit else "❌"
        print(f"  [{qid}] retrieval_hit={status}  citation_correct={citation_correct}")

    # --- สรุปผล ---
    total = len(results)
    retrieval_hits = sum(r.retrieval_hit for r in results)
    citation_checks = [r for r in results if r.citation_correct is not None]
    citation_correct_count = sum(r.citation_correct for r in citation_checks)

    print("\n" + "=" * 60)
    print("สรุปผล Evaluation")
    print("=" * 60)
    print(f"Retrieval Hit Rate:     {retrieval_hits}/{total} ({retrieval_hits/total*100:.1f}%)")
    if citation_checks:
        print(f"Citation Correctness:  {citation_correct_count}/{len(citation_checks)} "
              f"({citation_correct_count/len(citation_checks)*100:.1f}%)")

    output_path = Path("data/eval_results.json")
    output_path.write_text(
        json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nรายละเอียดเต็มบันทึกไว้ที่ {output_path}")
    print("\n⚠️  หมายเหตุ: 'Answer Correctness' (เทียบความหมายกับ expected_answer)")
    print("   ยังไม่ได้ทำอัตโนมัติในเวอร์ชันนี้ — ต้องอ่าน data/eval_results.json")
    print("   เทียบด้วยตาก่อน หรือเพิ่ม LLM-as-judge ทีหลัง (ดู TODO ในไฟล์นี้)")

if __name__ == "__main__":
    run_eval()