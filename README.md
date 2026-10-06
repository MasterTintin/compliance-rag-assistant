# Compliance RAG Assistant

> Enterprise Knowledge Assistant สำหรับค้นหาและตอบคำถามจากเอกสารกำกับดูแล 
> พร้อม citation ที่ตรวจสอบย้อนกลับได้เสมอ — สร้างขึ้นเพื่อจำลองปัญหาจริงที่ compliance
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

ระบบรันครบ end-to-end จริงแล้ว (ingestion → retrieval → generation) ทดสอบผ่าน `demo.py` และผ่าน evaluation harness เต็มชุด 30 คำถามแล้ว (ดูผลด้านล่าง)

**ตัวอย่าง output จริงจากการรัน `demo.py`:**

```
Q: การดำรงเงินกองทุนของผู้ประกอบธุรกิจฉบับปัจจุบันคือฉบับไหน?

A: ประกาศที่ใช้บังคับในปัจจุบันคือ ประกาศคณะกรรมการกำกับหลักทรัพย์และตลาดหลักทรัพย์
   ที่ กธ. 30/2567 เรื่อง การดำรงเงินกองทุนของผู้ประกอบธุรกิจ (ฉบับที่ 4) [1]

   ประกาศฉบับที่ 4 นี้แก้ไขเพิ่มเติมประกาศแม่ กธ. 26/2563 ลงวันที่ 8 ตุลาคม 2563
   มีผลใช้บังคับตั้งแต่วันที่ 1 พฤศจิกายน 2567 [2]

   [1] sec_10426_amendment4 หน้า 1
   [2] sec_10426_amendment4 หน้า 5 (ข้อ 7)
```

*หมายเหตุ: ตอนทดสอบด้วย ground truth set เจอว่าคำถามแรกที่เขียนไว้ตอนต้น (`q001`) เข้าใจผิดว่า
"การดำรงเงินกองทุน" (กลุ่มประกาศ กธ.) กับ "การคำนวณและการรายงานการคำนวณเงินกองทุน" (กลุ่มประกาศ สธ.)
เป็นเรื่องเดียวกัน — ทั้งที่จริงเป็นคนละกลุ่มประกาศ ระบบตอบถูกต้องตามคำถามจริง แต่ ground truth
เขียนผิด จึงแก้ไข ground truth ให้ตรงกับความเป็นจริงแทน เป็นตัวอย่างที่ดีว่าทำไม evaluation
framework ถึงสำคัญ — มันช่วยจับความเข้าใจผิดได้ แม้จะเป็นความเข้าใจผิดของคนเขียนเองก็ตาม*

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

รันจริงกับ ground truth set ทั้ง 30 คำถาม (`python -m src.eval.run_eval`) — ผลลัพธ์ล่าสุด:

| Metric | Score |
|---|---|
| Retrieval Hit Rate | 29/30 (96.7%) |
| Citation Correctness | 27/28 (96.4%) |
| Answer Correctness (Claude-as-judge) | 16/30 (53.3%) |

**Finding ที่น่าสนใจ:** Answer Correctness แยกตามความยากของคำถามต่างกันชัดเจนมาก —

| ความยาก | ผ่าน |
|---|---|
| Basic | 8/9 (88.9%) |
| Intermediate | 2/7 (28.6%) |
| Advanced | 6/14 (42.9%) |

Retrieval และ Citation แม่นเกือบสมบูรณ์ (>96%) แต่ Answer Correctness ร่วงหนักในคำถามที่ออกแบบมา
ให้ทดสอบ multi-stage deadline, comparative precision และ list completeness — สรุปคือ **ระบบหา context ที่ถูกต้องเจอเกือบทุกครั้ง
แต่ generation ยังพลาดเวลาต้องรวบรวม/เปรียบเทียบรายละเอียดหลายจุดในคำตอบเดียว** นี่คือจุดที่วางแผน
ปรับปรุงต่อ (ดู future work ใน `docs/architecture.md`) ไม่ใช่จุดที่มองข้าม

รายละเอียดวิธีวัดผล: [`docs/architecture.md#4-evaluation-strategy`](docs/architecture.md)

## Known Limitations

- Answer Correctness อยู่ที่ 53.3% โดยเฉพาะคำถามระดับ advanced ที่ต้องเปรียบเทียบ/รวบรวมตัวเลข
  หลายจุด (ดู Evaluation Results ด้านบน) — เป็นจุดที่ยังต้องปรับปรุง prompt หรือเพิ่ม
  re-ranking เพื่อให้ context ที่ส่งเข้า LLM ครบถ้วนกว่านี้
- ยังไม่รองรับเอกสารภาพสแกนคุณภาพต่ำ (ต้องใช้ OCR pipeline เพิ่ม)
- ยังไม่มี role-based access control — v1 นี้สมมติว่าผู้ใช้ทุกคนเข้าถึงเอกสารได้เท่ากัน
- ยังไม่มี FastAPI endpoint ที่ใช้งานจริง (`src/api/` ว่าง) — ตอนนี้ทดสอบผ่าน `demo.py` และ
  `src/eval/run_eval.py` โดยตรง
- ดู future work เพิ่มเติมใน [`docs/architecture.md`](docs/architecture.md)

## Status

🚧 อยู่ระหว่างพัฒนา — ดู progress ได้ที่ [Projects board](https://github.com/USERNAME/compliance-rag-assistant/projects/1)

## License

MIT — ดูรายละเอียดใน [LICENSE](LICENSE)

---

*โปรเจกต์นี้ใช้เอกสารสาธารณะจาก ธปท./ก.ล.ต. เพื่อการศึกษาและทดสอบระบบเท่านั้น
ไม่ใช่ผลิตภัณฑ์ทางการเงินหรือคำแนะนำทางกฎหมายที่ใช้งานจริง*