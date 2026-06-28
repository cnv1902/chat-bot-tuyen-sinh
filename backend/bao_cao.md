# Báo Cáo Kỹ Thuật Toàn Diện: Hệ Thống Backend Chatbot Tuyển Sinh ĐH Vinh

## 1. Tổng quan Kiến trúc Hệ thống

**1.1. Các thành phần chính và vai trò**
Hệ thống backend Chatbot Tuyển sinh ĐH Vinh được thiết kế theo kiến trúc microservices và Agentic RAG. Bao gồm các thành phần:
- **FastAPI Backend (`api/`):** Xử lý REST API, điều phối request từ người dùng, quản lý background task.
- **Agentic RAG (`agent/`):** Sử dụng **LangGraph** để xây dựng luồng suy luận thông minh, định tuyến câu hỏi và quyết định khi nào cần tìm kiếm (search), trả lời (generate) hay từ chối (fallback).
- **Indexing Pipeline (`indexing/`):** Quy trình ETL chuyên sâu chuyển hóa văn bản dạng PDF sang Qdrant vector database. Sử dụng **Gemini Vision** để đọc nội dung ảnh và trích xuất bảng biểu.
- **LLM Module (`llm/`):** Module quản lý giao tiếp với các mô hình ngôn ngữ lớn (LLM). Hỗ trợ linh hoạt nhiều provider như Gemini, Groq, OpenAI, vLLM. Quản lý qua UI (Database).
- **Core Storage (`core/` & `db/`):**
  - **Qdrant:** Vector Database lưu trữ chunk và thực hiện Hybrid Search (Vector similarity + hard filter metadata).
  - **Redis:** Lưu trữ ngữ cảnh/session chat (Session Management) với Optimistic Locking để chống race condition.
  - **PostgreSQL:** Lưu cấu hình LLM (providers, slots) và trạng thái upload file (`uploaded_documents`).
  - **BAAI/bge-m3:** Mô hình Embedding cục bộ xử lý tìm kiếm ngữ nghĩa tiếng Việt.

**1.2. Sơ đồ luồng dữ liệu tổng quát (Data Flow)**
- **User Request** -> `FastAPI /api/chat` -> Sinh/lấy session `Redis` -> Gọi `LangGraph (Agent)` -> Node `Classify` (Phân loại intent) -> Node `Search` (Tìm trên `Qdrant` dùng BAAI/bge-m3 embedding) -> Node `Check` -> Node `Generate / Fallback` (Gọi LLM) -> Update `Redis` -> **Response**.
- **Admin Upload** -> `FastAPI /api/upload` -> `Background Task` -> Chạy OCR PDF thành Image (`pdf2image`) -> Trích xuất dữ liệu bảng biểu/Text bằng `Gemini Vision` -> `Validator` kiểm duyệt Regex -> `Chunking` (Table & Paragraph) -> Encode (`SentenceTransformers`) -> Qdrant lưu trữ UUID.

## 2. Quản lý LLM và Cơ sở dữ liệu

**2.1. Thiết kế Bảng dữ liệu (PostgreSQL)**
- Bảng `providers`: Chứa danh sách các LLM API (gemini, groq, openai, vllm). Trường thông tin: `provider` (PK), `api_key`, `endpoint`, `is_active`.
- Bảng `slots`: Phân luồng các nhiệm vụ cho từng model. Có 2 slot chính: `chat` (dùng cho bot hội thoại) và `ocr` (dùng trong Indexing pipeline lấy text từ ảnh). Trường: `slot` (PK), `provider` (FK), `model_name`.
- Bảng `uploaded_documents`: Lưu lịch sử nạp tài liệu (id, filename, status, message, year) dùng cho giao diện quản trị tiến độ.

**2.2. Cơ chế Multi-Provider (Module `llm/`)**
- Module triển khai pattern đa hình thông qua abstract class `BaseLLMProvider`.
- Mỗi provider implement các hàm `complete`, `complete_json`, `complete_vision`.
- Hệ thống hỗ trợ Groq, Gemini, OpenAI, vLLM. Đối với **vLLM**, có cơ chế bypass chặn User-Agent bằng thư viện `httpx` và gỡ rối (strip) tag `<think>` trả về từ các Reasoning Models.

## 3. Hệ thống Session và Redis

**3.1. Cấu trúc lưu trữ hội thoại**
- Sử dụng Redis làm in-memory store. Khóa lưu trữ dựa trên `session_id` từ client gửi lên.
- Mỗi khóa chứa danh sách các lượt chat (List of dicts: `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]`).
- Chỉ lưu giữ tối đa 20 messages gần nhất (tương đương 10 lượt hội thoại) bằng Python list slicing để tiết kiệm context window.

**3.2. Cơ chế Optimistic Locking (WATCH/MULTI/EXEC)**
- Giải quyết vấn đề Race Condition khi người dùng spam gửi câu hỏi. 
- Tại file `core/session.py`, hàm `save_history` sử dụng Redis `WATCH` khóa `session_id`. Nó đọc lịch sử hiện tại, ghép nối phần lịch sử cũ với nội dung thêm mới, sau đó dùng lệnh `MULTI`/`EXEC` cập nhật lại. Nếu có request đồng thời xen vào làm đổi dữ liệu, transaction sẽ rollback và log retry.

## 4. Pipeline Tiền xử lý Dữ liệu (ETL / Indexing)

**4.1. Quy trình 5 bước (từ file tải lên đến Qdrant)**
1. `pdf_to_images.py`: Dùng `pdf2image` để băm nhỏ PDF thành các trang ảnh JPEG 200dpi.
2. `vision_extractor.py`: Sử dụng provider LLM (thường là Gemini Vision) theo System Prompt đặc thù trích xuất chữ và bảng biểu (Markdown Table) từ ảnh kèm theo JSON metadata tự suy diễn (`year`, `doc_type`, `scope`).
3. `validator.py`: Là chốt chặn. Các rules Regex (giới hạn điểm, mã ngành 7 chữ số) quét dữ liệu do LLM Vision trả về. Dữ liệu sai không bị bỏ mà được cảnh báo vào `needs_review`.
4. `chunker.py`: Băm Markdown. Bảng biểu được băm theo **từng hàng (Table Rows)** -> mỗi hàng trở thành một câu semantic hoàn chỉnh. Văn bản xuôi được giữ nguyên từng đoạn.
5. `indexer.py`: Nhúng qua Embedder cục bộ (`BAAI/bge-m3`) và đẩy sang Qdrant Collection.

**4.2. Vai trò của `validator.py` và cách thức bắt ảo giác (hallucination)**
- Gemini Vision rất mạnh nhưng thi thoảng sinh số liệu không chuẩn. `validator.py` dùng Regex xác nhận:
  - `diem_chuan_range`: Chỉ từ 10.0 -> 30.0.
  - `ma_nganh_7digits`: Phải bắt đúng 7 chữ số.
  - `hoc_phi_range`: Chỉ từ 5 triệu đến 100 triệu VNĐ.
- Không chặn luồng chạy (fail-all strategy), ghi log cảnh báo và xuất danh sách các trang "cần soát lỗi" cho AdminUI.

## 5. Cấu trúc Vector Database và Chiến lược Chunking

**5.1. Qdrant Payload Schema**
Mỗi chunk đẩy vào Qdrant chứa UUIDv5 (đảm bảo tính Idempotent), vector 1024 chiều và cấu trúc metadata (payload) sau:
- `content`: Text tự nhiên.
- `source_file`: Tên tài liệu.
- `year` (int), `doc_type` (str), `scope` (str), `page` (int), `chunk_type` (str), `major`, `major_code`.

**5.2. Semantic Chunking cho Bảng biểu**
- **Vấn đề:** Điểm chuẩn và thông tin ngành học nằm trọn trong Bảng (Table). Nếu chia đoạn văn bản thường, ngữ cảnh sẽ bị mất, LLM bị rối giữa nhiều hàng trong bảng.
- **Giải pháp (`indexing/chunker.py`):** Mỗi hàng trong bảng được gộp các cột (`major`, `code`, `score`, `combo`) thành **một câu có ý nghĩa ngữ nghĩa đầy đủ**. (VD: "Ngành CNTT mã 7480103 có điểm năm 2026 là 24.5"). Nhờ đó, Vector DB truy xuất theo hàng cực kỳ chính xác.

## 6. Embedding Model

**6.1. Tại sao chọn BAAI/bge-m3?**
- Là model nhẹ gọn (dense vector, không cần GPU mạnh) phục vụ multilingual. 
- Hỗ trợ semantic search vượt trội bằng tiếng Việt.
- Chạy cục bộ bằng thư viện `SentenceTransformers`, không tốn chi phí gọi API ra ngoài (không lo rate limit hay tốn credit) cho lượng lớn văn bản.
- Chiều vector (Dimension): 1024.

**6.2. Cơ chế Warmup (`core/embedder.py`)**
- Ở `api/main.py` -> event `startup`, gọi `embedder_warmup()`.
- Force tải Model vào bộ nhớ RAM trước khi ứng dụng sẵn sàng nhận request.
- Điều này khắc phục tình trạng Request API đầu tiên bị nghẽn (lag 5-8 giây do tải mô hình lần đầu).

## 7. LangGraph Workflow (Agentic RAG)

**7.1. Sơ đồ Node và Edge (Chi tiết theo `graph.py` và `nodes.py`)**
- Node `classify_intent` -> Node `search_knowledge` -> Node `check_context`.
- **Conditional Edge:** `route_after_check()` rẽ nhánh tại Node `check_context`:
  - `trigger_generation` -> Node `generate_answer` -> `END`.
  - `retry_search_loop` -> Quay lại `search_knowledge` -> Tăng `iterations`.
  - `trigger_fallback` -> Node `fallback_answer` -> `END`.

**7.2. State Schema (`AdmissionState`)**
State trung tâm của đồ thị gồm:
- INPUT: `session_id`, `user_message`, `history`.
- PHÂN LOẠI: `intents`, `search_queries`, `dynamic_filters`.
- TÌM KIẾM: `relaxed_filters`, `search_results`, `context`.
- KIỂM SOÁT VÒNG LẶP: `iterations` (Tối đa = 3 vòng lặp).
- OUTPUT: `final_answer`.

## 8. Chi tiết các Nodes trong Agent

**8.1. Classify Intent Node**
- Dùng chat provider ép xuất JSON. Prompt cứng cấu trúc: `{"intents": [...], "queries": [...], "filters": {...}}`.
- Đặc trưng mạnh: Function `_extract_json_robust` cung cấp **5 chiến lược (S1-S5)** để cưỡng chế bắt JSON từ raw response của các LLM (Dù LLM trả JSON trần, JSON trong thẻ Markdown, hay JSON bị kẹp rác chữ văn bản).

**8.2. Search Knowledge Node và Cơ chế Retry**
- Gọi `search_admission_info` từ `tools.py` để làm hybrid search Qdrant.
- Gộp các kết quả theo query, **Deduplicate giữ nguyên thứ tự top score** bằng trick `dict.fromkeys`. 
- **Retry Mechanism:**
  - Iteration 0: Dùng đầy đủ `year` + `doc_type` filter.
  - Iteration 1: Thả bộ lọc `doc_type`, chỉ giữ `year`.
  - Iteration 2: Thả hoàn toàn bộ lọc (search rộng không filter).

**8.3. Check Context Node & Rẽ nhánh định tuyến**
- Cập nhật số vòng lặp `iterations`. 
- Hàm `route_after_check()` chịu trách nhiệm định tuyến. Logic ưu tiên:
  - (1) Nếu intent = "other" -> Vào Fallback.
  - (2) Nếu text context lấy ra $\geq$ 40 ký tự -> Đủ context -> Vào Generate.
  - (3) Nếu context < 40 ký tự & `iterations` < 3 -> Trả về Retry (Vòng lại search_knowledge).
  - (4) Nếu HẾT retry -> Trả về Fallback.

**8.4. Generate vs Fallback**
- `Generate`: Ép temperature = 0.0, top_p = 0.1, hệ thống nhắc nhở chatbot tuyệt đối chỉ lấy số liệu từ thẻ `<context>`. Cấu trúc prompt ghép lịch sử chat và context của lượt này. Nếu trả lời lỗi, dùng try-except catch -> rơi vào Fallback message tĩnh.
- `Fallback`: Đưa ra câu nhắc nhở định sẵn "Không tìm thấy dữ liệu..." thay vì để LLM tự chém gió ảo giác.

## 9. Tools và Tính năng hỗ trợ

**9.1. `search_admission_info` (Qdrant Gateway)**
- Mọi truy vấn Qdrant bắt buộc phải chạy ngang hàm này tại `agent/tools.py`.
- Thiết kế nhằm dễ ghi Log trung tâm (field được filter, top K, Score distribution), dễ kiểm thử (Mocking). Lọc kết quả với ngưỡng Score > 0.3.

**9.2. `calculate_eligibility` (Tính toán đỗ/trượt)**
- Hàm pure-function nhận `user_score` và `threshold`.
- Trả về câu văn mẫu "CÓ ĐỦ/CHƯA ĐỦ" rất mạnh mẽ, chặn mọi ngoại lệ type int/float đầu vào. Hiện tại tuy không trực tiếp kích hoạt như Node, nhưng sẵn sàng để dùng trực tiếp cho LLM Function Calling nếu mở rộng.

## 10. FastAPI Routers và Endpoints

**10.1. REST API Cấu trúc (Controllers)**
- `POST /api/chat`: Điểm kết nối chat. Payload gửi Session và user message. Request gọi `admission_graph.invoke()`.
- `POST /api/upload` và `GET /api/upload/documents`: Giao tiếp cổng nghiệp vụ Upload file và track tiến độ Background Tasks của `uploaded_documents`.
- `GET /POST /admin/*`: Quản lý Providers, Slot Chat, Slot OCR, lấy Models bằng API từ xa. Cập nhật settings.
- `GET /health`: Probe System Health Check.

**10.2. Chống Xung đột Event Loop (`asyncio`)**
- Ở Endpoint `/api/chat` và `/api/upload`, LangGraph và Indexing quá trình xử lý I/O + CPU nặng, do vậy chạy `.to_thread()` trong background.
- Nhưng trong luồng đó, LLM provider sử dụng AsyncIO để request API. Vì vậy cần inject Event loop hiện tại vào module (thông qua `_MAIN_LOOP` và module scope `set_main_loop()`), đảm bảo LangGraph vẫn gọi được Provider Async mà không bị lỗi "cannot be called from running loop".

## 11. Xử lý Lỗi và Global Exception

**11.1. Bắt lỗi tại Middleware/Event (Global Exception Handler)**
- Cấu hình tại `api/main.py`: `global_exception_handler` bao trọn `Exception`, trả về 500 error không ném traceback cho client để đảm bảo an ninh (Security Hardening), đồng thời ghi toàn bộ Traceback ra Console phục vụ log.
- `value_error_handler` ném về 400 Bad Request một cách rõ ràng.

**11.2. Tính Graceful Degradation**
- Khi Redis hỏng hóc kết nối, Session History return mảng rỗng `[]` (Graceful Fetch) và hàm `save_history` catch lỗi pass, hệ thống vẫn phục vụ Chatbot (mất lưu session lượt cũ nhưng luồng chính Qdrant/Agent vẫn chạy được). Cực kỳ bền vững.

## 12. Triển khai, Cấu hình môi trường và Lifecycle

**12.1. Lifespan Events**
- Ứng dụng dùng API Lifecycle (`@asynccontextmanager`) khởi chạy Database Table, Warm up BAAI Embedding Model và xác thực Qdrant Collection khi bắt đầu.
- Tự động seed tài khoản LLM mặc định từ `.env` (`_seed_default_llm_config()`).

**12.2. CORS & Port/IP cấu hình**
- Dynamic thông qua `.env` (`CORS_ORIGINS`). 
- Chạy cùng FastAPI chuẩn production. 

## 13. Logging và Giám sát Hệ thống

**13.1. Định dạng File và Console Logs**
- Logging xuất cả Stream (Console) và File (`logs/app.log`) với format datetime chuẩn hóa. 
- Mức log có thể được điều khiển bởi biến môi trường `LOG_LEVEL`.
- Chủ động suppress (đè) noise warning từ các package như `httpx`, `uvicorn`, `qdrant_client`.

**13.2. Endpoint `/health`**
- Endpoint `/health` tuần tự check (1) Redis kết nối, (2) Qdrant collection, (3) Embedding Models chiều vector. 
- Trả về status: "ok" (200), "degraded" (Lỗi thành phần phụ không chặn Request, 200), "error" (Sụp đổ hạ tầng trọng tâm, ném 503 để Load Balancer reject traffic).

## 14. Fix Text / Mojibake trong Indexing

**14.1. Cơ chế `text_utils.py`**
- OCR có thể gây ra text mã hóa đôi UTF-8 gây ra Mojibake (VD: `SÆ° pháº¡m` thay vì `Sư phạm`). Hệ thống `repair_mojibake()` dùng thuật toán heuristic brute-force normalize utf-8, tự động chữa lại văn bản mojibake thành Tiếng Việt chuẩn. Điều này cải thiện Embedding và Semantic Search lên cực cao.

## 15. Kết luận và Mở rộng

Hệ thống được thiết kế cực kỳ hiện đại với cơ chế Agentic LangGraph hoàn hảo cho nhiệm vụ Retrieval-Augmented Generation (RAG). Bằng việc phân tách rõ ràng trách nhiệm Node (Classify/Search/Generate) và sử dụng chiến lược Retry vòng lặp tự thân với Threshold cứng, nó chặn phần lớn các câu trả lời Ảo giác (Hallucination). Kiến trúc Database và cấu hình linh động cho phép thay lõi LLM nóng (vLLM, Groq, OpenAI, Gemini) mà không cần restart server.

**Gợi ý Mở rộng tương lai:**
- Mở rộng Multi-Agent để giải các câu hỏi kết hợp (VD: So sánh 2 ngành nghề - Multi-Search).
- Triển khai Worker Celery thực thi BackgroundTask ở Node ngoài thay vì BackgroundTask tích hợp của FastAPI, giúp scale ETL độc lập.
