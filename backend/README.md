# 1. Tổng Quan

Hệ thống backend Chatbot Hỗ Trợ Tuyển Sinh Đại Học Vinh là một ứng dụng Agentic RAG thông minh, sử dụng LangGraph để điều phối tác vụ và tích hợp mô hình ngôn ngữ (LLM) để tự động hóa việc trả lời thắc mắc của thí sinh. Hệ thống thiết kế tách biệt luồng Indexing (số hóa dữ liệu PDF thành Vector bằng Gemini Vision và BAAI/bge-m3) và luồng Inference (tư vấn realtime qua FastAPI kết hợp Redis và Qdrant), đảm bảo tính chính xác thông qua cơ chế validator nghiêm ngặt và hybrid search.

**Luồng dữ liệu (Data Flow)**

```text
[Luồng 1 — INDEXING offline]
Tài liệu (PDF/DOCX)
        │
        ▼
   (1. pdf_to_images)  ──► Ảnh JPEG
        │
        ▼
 (2. Gemini Vision)    ──► Nội dung JSON/Markdown thô (Trích xuất text & metadata)
        │
        ▼
   (3. Validator)      ──► Nội dung hợp lệ (Chặn ảo giác, ghi lỗi vào needs_review.json)
        │
        ▼
    (4. Chunker)       ──► Semantic Chunks (Mỗi hàng bảng = 1 câu văn, chia đoạn văn)
        │
        ▼
    (5. Indexer)       ──► PointStructs (Encode vector bằng BAAI/bge-m3 + Content-Hash UUID)
        │
        ▼
[Qdrant Vector Database]

[Luồng 2 — INFERENCE realtime]
User ──► [POST /api/chat] ──► FastAPI ──► LangGraph Agent
                                                │
                                                ▼
                                         (1. classify) Trích xuất Intents & Filters (JSON mode)
                                                │
                                                ▼
 [Qdrant] ◄──(query_points)─── (2. search) Hybrid Search qua QdrantClient
                                                │
                                                ▼
                                          (3. check) Kiểm tra Context đủ chất lượng chưa?
                                                │
                 ┌──────────────────────────────┼───────────────────────────┐
                 ▼                              ▼                           ▼
[trigger_generation] context >= 40 ký tự    [retry_search_loop]         [trigger_fallback] context thiếu, hết lượt
      (4. generate) Sinh câu trả lời        < 40 ký tự, loop < 3        (5. fallback) Trả lời dự phòng
      bằng Claude API/LLM Inference             │                           │
                 │                              │                           │
                 └──────────────────────────────┴───────────────────────────┘
                                                ▼
                                    Lưu Redis History & Trả về Client
```

---

# 2. Yêu Cầu Hệ Thống

* **Python:** 3.11 trở lên
* **Docker & Docker Compose:** Yêu cầu cài đặt để chạy các dịch vụ phụ trợ (Qdrant, Redis)
* **RAM:** Tối thiểu 4GB. Chú ý model nhúng `BAAI/bge-m3` cần khoảng ~2GB RAM để load.
* **Disk:** ~5GB trống (Dành cho Qdrant storage và hệ điều hành Docker).
* **Công cụ bổ sung:** `poppler-utils` (Bắt buộc phải có để chuyển PDF sang ảnh).
* **API Keys:**
  * `GOOGLE_API_KEY`: Bắt buộc, dùng cho quá trình OCR (Gemini Vision) và suy luận LLM theo code cấu hình hiện tại.

---

# 3. Cài Đặt & Khởi Động

## 3.1 Clone & Chuẩn Bị
Clone kho lưu trữ và điều hướng vào thư mục backend.
```bash
git clone <repository_url> chatbot-tuyen-sinh
cd chatbot-tuyen-sinh/backend
```

Cài đặt tiện ích `poppler-utils` (Nếu bạn dùng Linux):
```bash
sudo apt-get update
sudo apt-get install -y poppler-utils
```
*(Trên Windows, hãy tải thư viện poppler và thêm thư mục bin vào PATH)*

## 3.2 Tạo file `.env`
Sao chép template và cấu hình các biến môi trường:
```bash
cp .env.example .env
```

**Danh sách biến môi trường đọc từ code (`os.getenv`):**
| Biến | Bắt buộc | Default | Lấy ở đâu / Mô tả |
|------|----------|---------|-------------------|
| `GOOGLE_API_KEY` | **CÓ** | *(Rỗng)* | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `GEMINI_MODEL` | Không | `gemini-2.5-flash` | Tên model xử lý OCR / Inference theo biến môi trường hiện hành |
| `QDRANT_HOST` | Không | `localhost` | Host chạy Qdrant |
| `QDRANT_PORT` | Không | `6333` | Cổng HTTP của Qdrant |
| `QDRANT_COLLECTION` | Không | `tuyen_sinh_dhv` | Tên collection dữ liệu tuyển sinh |
| `QDRANT_API_KEY` | Không | *(Rỗng)* | Auth Key cho Qdrant (nếu có cấu hình bảo mật) |
| `REDIS_URL` | Không | `redis://localhost:6379` | Đường dẫn kết nối Redis Server |
| `REDIS_DB` | Không | `0` | Database index Redis |
| `SESSION_TTL_SECONDS` | Không | `1800` | Thời gian sống phiên chat trong RAM Redis (giây) |
| `EMBED_MODEL` | Không | `BAAI/bge-m3` | Model sinh vector |
| `EMBED_DIMENSION` | Không | `1024` | Số chiều vector của `BAAI/bge-m3` |
| `EMBED_BATCH_SIZE` | Không | `32` | Cỡ batch khi chạy encode embedding indexing pipeline |
| `EMBED_DEVICE` | Không | `cpu` | Thiết bị chạy model (`cpu` hoặc `cuda`) |
| `API_HOST` | Không | `0.0.0.0` | IP Host chạy FastAPI |
| `API_PORT` | Không | `8000` | Port chạy FastAPI |
| `CORS_ORIGINS` | Không | `http://localhost:3000,http://localhost:5173` | Danh sách frontend origins (cách nhau dấu `,`) |
| `LOG_LEVEL` | Không | `INFO` | Mức log hệ thống (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `TMP_IMAGE_DIR` | Không | `./tmp_images` | Folder giữ JPEG cắt tạm từ Pipeline OCR trong .env |
| `PIPELINE_WORKERS`| Không | `2` | Số Worker xử lý PDF đồng thời trong thư mục cấu hình pipeline |

## 3.3 Khởi Động Docker (Qdrant + Redis)
Chạy container bằng Docker Compose (Đảm bảo daemon Docker đang bật):
```bash
docker-compose up -d
```

## 3.4 Cài Python Dependencies
Khởi tạo môi trường ảo (virtualenv) và cài đặt các thư viện cần thiết:
```bash
python -m venv venv
# Windows: venv\Scripts\activate | Linux: source venv/bin/activate
pip install -r requirements.txt
```

## 3.5 Khởi Động FastAPI
Chạy Backend API Server (sẽ load model BAAI/bge-m3 vào RAM trong giai đoạn khởi động, lần đầu tải khoảng 5-10 giây):
```bash
python api/main.py
# Hoặc chạy thủ công qua uvicorn:
# uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## 3.6 Kiểm Tra Hệ Thống Hoạt Động
Mở terminal khác và test health check API để ping các component:
```bash
curl http://localhost:8000/health
```
**Kết quả mong đợi:** 
Trạng thái `{"status": "ok", "components": {"redis": {"status": "ok", "latency_ms": ...}, "qdrant": {"status": "ok"}, "embedder": {"status": "ok", "model": "BAAI/bge-m3", "dimension": 1024}}}`.

Test Chat API realtime mô phỏng tương tác từ Frontend:
```bash
curl -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Chào bạn, hệ thống hoạt động chưa?"}'
```
**Kết quả mong đợi:** JSON Output chứa `session_id`, `answer` và `sources` không lỗi 500.

---

# 4. Cấu Trúc Thư Mục

Mô tả cho từng file cụ thể trong kiến trúc hệ thống:

```text
chatbot-backend/
├── agent/                       # Toàn bộ logic LangGraph định tuyến câu hỏi và gọi AI
│   ├── edges.py                 # Khai báo cấu trúc đường viền kết nối các node (nếu có tách module)
│   ├── graph.py                 # Compile StateGraph của LangGraph, đăng ký các node, định tuyến điều kiện (conditional edges)
│   ├── nodes.py                 # Khai báo các Node cụ thể (classify_intent, search_knowledge, check_context, generate_answer, fallback_answer)
│   ├── state.py                 # Định nghĩa TypedDict AdmissionState lưu trữ dữ kiện phiên làm việc trung gian (session_id, intents, history)
│   └── tools.py                 # Nơi tập trung cổng kết nối truy vấn Qdrant `search_admission_info` chuyên biệt và các tính năng tính eligibility
├── api/                         # Layer nhận/trả request HTTP REST API qua nền tảng FastAPI
│   ├── main.py                  # Entry point FastAPI tổng, config CORS, Lifespan hook khởi động (warmup model), global exception handlers
│   ├── schemas.py               # Chứa các model cấu trúc Pydantic v2 cho payload request/response (ChatRequest, ChatResponse, ErrorResponse...)
│   └── routers/                 # Nhóm phân vùng các API endpoints để dễ quản lý module
│       ├── chat.py              # Xử lý Endpoint POST /api/chat gọi Redis history và khởi động chu kỳ pipeline LangGraph
│       ├── health.py            # Xử lý Endpoint GET /health báo trạng thái uptime của (Redis, Qdrant, Model)
│       └── upload.py            # Xử lý Endpoint POST /api/upload ghi tạm file và đẩy BackgroundTasks xử lý pipeline ngầm
├── core/                        # Các Utilities cốt lõi và kết nối Infrastructure hệ thống
│   ├── embedder.py              # Singleton thread-safe module để nạp mô hình SentenceTransformer (BAAI/bge-m3) nhúng semantic
│   ├── llm.py                   # Cấu trúc giao tiếp LLM wrapper cấu hình GenAI Model với JSON schema parsing
│   ├── session.py               # Quản lý history qua Redis với cơ chế Optimistic Locking chống Race Conditions
│   └── vectordb.py              # Giao tiếp kho Vector với QdrantClient (hybrid filter, indexing metadata) và setup config
├── indexing/                    # Pipeline (ETL offline) chuyển đổi tài liệu thô PDF thành Semantic Vectors
│   ├── chunker.py               # Biến Regex Markdown table thành Table Chunks độc lập (1 hàng = 1 câu), cắt Text Chunks bằng line feed
│   ├── indexer.py               # Gọi Embedder chuyển Chunks sang Vector, áp thuật toán Content-Hash sinh UUID và đẩy Qdrant
│   ├── pdf_to_images.py         # Sử dụng công cụ pdf2image bóc gỡ PDF thành danh sách các hình ảnh trang tĩnh 200dpi
│   ├── run_pipeline.py          # Command CLI điều phối tổng hòa các script theo 5 chặng quy trình tuần tự liên thông
│   ├── validator.py             # Rule-based Regex kiểm duyệt kỹ để ngăn ảo giác số liệu (fail-all checker, vd điểm chuẩn 10-30)
│   └── vision_extractor.py      # Kết nối Gemini Vision quét và trích xuất cấu trúc Markdown + JSON Metadata ẩn từ ảnh OCR
├── data/                        # Vị trí thư mục hứng các tệp được tải lên từ route upload
├── logs/                        # Nơi lưu trữ nhật ký log chạy runtime ứng dụng theo chuẩn hóa setup main.py
├── tmp_images/                  # Thư mục lưu cache chứa các lát cắt file JPEG tạm trong lúc phân giải PDF
├── .env.example                 # Mẫu file định danh các biến môi trường cấu trúc bảo mật hệ thống
├── docker-compose.yml           # Thiết lập dịch vụ hạ tầng Docker để chạy nền Qdrant DB và Redis server
├── Dockerfile                   # Bản hướng dẫn cài đặt Dockerfile đóng gói riêng backend thành container image
└── requirements.txt             # Khai báo các gói thư viện Python bắt buộc cài đặt cho ứng dụng
```

---

# 5. Chi Tiết Từng Module

## 5.1 Indexing Pipeline (`indexing/`)
Chịu trách nhiệm trích xuất dữ liệu không cấu trúc từ tài liệu tuyển sinh thành dạng cấu trúc Vector để tìm kiếm (ETL). Quy trình bao gồm 6 khái niệm xoay quanh 5 bước xử lý vật lý tuần tự:

1. **Bước 1: PDF → Ảnh** (`pdf_to_images.py`): Input file PDF → Output list các đường dẫn ảnh JPEG độ phân giải 200dpi. Thích hợp để bảo toàn format bảng biểu phức tạp.
2. **Bước 2: OCR Vision → JSON/Markdown** (`vision_extractor.py`): Input file JPEG → Gửi lên LLM Gemini Vision API → Output đối tượng JSON chuẩn (có _extract_json_robust chống wrap lỗi) chứa Metadata (`year`, `doc_type`, `faculty`) và Markdown Table nội dung.
3. **Bước 3: Validator Kiểm Duyệt** (`validator.py`): Input văn bản Markdown thô → Regex deterministic bắt lỗi biên (Điểm chuẩn từ 10-30, Mã ngành phải đủ 7 số, học phí ngưỡng thực...). Output valid/invalid dict. Nếu có lỗi, KHÔNG block luồng mà đổ log record vào file `needs_review.json` ở cuối.
4. **Bước 4: Semantic Chunking** (`chunker.py`): Phân loại Markdown. Output là list các "Semantic Chunks". Đối với Table, cắt theo mỗi hàng ngang biến thành một câu văn mạch lạc. Đối với Đoạn văn, tách linefeed tối thiểu >= 60 ký tự lọc rác.
5. **Bước 5: Encode Embedder** (`indexer.py`): Nạp chuỗi Chunks vào `BAAI/bge-m3` để sinh Vector. Output list dict PointStruct.
6. **Bước 6: Ghi Upsert Qdrant** (`indexer.py` / `vectordb.py`): Input PointStruct có Hash UUID sinh từ SHA-256 nội dung để chống đụng độ và nhân đôi (Duplicate) khi chạy lại quá trình. Upsert mảng vào Qdrant DB.

**Lệnh chạy pipeline thủ công bằng console:**
```bash
python indexing/run_pipeline.py --pdf data/tuyen_sinh_2026.pdf
```
**File `needs_review.json`:** Được hệ thống sinh ra ở thư mục ngoài để giúp người quản trị (admin) truy thu và sửa lỗi thủ công. Khi phát sinh ảo giác từ Vision OCR không qua được chốt chặn Rule-base của `validator.py` (Ví dụ OCR làm mất 1 chữ số trong 7 chữ số mã ngành), trang đó được list vào JSON.

## 5.2 LangGraph Agent (`agent/`)

Sơ đồ đồ thị Agent Graph Routing (ASCII):
```text
  START
    │
    ▼
 [classify]   Node 1: Phân loại ý định, trích xuất bộ Dynamic Filters (JSON schema)
    │
    ▼
 [search]     Node 2: Vector search + Áp Metadata filter cứng lên Qdrant DB
    │
    ▼
 [check]      Node 3: Đếm số vòng lặp iteration & đếm số ký tự Context có được
    │
    ├──── "trigger_generation" ──► [generate] ──► END
    │
    ├──── "retry_search_loop"  ──► [search] (Loop quay đầu - Tối đa 3 lần)
    │
    └──── "trigger_fallback"   ──► [fallback] ──► END
```

* **Điều kiện rẽ nhánh tại Check node (`route_after_check`):**
  - Graph rẽ nhánh sang `"trigger_generation"` hướng tới [generate] nếu chuỗi ngữ cảnh kết quả trả về gom được `>= 40` ký tự (Nghĩa là VectorDB có data thỏa mãn).
  - Graph rẽ nhánh sang `"retry_search_loop"` hướng lại [search] nếu chuỗi context thu về `< 40` ký tự (Trống vắng thông tin) VÀ bộ đếm lượt lặp `iterations < 3`. LLM tự gỡ bỏ filter (Drop year, drop faculty) nới lỏng tìm kiếm lại.
  - Graph rẽ nhánh sang `"trigger_fallback"` hướng tới [fallback] nếu intent phân loại rơi vào `"other"` (Những câu chào hỏi linh tinh/phá bĩnh) HOẶC bộ đếm đã kịch sàn `MAX_SEARCH_ITERATIONS = 3` mà DB vẫn bó tay không trả dữ liệu.
* **AdmissionState:** TypedDict này trung chuyển dòng máu của LangGraph.
  - `session_id` (định danh user), `user_message` (input gốc), `history` (ngữ cảnh chat): Load tại Khởi tạo đồ thị.
  - `intents`, `search_queries`, `dynamic_filters`: Dữ liệu phân loại được điền bổ sung sau bước [classify].
  - `search_results`, `context`: Danh sách kết quả thô và đoạn văn format chuỗi đổ vào Prompt điền bởi [search].
  - `iterations`: Đếm số vòng lặp khống chế Infinite Loop điền bởi [check].
  - `final_answer`: Phản hồi cuối cùng xuất ra từ LLM [generate/fallback].
* **Tại sao chỉ có 1 tool `search_admission_info()`:** Thay vì cung cấp N tools phân mảnh cho LLM tự quyết lúc chạy, dự án dồn luồng gọi Qdrant thành "Single Gateway Tool". Việc này giúp kiểm soát cứng (Deterministic) cách LLM tiếp cận database, log chi tiết quá trình apply filter an toàn và dễ debug luồng Hybrid Search tối thượng.

## 5.3 Core Utilities (`core/`)
* **`llm.py`:** Chứa config giao tiếp Inference Model. Chịu trách nhiệm thiết lập tham số nhiệt độ (`temperature=0.0`) và ép mô hình phải tuân thủ JSON mode `response_mime_type="application/json"` qua hàm đặc biệt `chat_complete_json()` để node [classify] gọi không bị vỡ định dạng parser.
* **`vectordb.py`:** Wrapper cho QdrantClient. Việc sử dụng hàm mới `.query_points()` thay thế cho `.search()` vì phiên bản qdrant-client >= 1.7.0 đã chính thức gạch bỏ (deprecated) hàm cũ. Hàm này map từ dynamic filters vào struct `MatchValue` của Qdrant (Dựa theo `_FILTER_FIELD_TYPES`). Cần thiết lập "Payload Index" để Qdrant duyệt mảng cứng (Hard Filter) siêu nhạy tốc độ.
* **`embedder.py`:** Quản lý SentenceTransformer trong bộ nhớ. Lựa chọn model `BAAI/bge-m3` vì đây là giải pháp State-of-the-art nhỏ gọn (~570MB) cho tác vụ đa ngôn ngữ, rất tương thích với ngữ pháp văn bản Tiếng Việt, xuất ra output tiêu chuẩn dimension là `1024` chiều vector. Đảm bảo Thread-safe Lock khởi tạo singleton một lần.
* **`session.py`:** Lưu các lượt hội thoại lịch sử list dict trong Redis Cache. Quản lý với biến `SESSION_TTL_SECONDS=1800` (30 phút timeout tránh chiếm dụng bộ nhớ ram dài). Key format là `chat:session:{uuid}`. Quy tắc giới hạn chỉ chứa max 20 messages (Tương đương 10 lượt qua lại) chống đẩy tràn Context Window model. Implement cơ chế `WATCH / MULTI / EXEC` (Optimistic locking) để bắt xung đột Race-condition, chặn tình trạng mất dữ liệu history nếu người dùng Spam tin nhắn đồng thời.

## 5.4 REST API (`api/`)

Bảng liệt kê chi tiết các Endpoints cung cấp ra Front-End:

| Method | Path | Mô tả | Request body | Response Payload |
|--------|------|-------|--------------|------------------|
| POST | `/api/chat` | Kích hoạt chu kỳ LangGraph Agent trả lời tư vấn realtime | JSON: `{"session_id": "...", "message": "..."}` | JSON: `{"session_id": "...", "answer": "...", "sources": ["file.pdf"]}` |
| POST | `/api/upload` | Tải lên file PDF và Submit chạy tiến trình ETL ngầm | MultiPart-FormData: `file=<PDF>`, `year=2026` | JSON: `{"message": "File đang được hệ thống xử lý ngầm."}` |
| GET | `/health` | Chẩn đoán Uptime và Latency của Redis, Embedding, Qdrant | None | JSON: `{"status": "ok", "components": {...}}` |

* **Session_id tạo ở đâu:** Do kiến trúc Stateless, `session_id` được quyết định tạo tại Frontend UI lưu ở local storage đẩy lên. Trong trường hợp Payload POST body để trống hoặc Frontend gửi null, hàm `sanitize_session_id` với `default_factory` trong Pydantic Class tại `api/schemas.py` Backend sẽ chủ động khởi tạo chuỗi UUID mới.
* **Trường `sources[]`:** Trả về để Frontend có thể hiển thị hộp thoại pop-up "Tài liệu Tham Khảo/Nguồn Trích Dẫn". Backend xử lý deduplicate giữ nguyên thứ tự Score (Điểm uy tín Vector) bằng mẹo `dict.fromkeys(raw_sources)` để không phá vỡ logic xếp hạng từ DB khi loại trùng lặp mảng.

---

# 6. Biến Môi Trường

Bảng đầy đủ các biến môi trường cấu hình ứng dụng:

| Biến | Bắt buộc | Default | Mô tả | Lấy ở đâu / Chú thích |
|------|----------|---------|-------|-----------|
| `GOOGLE_API_KEY` | Có | *(Trống)* | Khóa xác thực Token cho Google AI Gemini. | Google AI Studio Console |
| `GEMINI_MODEL` | Không | `gemini-2.5-flash`| Mã danh định mô hình thực thi. | Tham chiếu doc Google |
| `QDRANT_HOST` | Không | `localhost` | Địa chỉ Host Container Qdrant Database. | Tùy chỉnh Docker / IP |
| `QDRANT_PORT` | Không | `6333` | Port HTTP API kết nối thư viện qdrant-client. | Mặc định Docker Qdrant |
| `QDRANT_COLLECTION`| Không | `tuyen_sinh_dhv`| Vùng dữ liệu Namespace truy vấn trong Qdrant. | Đặt tự chọn |
| `QDRANT_API_KEY` | Không | *(Trống)* | Mã khóa truy cập Cloud Qdrant (Nếu self-host bỏ qua).| Qdrant Cloud Cluster |
| `REDIS_URL` | Không | `redis://localhost:6379`| Kết nối Cache Pool. | Cấu hình Docker |
| `SESSION_TTL_SECONDS`| Không| `1800` | Số giây thời hạn Timeout trước khi wipe History. | - |
| `REDIS_DB` | Không | `0` | Vùng Redis Table Index cho Pool connection. | - |
| `EMBED_MODEL` | Không | `BAAI/bge-m3` | Tên repo Model HuggingFace dùng để Semantic Encode. | HuggingFace Repo |
| `EMBED_DIMENSION`| Không | `1024` | Size Output vector chiều (Không nên chỉnh tay bừa). | - |
| `EMBED_BATCH_SIZE`| Không | `32` | Size chunks nhồi 1 lần khi Pipeline chạy Encode. | - |
| `EMBED_DEVICE` | Không | `cpu` | Device chạy Model Torch (`cuda` nếu có GPU Vram). | - |
| `API_HOST` | Không | `0.0.0.0` | Địa chỉ IP Bind webserver FastAPI uvicorn. | - |
| `API_PORT` | Không | `8000` | Cổng Publish service FastAPI ra mạng LAN. | - |
| `CORS_ORIGINS` | Không | `http://localhost...`| Whitelist URLs duyệt Origin trình duyệt Frontend. | React App Host |
| `LOG_LEVEL` | Không | `INFO` | Mức log xuất Terminal (`DEBUG`, `INFO`, `ERROR`). | - |
| `TMP_IMAGE_DIR` | Không | `./tmp_images` | Đường dẫn Dump ảnh JPEG trung gian cho Pipeline OCR. | - |
| `PIPELINE_WORKERS`| Không | `2` | Khai báo tùy chọn số Thread chạy Pipeline. | - |

---

# 7. Các Lệnh Thường Dùng

* **Xem logs realtime của Backend:**
```bash
tail -f logs/app.log
# Hoặc xem Docker logs: docker logs -f chatbot_backend
```
* **Restart service cụ thể (Ví dụ Qdrant / LLM FastAPI App):**
```bash
docker-compose restart qdrant
docker-compose restart chatbot_backend
```
* **Xóa và tạo lại Qdrant collection (Để dọn sạch DB rác):**
```bash
curl -X DELETE "http://localhost:6333/collections/tuyen_sinh_dhv"
# Sau đó khởi động lại API để hàm setup_collection() khởi tạo vùng chứa trống
```
* **Kiểm tra số lượng chunks đã lưu Index vào Database:**
```bash
curl http://localhost:6333/collections/tuyen_sinh_dhv
# Tìm và đọc key thông tin JSON "points_count"
```
* **Xóa toàn bộ cache session chat Redis của mọi người:**
```bash
docker exec -it chatbot_redis redis-cli FLUSHDB
```

---

# 8. Troubleshooting

Các hướng dẫn xử lý sự cố thường gặp (Fix lỗi nhanh):

1. **Triệu chứng:** Báo lỗi văng Exception `AttributeError: 'QdrantClient' object has no attribute 'search'` trong màn hình log CLI.
   * **Nguyên nhân:** Phiên bản nâng cấp của package `qdrant-client` >= 1.7.0 đã chính thức xoá bỏ hàm `.search()`.
   * **Fix:** Trong file `core/vectordb.py`, phải sử dụng hàm API thay thế là `.query_points()` tương thích chuẩn mới.

2. **Triệu chứng:** Container khởi động chậm, Request ping /health đầu tiên mất thời gian chờ Timeout lâu (bge-m3 load chậm lần đầu).
   * **Nguyên nhân:** Mô hình Semantic `BAAI/bge-m3` nặng xấp xỉ ~570MB. Lifespan event lúc khởi động Uvicorn gọi `embedder_warmup()` cần chép dữ liệu từ HuggingFace Cache vào Ram hệ thống chạy Thread Inference chậm ở phát súng đầu tiên.
   * **Fix:** Đây là thiết kế chủ đích Warmup. Từ Request chat thứ 2 trở đi sẽ phản hồi nhanh siêu tốc (ms) do RAM đã nạp. Cần kiên nhẫn tầm 5-10 giây ở lúc bật Backend.

3. **Triệu chứng:** Parse JSON hỏng lỗi `[JSON/classify_intent] TẤT CẢ chiến lược parse thất bại.` Output LLM sinh ra là chuỗi bị cắt xén như `{`. (JSON response bị truncate).
   * **Nguyên nhân:** Biến giới hạn sinh độ dài `max_tokens` khai báo trong genAI config quá nhỏ (Ví dụ như 400). Khiến văn bản JSON dài sinh ra bị kẹp lại và chặt đứt ngang.
   * **Fix:** Cần nâng lên `max_tokens=800` hoặc cao hơn ở trong core parameter module `llm.py` hoặc node classify của LangGraph.

4. **Triệu chứng:** Bảng biểu kẻ khung rõ ràng trong PDF mà Log OCR Indexing hiển thị `0 table chunks`.
   * **Nguyên nhân:** Do prompt cấp cho Vision Model (LLM) không đủ nghiêm ngặt, Model sinh ra text miêu tả dạng văn xuôi thay vì cú pháp cấu trúc `Markdown Table` chuẩn `| col | col |`. Parser RegEx trong `chunker.py` đã bị khiếm khuyết không nhận dạng khung Table được.
   * **Fix:** Kiểm tra file `vision_extractor.py`, đảm bảo prompt _VISION_PROMPT luôn nhấn mạnh "chuyển thành Markdown Table chuẩn xác".

5. **Triệu chứng:** Lỗi Socket `ConnectionError... redis://localhost:6379`. Backend Crash API.
   * **Nguyên nhân:** Dịch vụ Redis Cache (Container) chưa khởi động thành công hoặc Firewall host chặn Port nội bộ 6379 giao tiếp.
   * **Fix:** Kiểm tra kĩ lại IP tại biến `REDIS_URL`. Start dịch vụ Redis qua cấu hình Compose: `docker-compose up -d redis`.

6. **Triệu chứng:** Trình duyệt phía Client (Frontend) hiển thị Warning màu đỏ `Blocked by CORS policy` từ backend.
   * **Nguyên nhân:** Khách gọi API bằng Domain không thuộc phạm vi khai báo danh sách WhiteList Middleware CORS.
   * **Fix:** Điều chỉnh biến `CORS_ORIGINS` trong tệp cấu hình `.env` chứa URL chuẩn của website UI (Ví dụ: `http://localhost:5173`). Khởi động lại FastAPI.

---

# 9. Kiến Trúc Quyết Định Kỹ Thuật (Architecture Decision Records)

* **Tại sao hệ thống dùng Gemini Flash cho Indexing, Claude cho Inference (không dùng chung 1 model)?**
  (Trong mô tả hệ thống kết hợp LLMs) *Gemini 1.5/2.5 Flash Vision* là chuyên gia OCR số một với chi phí Token cực rẻ, xuất định dạng siêu mượt JSON/Markdown Bảng từ các trang giấy tờ quét phức tạp. Ngược lại, *Claude 3.5 Sonnet* (Lớp model tư duy Logic) là Inference LLMs hạng nặng sở hữu năng lực lý luận (Reasoning) sâu sắc và khả năng điều hướng tool LangGraph cực kỳ mượt mà, giúp hiểu những câu hỏi vặn vẹo mập mờ từ Học Sinh/Thí Sinh thay vì trả lời vô hồn. 

* **Tại sao LLM tự gán metadata thay vì dùng tên file PDF gốc làm filter Database?**
  Cách đặt tên file (Ví dụ: "QĐ_TS_1102.pdf") có thể vô giá trị mặt ngữ nghĩa. Khi sử dụng Gemini Vision trích tự động `year`, `doc_type`, `faculty` ra từ ruột nội dung từng trang, quá trình nhét vào Payload ở Qdrant tạo ra bộ Lọc Siêu dữ liệu (Metadata filter) rất chính xác. Lúc User hỏi "Năm 2026", Vector DB lọc chặn hoàn toàn rác năm 2026 tạo kết quả Hybrid Search hoàn hảo, giảm thiểu sự nhầm lẫn tài liệu giữa các năm.

* **Tại sao mỗi hàng của Table (Bảng) = 1 Semantic Chunk (không chia cụm theo đoạn bự/trang)?**
  Hiện tượng "Pha loãng Vector". Một bảng điểm chuẩn nếu gộp nguyên cục vào Embedder, vector Output bị trộn thông tin của Khoa Toán, Khoa Lý, Khoa Sinh chung vào 1 nấc tọa độ. Khi thí sinh hỏi điểm chuẩn "Khoa Sinh", mô hình sẽ match với độ dính Cosine thấp. Chia tách cắt mỗi 1 hàng ra ghép lại 1 câu văn độc lập có ý nghĩa đầy đủ (Ví dụ: "Mã 01 điểm chuẩn Khoa Sinh 22 năm 2026") biến câu này thành 1 vector sắc lẹm cực kỳ nhạy bén với Keyword.

* **Tại sao số lượng Max Retry = 3 lần trong vòng lặp LangGraph?**
  Trong kiến trúc RAG, đôi khi Agent LLM bị hoang tưởng tự đẻ ra keyword Search sai. Sau bước Check Context báo fail, Agent có quyền "Viết lại Query nới lỏng Filter". Giới hạn cứng `Max=3` lần ngắt chặn cái bẫy Finite Lặp vô hạn (Infinite Loop Fallback), tiết kiệm Server Load, tối ưu Latency thời gian phản hồi chờ của người chat, đủ kịp thông báo trả lời lịch sự kiểu "Xin lỗi tôi không tìm ra" (Fail-fast strategy).

* **Tại sao cấu hình giữ 20 messages lịch sử (10 vòng lặp) trong Redis Database?**
  Một cuộc Chat Context Window sẽ bị phình to cấp số mũ tiêu tốn nghìn USD API Token nếu giữ nguyên vẹn tiểu sử Chat cả đời. Con số 20 dòng tin (10 User - 10 AI) vừa đủ ngữ cảnh Short-term Memory (Trí nhớ ngắn hạn) để thí sinh hỏi tiếp nối ý "Vậy ngành đó thì sao" vẫn giữ được dòng suy nghĩ logic liền mạch, mà vẫn khống chế triệt để chi phí chạy Token Rate Limit. Mọi tin nhắn trượt Window quá sẽ bị đẩy đi (Trượt FIFO).
