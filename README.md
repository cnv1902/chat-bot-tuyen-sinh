# 🎓 Hệ thống Quản lý và Tư vấn Tuyển sinh Đại học (AI-Powered)

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![React](https://img.shields.io/badge/react-18.x-cyan.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.100+-00a393.svg)
![PostgreSQL](https://img.shields.io/badge/postgresql-15+-336791.svg)

Hệ thống quản trị và tư vấn tuyển sinh thông minh dành cho trường Đại học, tích hợp **Chatbot AI (RAG & Handoff)** và bộ công cụ **Admin Dashboard** mạnh mẽ. Hệ thống giúp thí sinh dễ dàng tra cứu thông tin tuyển sinh, đồng thời số hóa hoàn toàn nghiệp vụ nhập liệu, phân quyền và điều phối luồng hỗ trợ trực tuyến của cán bộ tuyển sinh.

---

## 1. 🏗 Tổng quan Hệ thống (System Overview)

Dự án được xây dựng theo kiến trúc Micro-services (monorepo) định hướng Enterprise, tách biệt rõ ràng giữa AI Engine, Backend API và Frontend.

### Tech Stack Chi tiết

- **Backend (API & AI Routing):**
  - **Framework:** FastAPI (High-performance, async-first).
  - **ORM & Database Driver:** SQLAlchemy 2.0 + Asyncpg (PostgreSQL).
  - **Data Processing:** Pandas (Xử lý hàng vạn dòng Excel siêu tốc).
  - **Security:** JWT (JSON Web Tokens) cho API Authentication.
  - **AI Engine:** LangGraph (Định tuyến câu hỏi - AI Router), LangChain.
- **Frontend (Admin Dashboard & Chat Widget):**
  - **Core:** React 18 + Vite (Build tool siêu tốc).
  - **UI/UX Framework:** Ant Design (antd) 5.x.
  - **State Management & Routing:** React Router DOM.
- **Infrastructure & Databases:**
  - **Relational DB:** PostgreSQL (Lưu trữ cấu trúc, hồ sơ, đề án).
  - **Vector DB:** Qdrant (Lưu trữ embeddings để Retrieval-Augmented Generation - RAG).
  - **Caching/Queue:** Redis (Tùy chọn cho Load Balancing & Session).

---

## 2. 🔐 Kiến trúc Xác thực & Phân quyền (Auth & Delegation)

Hệ thống sử dụng **Kiến trúc dữ liệu ủy quyền (Delegated Auth)** giúp mở rộng linh hoạt tệp người dùng:

- **SSO Google OAuth2:** Thí sinh và Cán bộ có thể đăng nhập nhanh 1 chạm thông qua Google. Backend xử lý verify token và ánh xạ vào database nội bộ.
- **Cổng xác thực chung (`accounts`):** Mọi user đều có 1 bản ghi tại bảng `accounts` để quản lý `username`, `password_hash`, và `role`.
- **Móc nối 1-1 (1-to-1 Mapping):** Bảng `accounts` móc nối trực tiếp tới `candidate_profiles` (Hồ sơ thí sinh) hoặc `staff_profiles` (Hồ sơ cán bộ) tùy theo vai trò.

### Hệ thống 4 Roles (RBAC):
1. 🛡️ **`ADMIN`**: Quản trị viên tối cao, toàn quyền cấu hình AI, quản lý danh sách cán bộ.
2. 🏫 **`STAFF_TRUONG`**: Cán bộ cấp trường. Trả lời các câu hỏi chung về quy chế, học phí, ký túc xá.
3. 📚 **`STAFF_NGANH`**: Cán bộ cấp ngành. Trả lời các câu hỏi chuyên sâu về một hoặc nhiều ngành cụ thể. Mảng `major_codes` định nghĩa quyền hạn của họ.
4. 🎓 **`CANDIDATE`**: Thí sinh. Khách hàng sử dụng Chatbot AI và đặt câu hỏi.

---

## 3. 🗄️ Cấu trúc Database (Database Schema)

Database PostgreSQL được chuẩn hóa cao độ, chia làm 3 nhóm chính:

### Nhóm Account (Người dùng & Xác thực)
- `accounts`: Bảng gốc chứa thông tin đăng nhập, phân quyền.
- `candidate_profiles`: Lưu thông tin cá nhân của thí sinh (SĐT, Email, Ngành quan tâm).
- `staff_profiles`: Quản lý nghiệp vụ cán bộ.
  - Chứa cột mảng `major_codes` (danh sách các mã ngành mà cán bộ phụ trách).
  - Chứa cột `current_load` theo dõi số lượng phiên chat đang hỗ trợ (để cân bằng tải).

### Nhóm Cơ cấu Đào tạo (Academic Structure)
- `institutes`: Quản lý các Trường/Viện trực thuộc.
- `majors`: Danh sách ngành đào tạo, liên kết khóa ngoại (Foreign Key) tới `institutes`.
- `admission_codes`: Mã xét tuyển đặc thù (nhiều mã xét tuyển có thể map chung về 1 ngành gốc).

### Nhóm Nghiệp vụ Xét tuyển (Admission Logic)
- `subject_combinations`: Danh mục Khối/Tổ hợp môn (A00, B00, D01...).
- `admission_methods`: Danh mục Phương thức xét tuyển (VD: Xét học bạ, Xét điểm thi THPT).
- `admission_plans`: **Đề án tuyển sinh** (Bảng lõi chứa 15 cột dữ liệu mapping trực tiếp từ Excel như: `mã xét tuyển`, `mã ngành`, `chỉ tiêu`, `tổ hợp`,...).
- `admission_cutoffs`: **Quản lý Điểm Chuẩn** (Tương tự `admission_plans`, mở rộng 15-17 cột để lưu điểm trúng tuyển theo từng năm).

---

## 4. 💻 Chi tiết Chức năng & Menu Admin Dashboard

Admin Dashboard được xây dựng bằng **Ant Design**, mang lại trải nghiệm thao tác dữ liệu (Data-grid) mượt mà như Excel.

✅ **Menu Quản lý Cơ cấu Đào tạo**
- Hỗ trợ Import file Excel cho Trường/Viện và Ngành.
- Thuật toán **Upsert tự động**: Nếu Mã Trường/Ngành đã tồn tại sẽ thực hiện Update, nếu chưa có sẽ tự Insert mới. Tự động khắc phục lỗi Foreign Key khi dữ liệu tham chiếu bị thiếu.

✅ **Menu Quản lý Đề án Tuyển sinh & Mã xét tuyển**
- Giao diện chia Tabs khoa học: Quản lý Tổ hợp, Phương thức, Đề án.
- Tốc độ xử lý Import Excel siêu tốc thông qua thư viện `Pandas`.
- Lưới dữ liệu (Table) được cố định tiêu đề (Fixed Headers) và hỗ trợ cuộn ngang vô cực (Horizontal Scroll) cho các bảng nhiều cột.

✅ **Menu Quản lý Điểm Chuẩn**
- Bảng hiển thị 17 cột dữ liệu chi tiết của từng năm.
- **Excel-like Filtering:** Kế thừa bộ lọc `onFilter` của Ant Design, cho phép Multi-filtering (lọc kết hợp AND logic) trực tiếp trên tiêu đề cột (VD: Lọc `Khối A00` VÀ `Điểm chuẩn > 24`).

✅ **Menu Quản lý Cán bộ**
- Admin có thể tạo tài khoản cán bộ, hệ thống tự động băm mật khẩu bảo mật (Bcrypt).
- Phân bổ quyền hỗ trợ: Gán mảng `major_codes` cho từng cán bộ cấp ngành.

✅ **Menu Quản lý Thí sinh**
- Quản lý danh sách Thí sinh đăng nhập qua hệ thống Google.
- Tính năng Export ra Excel sử dụng cơ chế `StreamingResponse` và `io.BytesIO`, giúp xuất hàng chục ngàn dòng không gây nghẽn RAM máy chủ.

---

## 5. 🤖 Luồng xử lý AI & Handoff (Chatbot Routing)

Tính năng Handoff (Chuyển tiếp cho tư vấn viên) được vận hành hoàn toàn tự động dựa trên đồ thị trạng thái **LangGraph**:

1. **Phân loại Ngữ cảnh (Node Classify):** AI tự động phân tích intent của thí sinh.
2. **Định tuyến (Node 5 - Handoff Router):**
   - 🎯 **Có mã ngành/Tên ngành cụ thể:** Hệ thống quét trong bảng `staff_profiles` để tìm các cán bộ (`STAFF_NGANH`) có `major_codes` khớp với ngành được hỏi.
   - 🏫 **Hỏi thông tin chung chung (Học phí, quy chế):** Định tuyến cuộc gọi tới nhóm cán bộ trường (`STAFF_TRUONG`).
3. **Cân bằng tải (Load Balancing):** Trong trường hợp có nhiều cán bộ cùng thỏa mãn điều kiện, thuật toán sẽ tự động chọn cán bộ đang có `current_load` (số cuộc chat đang tiếp) **thấp nhất** để assign, đảm bảo chất lượng phản hồi nhanh nhất cho thí sinh.

---
*Trân trọng!* 
*Technical Lead - Đội ngũ Phát triển Dự án Tuyển sinh.*
