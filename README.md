# Compliance RAG Assistant

> Enterprise Knowledge Assistant สำหรับค้นหาและตอบคำถามจากเอกสารกำกับดูแล (regulatory/compliance
> documents) พร้อม citation ที่ตรวจสอบย้อนกลับได้เสมอ — สร้างขึ้นเพื่อจำลองปัญหาจริงที่ compliance
> officer ในสถาบันการเงินเจอ ไม่ใช่แค่ demo "chat with PDF" ทั่วไป

[![CI](https://github.com/USERNAME/compliance-rag-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/USERNAME/compliance-rag-assistant/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

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

**สถานะตอนนี้:** Retrieval pipeline (ingestion → chunking → embedding → vector search) รันและทดสอบแล้วจริงกับเอกสารตัวอย่าง — ค้นเจอ chunk ที่เกี่ยวข้องถูกต้องตามที่คาดไว้ (ดู log ใน `demo.py`) ส่วน Generation service (`src/generation/generator.py`) เขียนเสร็จและเชื่อมเข้า pipeline เรียบร้อยแล้ว แต่ยังไม่ได้รัน live demo แบบเต็มเพราะติดเรื่อง API credit ชั่วคราว — โค้ดพร้อมรันได้ทันทีเมื่อมี `ANTHROPIC_API_KEY` ที่มีเครดิต

**ตัวอย่าง output ที่คาดหวัง** (ตามรูปแบบที่กำหนดใน system prompt ของ `generator.py` — ยังไม่ใช่ output จริงจากการรัน จะอัปเดตด้วย log จริงเร็วๆ นี้):

```
Q: การดำรงเงินกองทุนของผู้ประกอบธุรกิจฉบับปัจจุบันคือฉบับไหน?

A: ฉบับปัจจุบันคือประกาศ สธ. 64/2563 (ฉบับประมวล) ซึ่งรวมการแก้ไขทั้งหมดไว้เป็นฉบับเดียว [1]
   รวมถึงการแก้ไขล่าสุดตามประกาศ กธ. 30/2567 (ฉบับที่ 4) [2]

   [1] sec_9563s_consolidated.pdf
   [2] sec_10426_amendment4.pdf
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

# 3. รัน infrastructure (Qdrant + Redis)
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
│   ├── ingestion/     
│   ├── retrieval/      
│   ├── generation/      
│   ├── api/             
│   └── eval/            
├── tests/               
├── docs/
│   └── architecture.md  
├── docker/
└── data/sample_docs/    
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

- Generation service ยังไม่ได้รัน live demo แบบเต็ม (ติด API credit ชั่วคราว) — retrieval ทดสอบแล้วจริง โค้ด generation พร้อมรันได้ทันทีเมื่อมีเครดิต
- ยังไม่รองรับเอกสารภาพสแกนคุณภาพต่ำ (ต้องใช้ OCR pipeline เพิ่ม)
- ยังไม่มี role-based access control — v1 นี้สมมติว่าผู้ใช้ทุกคนเข้าถึงเอกสารได้เท่ากัน
- ดู future work เพิ่มเติมใน [`docs/architecture.md`](docs/architecture.md)

## Status

อยู่ระหว่างพัฒนา — ดู progress ได้ที่ [Projects board](https://github.com/USERNAME/compliance-rag-assistant/projects/1)

## License

MIT — ดูรายละเอียดใน [LICENSE](LICENSE)

---

*โปรเจกต์นี้ใช้เอกสารสาธารณะจาก ธปท./ก.ล.ต. เพื่อการศึกษาและทดสอบระบบเท่านั้น
ไม่ใช่ผลิตภัณฑ์ทางการเงินหรือคำแนะนำทางกฎหมายที่ใช้งานจริง*