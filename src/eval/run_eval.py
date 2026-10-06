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
    answer_correct: bool         
    judge_reason: str            
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
 
 
JUDGE_SYSTEM_PROMPT = """คุณคือ evaluator ที่เชี่ยวชาญด้านกฎหมายการเงิน หน้าที่ของคุณคือตัดสินว่า
"คำตอบที่ระบบให้" ตรงกับ "คำตอบที่ถูกต้อง" หรือไม่ ในเชิงเนื้อหา
 
กฎการตัดสิน:
- ถ้า "คำตอบที่ถูกต้อง" เป็น null (หมายความว่าคำถามนี้ไม่มีคำตอบในเอกสาร) ให้ตรวจว่า
  ระบบปฏิเสธตอบอย่างเหมาะสมหรือไม่ (เช่น บอกว่า "ไม่พบข้อมูล") ถ้าปฏิเสธถูกต้อง = PASS
  ถ้าระบบแต่งคำตอบขึ้นมาเอง = FAIL
- ถ้ามี "คำตอบที่ถูกต้อง" ให้เช็คว่าคำตอบของระบบมีข้อเท็จจริงสำคัญ (ตัวเลข, วันที่, ชื่อ,
  เงื่อนไข) ตรงกับคำตอบที่ถูกต้องหรือไม่ ไม่จำเป็นต้องตรงคำต่อคำหรือครบทุกรายละเอียด
  แต่ข้อเท็จจริงหลักต้องไม่ผิดและไม่ขาดหายจุดสำคัญ
 
ตอบกลับเป็น JSON เท่านั้น รูปแบบ: {"verdict": "PASS" หรือ "FAIL", "reason": "เหตุผลสั้นๆ"}
ห้ามมีข้อความอื่นนอกเหนือจาก JSON"""
 
 
def check_answer_correctness(
    generator: ComplianceAnswerGenerator,
    question: str,
    actual_answer: str,
    expected_answer: str | None,
) -> tuple[bool, str]:
    """ใช้ Claude เป็น judge เทียบคำตอบจริงกับ expected_answer"""
    expected_text = expected_answer if expected_answer else "null (ไม่มีคำตอบ — ระบบควรปฏิเสธตอบ)"
    user_message = (
        f"คำถาม: {question}\n\n"
        f"คำตอบที่ถูกต้อง: {expected_text}\n\n"
        f"คำตอบที่ระบบให้: {actual_answer}\n\n"
        f"ตัดสินว่า PASS หรือ FAIL"
    )
 
    response = generator.client.messages.create(
        model=generator.model,
        max_tokens=200,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    raw_text = "".join(block.text for block in response.content if block.type == "text")
 
    try:
        clean = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(clean)
        return parsed["verdict"] == "PASS", parsed.get("reason", "")
    except (json.JSONDecodeError, KeyError):
        return False, f"judge ตอบไม่เป็น JSON ที่ parse ได้: {raw_text[:100]}"
 
 
def run_eval():
    print("=== Compliance RAG Assistant — Evaluation Harness ===\n")
    print("กำลังเตรียม pipeline (ingest เอกสาร)...")
    embedder, store, generator = setup_pipeline()
 
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        eval_set = json.load(f)
 
    print(f"เจอคำถามทั้งหมด {len(eval_set)} ข้อ เริ่มรัน...\n")
 
    output_path = Path("data/eval_results.json")
    results: list[EvalResult] = []
 
    def save_progress():
        """เซฟผลลัพธ์เท่าที่มีตอนนี้ลงไฟล์ — เรียกทุกครั้งหลังรันแต่ละข้อ
        เพื่อให้ Ctrl+C กลางทางแล้วไม่เสียของเก่า"""
        output_path.write_text(
            json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
 
    try:
        for item in eval_set:
            qid = item["id"]
            question = item["question"]
            expected_source = item.get("expected_source")
 
            query_vector = embedder.embed_text(question)
            retrieved = store.search_similar(query_vector, top_k=5)
 
            retrieval_hit = check_retrieval_hit(expected_source, retrieved)
 
            gen_result = generator.generate_answer(question=question, retrieved_chunks=retrieved)
            citation_correct = check_citation_correct(expected_source, gen_result["sources"])
 
            answer_correct, judge_reason = check_answer_correctness(
                generator=generator,
                question=question,
                actual_answer=gen_result["answer"],
                expected_answer=item.get("expected_answer"),
            )
 
            results.append(EvalResult(
                question_id=qid,
                question=question,
                retrieval_hit=retrieval_hit,
                citation_correct=citation_correct,
                answer_correct=answer_correct,
                judge_reason=judge_reason,
                answer=gen_result["answer"],
                expected_answer=item.get("expected_answer"),
            ))
 
            r_status = "✅" if retrieval_hit else "❌"
            a_status = "✅" if answer_correct else "❌"
            print(f"  [{qid}] retrieval={r_status}  citation={citation_correct}  answer={a_status}")
 
            save_progress()
    except KeyboardInterrupt:
        print(f"\n\n⏸️  หยุดกลางทาง (Ctrl+C) — ทำไปแล้ว {len(results)}/{len(eval_set)} ข้อ จะสรุปผลเท่าที่มีให้ดู")
 
    # --- สรุปผล ---
    total = len(results)
    retrieval_hits = sum(r.retrieval_hit for r in results)
    citation_checks = [r for r in results if r.citation_correct is not None]
    citation_correct_count = sum(r.citation_correct for r in citation_checks)
    answer_correct_count = sum(r.answer_correct for r in results)
 
    print("\n" + "=" * 60)
    print("สรุปผล Evaluation")
    print("=" * 60)
    print(f"Retrieval Hit Rate:     {retrieval_hits}/{total} ({retrieval_hits/total*100:.1f}%)")
    if citation_checks:
        print(f"Citation Correctness:  {citation_correct_count}/{len(citation_checks)} "
              f"({citation_correct_count/len(citation_checks)*100:.1f}%)")
    print(f"Answer Correctness:    {answer_correct_count}/{total} ({answer_correct_count/total*100:.1f}%)")
 
    failed = [r for r in results if not r.answer_correct]
    if failed:
        print(f"\nข้อที่ FAIL ({len(failed)} ข้อ): {', '.join(r.question_id for r in failed)}")
        print("ดูเหตุผลแต่ละข้อได้ใน data/eval_results.json (field judge_reason)")
 
    if total < len(eval_set):
        print(f"\n⚠️  รันไปแล้ว {total}/{len(eval_set)} ข้อเท่านั้น (ยังไม่ครบ)")
    print(f"รายละเอียดเต็มบันทึกไว้ที่ {output_path}")
 
 
if __name__ == "__main__":
    run_eval()