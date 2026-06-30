"""
core/parser_service.py
======================
3-Layer RAG Document Ingestion Pipeline.

Layer 1 — Convert (phân nhánh theo loại file):
  - PDF  → pdfplumber (table-aware) với normalize_merged_cells
  - DOCX/PPTX/TXT → MarkItDown

Layer 2 — Dual-Strategy Chunking:
  - Prose (văn bản) → MarkdownHeaderSplitter + RecursiveCharacterTextSplitter
  - Table (bảng)   → Semantic Row Chunks với "Sticky Header"
                     (mỗi hàng = 1 chunk tự chứa đầy đủ tên cột)

Layer 3 — Context Injection:
  - Mỗi chunk được gắn breadcrumb ngữ cảnh vào đầu nội dung
    [Tài liệu: X | Năm: Y | Loại: Z]
"""
import logging
import re
from pathlib import Path
from typing import Optional

from markitdown import MarkItDown
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from db.connection import AsyncSessionLocal
from db.models import UploadedDocument, DocumentChunk

logger = logging.getLogger(__name__)

# Nhãn thân thiện cho doc_type
DOC_TYPE_LABELS: dict[str, str] = {
    "de_an":        "Đề án tuyển sinh",
    "quy_che":      "Quy chế tuyển sinh",
    "diem_chuan":   "Điểm chuẩn",
    "huong_dan":    "Hướng dẫn tuyển sinh",
    "hoc_phi":      "Học phí",
    "lich_su":      "Lịch sử truyền thống",
    "gioi_thieu":   "Giới thiệu chung",
    "co_so_vat_chat": "Cơ sở vật chất & KTX",
    "thanh_tich":   "Thành tích & Việc làm",
    "doi_song":     "Đời sống sinh viên",
}

# ---------------------------------------------------------------------------
# LAYER 1 — UTILITIES
# ---------------------------------------------------------------------------

def normalize_merged_cells(table_data: list[list]) -> list[list[str]]:
    """
    Chuẩn hóa ô gộp (merged cells) trong bảng 2 chiều.

    pdfplumber trả về None cho các ô bị gộp (rowspan / colspan).
    Thuật toán Forward Fill:
      - Duyệt từng ô theo hàng, theo cột.
      - Nếu ô hiện tại là None/"", lấy giá trị từ ô TRÊN (cùng cột) → xử lý rowspan.
      - Nếu ô trên cũng rỗng, lấy giá trị từ ô TRÁI (cùng hàng) → xử lý colspan.
      - Đảm bảo 100% ô đều có text sau khi xử lý.

    Args:
        table_data: Mảng 2D từ pdfplumber (có thể chứa None).

    Returns:
        Mảng 2D với 100% ô là chuỗi text đầy đủ.
    """
    if not table_data:
        return []

    # Tính số cột tối đa
    max_cols = max(len(row) for row in table_data)

    def clean_cell(c) -> str:
        if c is None:
            return ""
        return str(c).replace("\n", " ").strip()

    # Normalize kích thước: pad hàng thiếu cột + clean text
    normalized: list[list[str]] = []
    for row in table_data:
        cleaned = [clean_cell(c) for c in row]
        # Pad cột còn thiếu
        cleaned += [""] * (max_cols - len(cleaned))
        normalized.append(cleaned)

    rows = len(normalized)
    cols = max_cols

    # Forward Fill theo chiều dọc (Rowspan): ô rỗng lấy giá trị từ ô trên
    for r in range(1, rows):
        for c in range(cols):
            if normalized[r][c] == "":
                normalized[r][c] = normalized[r - 1][c]

    # Forward Fill theo chiều ngang (Colspan): ô rỗng còn lại lấy giá trị từ ô trái
    for r in range(rows):
        for c in range(1, cols):
            if normalized[r][c] == "":
                normalized[r][c] = normalized[r][c - 1]

    return normalized


def _flatten_header_rows(table: list[list[str]], header_row_count: int = 2) -> tuple[list[str], list[list[str]]]:
    """
    Gộp nhiều dòng header thành 1 dòng header phẳng.

    Tài liệu hành chính thường có 2 dòng header (dòng cha + dòng con).
    VD: Dòng 1: ["", "", "", "Mã phương thức", "", "", "", "Mã tổ hợp", ""]
        Dòng 2: ["TT", "Mã", "Tên", "PT1", "PT2", "PT3", "PT4", "TH1", "TH2"]
    → Merged: ["TT", "Mã", "Tên", "Mã phương thức PT1", ..., "Mã tổ hợp TH1", ...]

    Args:
        table: Bảng đã normalize_merged_cells.
        header_row_count: Số dòng đầu là header (mặc định 2).

    Returns:
        (merged_header, data_rows)
    """
    if len(table) <= header_row_count:
        # Không đủ dòng để tách header/data
        return table[0] if table else [], table[1:] if len(table) > 1 else []

    # Gộp các dòng header
    merged_header = []
    header_rows = table[:header_row_count]
    cols = len(header_rows[0])

    for c in range(cols):
        parts = []
        seen = set()
        for r in range(header_row_count):
            val = header_rows[r][c].strip()
            if val and val not in seen:
                parts.append(val)
                seen.add(val)
        merged_header.append(" ".join(parts).strip() if parts else f"Cột {c + 1}")

    data_rows = table[header_row_count:]
    return merged_header, data_rows


# ---------------------------------------------------------------------------
# LAYER 1 — CONVERTERS
# ---------------------------------------------------------------------------

def _convert_pdf_to_parts(file_path: str) -> tuple[str, list[dict]]:
    """
    Convert PDF → (prose_text, tables_list).

    Trả về:
      - prose_text: Toàn bộ văn bản thuần ghép từ các trang (bỏ vùng bảng).
      - tables_list: List các dict {"section": str, "headers": list, "rows": list[list]}.
        Mỗi dict đại diện 1 bảng đã chuẩn hóa, sẵn sàng cho Layer 2 tạo Sticky Chunks.
    """
    import pdfplumber

    prose_parts: list[str] = []
    all_tables: list[dict] = []
    current_section = "Nội dung tài liệu"  # Track section heading hiện tại

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            table_bboxes = [t.bbox for t in tables]

            # --- Text thuần (loại bỏ vùng bảng) ---
            if table_bboxes:
                text_page = page.filter(
                    lambda obj, _bboxes=table_bboxes: not any(
                        obj.get("x0", 0) >= bbox[0] - 2
                        and obj.get("x1", 0) <= bbox[2] + 2
                        and obj.get("top", 0) >= bbox[1] - 2
                        and obj.get("bottom", 0) <= bbox[3] + 2
                        for bbox in _bboxes
                    )
                )
            else:
                text_page = page

            raw_text = text_page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            if raw_text.strip():
                prose_parts.append(raw_text.strip())
                # Tìm heading cuối cùng trên trang để làm section context cho bảng
                # VD: "PHỤ LỤC 1", "I. TRƯỜNG KINH TẾ", "II. KHOA LUẬT"
                heading_matches = re.findall(
                    r'^(?:[IVX]+\.|PHỤ LỤC \d+|CHƯƠNG [IVX\d]+).*$',
                    raw_text,
                    flags=re.MULTILINE,
                )
                if heading_matches:
                    current_section = heading_matches[-1].strip()

            # --- Bảng: chuẩn hóa + lưu riêng ---
            for table in tables:
                raw_rows = table.extract()
                if not raw_rows or len(raw_rows) < 2:
                    continue

                # Bước 1: Chuẩn hóa ô gộp
                normalized = normalize_merged_cells(raw_rows)
                if not normalized:
                    continue

                # Bước 2: Phát hiện số dòng header
                # Heuristic: nếu dòng thứ 2 toàn giá trị con (không có ô rỗng ban đầu) → 1 dòng header
                # Nếu dòng đầu có nhiều ô gộp ngang (colspan) → 2 dòng header
                first_row_orig = [raw_rows[0][c] if c < len(raw_rows[0]) else None for c in range(len(normalized[0]))]
                empty_count_first = sum(1 for c in first_row_orig if c is None or str(c).strip() == "")
                header_row_count = 2 if empty_count_first >= 2 else 1

                headers, data_rows = _flatten_header_rows(normalized, header_row_count)

                # Lọc hàng dữ liệu trống
                data_rows = [r for r in data_rows if any(cell.strip() for cell in r)]
                if not data_rows:
                    continue

                all_tables.append({
                    "section": current_section,
                    "page": page_num,
                    "headers": headers,
                    "rows": data_rows,
                })
                logger.debug(
                    f"[Parser] Trang {page_num}: Bảng '{current_section}' — "
                    f"{len(headers)} cột, {len(data_rows)} hàng dữ liệu."
                )

    prose_text = "\n\n".join(prose_parts)
    return prose_text, all_tables


def _convert_generic_to_markdown(file_path: str) -> str:
    """Dùng MarkItDown cho DOCX, PPTX, TXT, v.v."""
    md = MarkItDown()
    result = md.convert(file_path)
    return result.text_content or ""


# ---------------------------------------------------------------------------
# LAYER 2 — DUAL-STRATEGY CHUNKING
# ---------------------------------------------------------------------------

def normalize_fake_headings(md_content: str) -> str:
    """
    Tiền xử lý văn bản:
    1. Un-escape các ký tự Markdown bị MarkItDown escape một cách an toàn.
    2. Chuyển các dòng in đậm đứng độc lập thành thẻ ### (Header 3).
    """
    if not md_content:
        return ""
        
    # 1. Un-escape an toàn
    # Replace \*\* thành **
    md_content = md_content.replace(r'\*\*', '**')
    
    # Replace \# thành # CHỈ khi nó đứng ở đầu dòng như một Header thực thụ
    md_content = re.sub(r'^(\\#+)\s+', lambda m: m.group(1).replace('\\', '') + ' ', md_content, flags=re.MULTILINE)
    
    # 2. Xử lý "Tiêu đề giả" (Fake headings)
    def replacer(match):
        content = match.group(1).strip()
        if len(content) < 150 and '\n' not in content:
            return f"### {content}"
        return match.group(0)

    # Tìm các dòng chỉ chứa **...** đứng độc lập
    md_content = re.sub(r'^\s*\*\*(.*?)\*\*\s*$', replacer, md_content, flags=re.MULTILINE)
    
    return md_content


def _chunk_prose(
    md_content: str,
    context_header: str,
    year: Optional[int],
    doc_type: str,
    doc_id: int,
) -> list[Document]:
    """
    Cắt văn bản thường với MarkdownHeaderSplitter + RecursiveCharacterTextSplitter.
    Áp dụng Layer 3 Context Injection vào từng chunk.
    """
    # Layer 1: Tiền xử lý (Un-escape & Clean)
    md_content = normalize_fake_headings(md_content)

    # Layer 2 - Cấp 1 (Cắt theo cấu trúc)
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False,
    )
    md_header_splits = markdown_splitter.split_text(md_content)

    # Layer 2 - Cấp 2 (Cắt theo kích thước)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
    )
    final_splits = text_splitter.split_documents(md_header_splits)

    result = []
    for chunk in final_splits:
        # Layer 3: Tiêm Context (Context Injection)
        meta = chunk.metadata
        h1 = meta.get("Header 1")
        h2 = meta.get("Header 2")
        h3 = meta.get("Header 3")
        
        sections = [h for h in [h1, h2, h3] if h]
        section_str = " > ".join(sections)
        
        enriched_context = context_header
        if section_str:
            # context_header có dạng: [Tài liệu: X | Năm: Y | Loại: Z]
            # Mở ngoặc cuối cùng để chèn thêm Mục
            enriched_context = context_header[:-1] + f" | Mục: {section_str}]"
            
        chunk.page_content = f"{enriched_context}\n{chunk.page_content}"
        chunk.metadata.update({
            "year": year,
            "doc_type": doc_type,
            "document_id": doc_id,
            "chunk_type": "prose",
        })
        result.append(chunk)

    return result


def _chunk_tables(
    tables: list[dict],
    context_header: str,
    year: Optional[int],
    doc_type: str,
    doc_id: int,
    filename: str,
) -> list[Document]:
    """
    Tạo Semantic Row Chunks cho bảng (Sticky Header strategy).

    Quy tắc:
    - Bảng nhỏ (< 20 hàng): Giữ nguyên toàn bảng dưới dạng Markdown table.
    - Bảng lớn (≥ 20 hàng): Tạo 1 chunk / hàng dữ liệu, mỗi chunk tự chứa header.
    """
    chunks = []

    for table in tables:
        headers: list[str] = table["headers"]
        rows: list[list[str]] = table["rows"]
        section: str = table.get("section", "")
        page: int = table.get("page", 0)

        # Tạo tiêu đề bảng cho context
        table_title = f"{context_header}\n[Bảng: {section} | Trang {page}]"

        if len(rows) < 20:
            # --- Bảng nhỏ: 1 chunk toàn bảng (Markdown table) ---
            header_row = "| " + " | ".join(headers) + " |"
            separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
            data_rows_md = ["| " + " | ".join(row) + " |" for row in rows]
            table_md = "\n".join([header_row, separator_row] + data_rows_md)

            content = f"{table_title}\n{table_md}"
            chunks.append(Document(
                page_content=content,
                metadata={
                    "year": year,
                    "doc_type": doc_type,
                    "document_id": doc_id,
                    "chunk_type": "table_full",
                    "source_section": section,
                    "source_page": page,
                    "source_file": filename,
                }
            ))
        else:
            # --- Bảng lớn: 1 chunk / hàng (Sticky Header) ---
            # Nhóm theo section header bên trong bảng (VD: "I. TRƯỜNG KINH TẾ")
            current_group = section
            group_rows: list[Document] = []

            for row in rows:
                # Phát hiện hàng tiêu đề nhóm trong bảng
                # Hàng chỉ có 1 ô có giá trị, hoặc khớp pattern "I. ...", "II. ..."
                non_empty = [c for c in row if c.strip()]
                is_group_header = (
                    len(non_empty) == 1 and len(non_empty[0]) > 3
                ) or bool(re.match(r'^[IVX]+\.\s+', row[0].strip()))

                if is_group_header:
                    current_group = " ".join(non_empty)
                    continue

                # Tạo "Header: Value" string cho hàng dữ liệu
                row_parts = []
                for h, v in zip(headers, row):
                    if v.strip():  # Bỏ qua cell rỗng
                        row_parts.append(f"{h}: {v}")

                if not row_parts:
                    continue

                row_text = " | ".join(row_parts)
                content = (
                    f"{table_title}\n"
                    f"[Nhóm: {current_group}]\n"
                    f"{row_text}"
                )

                chunks.append(Document(
                    page_content=content,
                    metadata={
                        "year": year,
                        "doc_type": doc_type,
                        "document_id": doc_id,
                        "chunk_type": "table_row",
                        "source_section": current_group,
                        "source_page": page,
                        "source_file": filename,
                    }
                ))

    return chunks


# ---------------------------------------------------------------------------
# LAYER 3 — CONTEXT INJECTION (helper)
# ---------------------------------------------------------------------------

def _build_context_header(filename: str, year: Optional[int], doc_type: str) -> str:
    """Tạo breadcrumb ngữ cảnh gắn đầu mỗi chunk."""
    label = DOC_TYPE_LABELS.get(doc_type, doc_type)
    year_str = str(year) if year else "Tất cả"
    return f"[Tài liệu: {filename} | Năm: {year_str} | Loại: {label}]"


# ---------------------------------------------------------------------------
# ENTRY POINT — được gọi bởi Background Task
# ---------------------------------------------------------------------------

async def process_document(doc_id: int, file_path: str, year: Optional[int], doc_type: str):
    logger.info(f"[Parser] Bắt đầu xử lý document ID {doc_id} từ {file_path}")

    try:
        ext = Path(file_path).suffix.lower()
        filename = Path(file_path).name
        context_header = _build_context_header(filename, year, doc_type)

        all_chunks: list[Document] = []

        # ==============================================================
        # LAYER 1: Convert
        # ==============================================================
        if ext == ".pdf":
            logger.info(f"[Parser] PDF mode: pdfplumber + normalize_merged_cells")
            prose_text, tables = _convert_pdf_to_parts(file_path)

            # Kiểm tra nội dung rỗng
            if (not prose_text or len(prose_text.strip()) < 50) and not tables:
                raise ValueError(
                    "Không trích xuất được nội dung. File có thể bị scan (ảnh) "
                    "hoặc không đúng định dạng được hỗ trợ."
                )

            # ==============================================================
            # LAYER 2: Dual Chunking
            # ==============================================================
            if prose_text.strip():
                prose_chunks = _chunk_prose(prose_text, context_header, year, doc_type, doc_id)
                all_chunks.extend(prose_chunks)
                logger.info(f"[Parser] Prose → {len(prose_chunks)} chunks")

            if tables:
                table_chunks = _chunk_tables(tables, context_header, year, doc_type, doc_id, filename)
                all_chunks.extend(table_chunks)
                logger.info(f"[Parser] Tables ({len(tables)} bảng) → {len(table_chunks)} chunks")

        else:
            logger.info(f"[Parser] Generic mode: MarkItDown cho {ext}")
            md_content = _convert_generic_to_markdown(file_path)

            if not md_content or len(md_content.strip()) < 50:
                raise ValueError(
                    "Không trích xuất được nội dung. File có thể không đúng "
                    "định dạng được hỗ trợ."
                )

            # ==============================================================
            # LAYER 2 (Generic): Chỉ dùng Prose chunking
            # ==============================================================
            all_chunks = _chunk_prose(md_content, context_header, year, doc_type, doc_id)

        logger.info(
            f"[Parser] Document {doc_id}: tổng {len(all_chunks)} chunks "
            f"({len([c for c in all_chunks if c.metadata.get('chunk_type','').startswith('table')])} table chunks, "
            f"{len([c for c in all_chunks if c.metadata.get('chunk_type') == 'prose'])} prose chunks)"
        )

        # ==============================================================
        # LAYER 3: Context đã được inject trong _chunk_prose/_chunk_tables
        # Bước cuối: Lưu vào PostgreSQL
        # ==============================================================
        async with AsyncSessionLocal() as db:
            doc = await db.get(UploadedDocument, doc_id)
            if not doc:
                logger.error(f"[Parser] Không tìm thấy document {doc_id} trong DB")
                return

            for chunk in all_chunks:
                db_chunk = DocumentChunk(
                    document_id=doc_id,
                    content=chunk.page_content,
                    metadata_payload=chunk.metadata,
                    status="pending",
                )
                db.add(db_chunk)

            doc.status = "pending_review"
            await db.commit()
            logger.info(f"[Parser] Đã tạo {len(all_chunks)} chunks cho document {doc_id}. Chờ Admin duyệt.")

    except ValueError as e:
        # Lỗi do nội dung không hợp lệ (file scan, rỗng...)
        logger.warning(f"[Parser] Document {doc_id} từ chối: {str(e)}")
        async with AsyncSessionLocal() as db:
            doc = await db.get(UploadedDocument, doc_id)
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)
                await db.commit()

    except Exception as e:
        logger.error(f"[Parser] Lỗi xử lý document {doc_id}: {str(e)}", exc_info=True)
        async with AsyncSessionLocal() as db:
            doc = await db.get(UploadedDocument, doc_id)
            if doc:
                doc.status = "failed"
                doc.error_message = f"Lỗi hệ thống khi phân tích tài liệu: {str(e)}"
                await db.commit()
