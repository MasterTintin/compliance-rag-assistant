# Architecture: Compliance RAG Assistant

> เอกสารนี้อธิบายการออกแบบระบบ Enterprise Knowledge Assistant สำหรับงาน Compliance/Finance

## 1. Problem Statement

Compliance officer และเจ้าหน้าที่กำกับดูแลในสถาบันการเงินต้องค้นหาข้อมูลจากเอกสารกฎระเบียบจำนวนมาก
ซึ่งมีจำนวนหลายร้อยฉบับ อัปเดตบ่อย และมี cross-reference กันเอง 
การค้นหาแบบ keyword search แบบเดิมใช้เวลานานและสามารถมีข้อผิดพลาดในบริบทได้

**เป้าหมาย:** สร้างระบบที่ตอบคำถามจากเอกสารเหล่านี้ได้ พร้อม citation ที่ตรวจสอบย้อนกลับได้เสมอ
และปฏิเสธที่จะตอบเมื่อไม่มั่นใจ (เพราะในบริบท compliance การตอบผิดแบบมั่นใจ
อันตรายกว่าการตอบว่า "ไม่พบข้อมูล")

## 2. System Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
│  Documents   │────▶│  Ingestion   │────▶│  Vector DB   │────▶│  Retrieval  │
│ (PDF/HTML)   │     │   Pipeline   │     │ (Qdrant)     │     │   Service   │
└─────────────┘     └──────────────┘     └─────────────┘     └──────┬──────┘
                                                                       │
┌─────────────┐     ┌──────────────┐     ┌─────────────┐            │
│    User      │◀────│   FastAPI    │◀────│  Generation  │◀───────────┘
│  (Web/API)   │     │   Gateway    │     │   Service    │
└─────────────┘     └──────────────┘     └─────────────┘
                            │
                     ┌──────┴──────┐
                     │  Redis Cache │
                     │  + Logging   │
                     └─────────────┘
```

ระบบแบ่งเป็น 4 ส่วนหลักที่ทำงานอิสระจากกัน (loosely coupled) เพื่อให้ทดสอบและปรับแต่งแยกส่วนได้:

1. **Ingestion Pipeline** — แปลงเอกสารดิบให้เป็น searchable chunks
2. **Retrieval Service** — ค้นหา chunk ที่เกี่ยวข้องกับคำถาม
3. **Generation Service** — สร้างคำตอบพร้อม citation จาก chunk ที่ค้นเจอ
4. **API Gateway** — จัดการ request, caching, logging, rate limiting

## 3. Component Detail

### 3.1 Ingestion Pipeline

**หน้าที่:** รับเอกสาร → parse → chunk → embed → เก็บเข้า vector DB พร้อม metadata

| ขั้นตอน | เครื่องมือ | เหตุผล |
|---|---|---|
| Parsing | `pdfplumber` / `unstructured` | รักษาโครงสร้างตาราง ซึ่งเอกสารกฎหมายมีเยอะ |
| Chunking | Semantic chunking | เอกสารกฎหมายมีหัวข้อ/มาตราชัดเจน การตัดแบบ fixed-size 500 ตัวอักษรจะตัดใจความขาดกลางประโยคได้ |
| Embedding | `text-embedding-3-small` หรือ multilingual model | รองรับเอกสารไทย/อังกฤษปนกัน |
| Metadata | source, page, section, effective_date, version | จำเป็นสำหรับ citation และการจัดการเอกสารที่มีการแก้ไข |

**Design decision — Chunking strategy:**
เลือกใช้ semantic/structure-aware chunking (แบ่งตามหัวข้อ/มาตรา) แทน fixed-size chunking
เพราะเอกสารกำกับดูแลมักอ้างอิงเป็น "มาตรา X วรรค Y" การตัด chunk ให้สอดคล้องกับโครงสร้างจริง
ทำให้ citation แม่นยำกว่า แต่แลกมาด้วย chunk size ที่ไม่สม่ำเสมอ ซึ่งต้องจัดการตอน embedding

**Design decision — Versioning:**
เอกสารกฎระเบียบมีการแก้ไข/ยกเลิกบ่อย จึงเก็บ `version` และ `effective_date` ใน metadata ทุก chunk
และทำ incremental re-index (ไม่ re-index ทั้งหมดทุกครั้ง) เพื่อประหยัด compute cost

### 3.2 Retrieval Service

**หน้าที่:** รับคำถาม → ค้นหา chunk ที่เกี่ยวข้องที่สุด

**Design decision — Hybrid search:**
ใช้ dense retrieval (semantic) ร่วมกับ BM25 (keyword) แทนที่จะใช้ semantic search อย่างเดียว
เพราะเอกสาร compliance มักมีการอ้างอิงเลขมาตรา/ชื่อประกาศเฉพาะเจาะจง ซึ่ง semantic search อย่างเดียว
มักพลาดคำที่เป็น exact match สำคัญๆ (เช่น "ประกาศ ธปท. ที่ สนส. 5/2566")

**Design decision — Re-ranking:**
เพิ่ม re-ranking layer หลัง initial retrieval เพื่อคัดกรอง chunk top-k ให้แม่นยำขึ้นก่อนส่งเข้า LLM
แลกกับ latency ที่เพิ่มขึ้นเล็กน้อย (~100-200ms) ซึ่งยอมรับได้เพราะความแม่นยำสำคัญกว่าความเร็วในบริบทนี้

### 3.3 Generation Service

**หน้าที่:** สร้างคำตอบจาก chunk ที่ retrieve มา พร้อม citation ที่ trace กลับไปยัง source ได้

**Design decision**
Prompt บังคับให้ LLM ตอบจาก context ที่ให้เท่านั้น และต้องระบุ citation (เอกสาร + มาตรา/หน้า)
ทุกประโยคที่เป็นข้อเท็จจริง หากไม่มี context ที่เกี่ยวข้องเพียงพอ ระบบต้องตอบว่า "ไม่พบข้อมูลที่เกี่ยวข้อง
ในเอกสารที่มี" แทนการเดา — นี่คือหัวใจของระบบทั้งหมด เพราะการ hallucinate ในบริบท compliance
มีต้นทุนสูงกว่าการตอบไม่ได้มาก

### 3.4 API Gateway & Infrastructure

| องค์ประกอบ | เครื่องมือ | เหตุผล |
|---|---|---|
| API Framework | FastAPI | async support, auto-generated OpenAPI docs |
| Caching | Redis | cache คำถามที่ถามซ้ำบ่อย ลด cost/latency |
| Logging/Tracing | OpenTelemetry | ตรวจสอบได้ว่าคำตอบไหนดึงจาก chunk ไหน (audit trail) |
| Containerization | Docker + docker-compose | reproducible environment |

## 4. Evaluation Strategy

ระบบนี้วัดผลด้วย metric 4 ตัว เทียบกับ ground-truth Q&A set:

- **Retrieval Precision/Recall** — chunk ที่ดึงมาเกี่ยวข้องจริงกี่เปอร์เซ็นต์
- **Answer Faithfulness** — คำตอบตรงกับ context ที่ให้จริงหรือไม่
- **Citation Accuracy** — citation ที่อ้างอิงตรงกับแหล่งจริงหรือไม่
- **Latency (p50/p99)** — เวลาตอบสนองภายใต้ load

Regression test รันทุกครั้งที่เปลี่ยน chunking strategy, embedding model หรือ prompt
เพื่อป้องกันไม่ให้การปรับแต่งจุดหนึ่งทำให้จุดอื่นแย่ลงโดยไม่รู้ตัว

## 5. Trade-offs & Known Limitations

| การตัดสินใจ | ข้อดี | ข้อเสีย/ข้อจำกัด |
|---|---|---|
| Semantic chunking | Citation แม่นยำขึ้น | Implementation ซับซ้อนกว่า fixed-size |
| Hybrid search | ครอบคลุมทั้ง exact-match และความหมาย | ต้องดูแล vector + keyword index |
| Re-ranking layer | ความแม่นยำสูงขึ้น | เพิ่ม latency ~100-200ms ต่อ request |
| Self-hosted vector DB | ควบคุมข้อมูลได้เต็มที่ | ต้องดูแล infra เอง ไม่มี managed service ช่วย |