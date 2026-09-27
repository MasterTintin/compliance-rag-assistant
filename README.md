# Compliance RAG Assistant

> Enterprise Knowledge Assistant สำหรับค้นหาและตอบคำถามจากเอกสารกำกับดูแล (regulatory/compliance
> documents) พร้อม citation ที่ตรวจสอบย้อนกลับได้เสมอ — สร้างขึ้นเพื่อจำลองปัญหาจริงที่ compliance
> officer ในสถาบันการเงินเจอ ไม่ใช่แค่ demo "chat with PDF" ทั่วไป

---

## ทำไมโปรเจกต์นี้ถึงต่างจาก RAG demo ทั่วไป

โปรเจกต์ "chat with your PDF" ส่วนใหญ่หยุดแค่ตอบคำถามได้ แต่ในบริบทงาน compliance/finance
การตอบผิดแบบมั่นใจ (hallucination) มีต้นทุนสูงกว่าการตอบว่า "ไม่พบข้อมูล" มาก โปรเจกต์นี้จึงเน้น 3 เรื่องที่
demo ทั่วไปมักข้าม:

- **Citation ที่ verify ได้จริง** — ทุกคำตอบ trace กลับไปยัง source document + มาตรา/หน้าที่แน่นอน
- **Evaluation framework** — วัด retrieval precision, faithfulness, citation accuracy แบบ automated ไม่ใช่ eyeball เอา
- **Production-ready infra** — caching, observability, containerized, load-tested ไม่ใช่แค่ script รันในเครื่อง

รายละเอียดการออกแบบและ trade-off แต่ละจุด: [`docs/architecture.md`](docs/architecture.md)

## Demo

**ตัวอย่างคำถาม-คำตอบ:**

```
Q: ธนาคารพาณิชย์ต้องดำรงเงินกองทุนขั้นต่ำเท่าไหร่ตามเกณฑ์ Basel III?

A: ตามประกาศ ธปท. ที่ สนส. XX/25XX ธนาคารพาณิชย์ต้องดำรงอัตราส่วนเงินกองทุนชั้นที่ 1
   ที่เป็นส่วนของเจ้าของ (CET1) ไม่ต่ำกว่า 4.5% ของสินทรัพย์เสี่ยง

   ⚠️ นี่คือตัวอย่างเพื่อการทดสอบระบบเท่านั้น ไม่ใช่คำแนะนำทางกฎหมาย โปรดตรวจสอบกับ
   เอกสารต้นฉบับหรือผู้เชี่ยวชาญก่อนนำไปใช้จริง
```

## Architecture

```
Documents → Ingestion Pipeline → Vector DB (Qdrant) → Retrieval → Generation → API
```

ดูรายละเอียดเต็มพร้อม design decisions: [`docs/architecture.md`](docs/architecture.md)

## Tech Stack

| ส่วน | เครื่องมือ |
|---|---|
| Backend API | FastAPI |
| Vector DB | Qdrant |
| Cache | Redis |
| Embedding | multilingual embedding model (รองรับไทย/อังกฤษ) |
| LLM | Claude API |
| Eval | RAGAS-based custom eval harness |
| Infra | Docker, GitHub Actions CI |

## Quickstart

```bash
# 1. Clone repo
git clone https://github.com/USERNAME/compliance-rag-assistant.git
cd compliance-rag-assistant

# 2. ตั้งค่า environment variables
cp .env.example .env
# แก้ .env ใส่ API key ของตัวเอง

# 3. รัน infrastructure
docker compose up -d

# 4. ติดตั้ง dependencies
uv sync   # หรือ poetry install

# 5. Ingest เอกสารตัวอย่าง
uv run python -m src.ingestion.run --source data/sample_docs/

# 6. รัน API
uv run uvicorn src.api.main:app --reload

# 7. ทดสอบ
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "เงินกองทุนขั้นต่ำของธนาคารพาณิชย์คือเท่าไหร่?"}'
```

ดู API docs แบบ interactive ได้ที่ `http://localhost:8000/docs` (FastAPI auto-generated)

## Project Structure

```
├── src/
│   ├── ingestion/      # แปลงเอกสาร → chunks → vector DB
│   ├── retrieval/      # hybrid search + re-ranking
│   ├── generation/      # grounded generation + citation
│   ├── api/             # FastAPI endpoints
│   └── eval/             # evaluation harness
├── tests/               # unit + integration tests
├── docs/
│   └── architecture.md  # design decisions & trade-offs
├── docker/
└── data/sample_docs/    # เอกสารตัวอย่างสำหรับทดสอบ
```

## Evaluation Results

<!-- TODO: ใส่ตารางผลจริงหลังรัน eval harness เสร็จ อย่าปล่อยว่างตอน submit -->

| Metric | Score |
|---|---|
| Retrieval Precision@5 | TBD |
| Answer Faithfulness | TBD |
| Citation Accuracy | TBD |
| Latency (p50 / p99) | TBD |

รายละเอียดวิธีวัดผล: [`docs/architecture.md#4-evaluation-strategy`](docs/architecture.md)

## Known Limitations

- ยังไม่รองรับเอกสารภาพสแกนคุณภาพต่ำ (ต้องใช้ OCR pipeline เพิ่ม)
- ยังไม่มี role-based access control — v1 นี้สมมติว่าผู้ใช้ทุกคนเข้าถึงเอกสารได้เท่ากัน
- ดู future work เพิ่มเติมใน [`docs/architecture.md`](docs/architecture.md)

## Status

อยู่ระหว่างพัฒนา — ดู progress ได้ที่ [Projects board](https://github.com/USERNAME/compliance-rag-assistant/projects/1)

## License

MIT — ดูรายละเอียดใน [LICENSE](LICENSE)

---