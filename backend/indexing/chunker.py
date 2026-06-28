"""
indexing/chunker.py
===================
Bước 4: Phân rã Markdown → Semantic Chunks tối ưu cho Vector Search.

Chiến lược kép:
    [A] TABLE CHUNKS  — Mỗi hàng bảng → 1 câu văn hoàn chỉnh đầy đủ ngữ cảnh.
        Ví dụ: "Ngành Kỹ thuật phần mềm (7480103), tổ hợp A00/A01/D01,
                điểm chuẩn 2026: 24.50, chỉ tiêu: 80 sinh viên."
        → Khi người dùng hỏi "điểm chuẩn CNTT", chunk này match chính xác.

    [B] TEXT CHUNKS   — Đoạn văn xuôi (sau khi xóa bảng) → giữ nguyên.
        Lọc đoạn < MIN_PARAGRAPH_LEN để loại bỏ header/footer rác.

Tại sao mỗi hàng bảng là 1 chunk?
    - Embedding của cả bảng bị "pha loãng" — điểm chuẩn ngành A bị ảnh hưởng
      bởi thông tin ngành B, C, D trong cùng bảng.
    - Mỗi hàng độc lập giúp retrieval chính xác theo tên ngành cụ thể.
"""

import logging
import re
from io import StringIO
from typing import Optional

import pandas as pd

from indexing.text_utils import normalize_scope, repair_mojibake

logger = logging.getLogger(__name__)

# Độ dài tối thiểu (ký tự) để một đoạn văn được coi là meaningful
MIN_PARAGRAPH_LEN = 60


# ---------------------------------------------------------------------------
# Table Extraction & Semantic Chunking
# ---------------------------------------------------------------------------

_TABLE_PATTERN = re.compile(
    r"(\|.+\|\n\|[-| :]+\|\n(?:\|.+\|\n?)*)",
    re.MULTILINE,
)


def extract_tables_from_markdown(markdown: str) -> list[str]:
    """
    Tìm tất cả Markdown Table trong văn bản.

    Pattern bắt:
        |col1|col2|...|\n
        |---|---|\n
        |data|data|...\n   (một hoặc nhiều hàng)

    Returns:
        Danh sách chuỗi Markdown Table thô, theo thứ tự xuất hiện.
    """
    return _TABLE_PATTERN.findall(markdown)


def table_to_semantic_chunks(table_md: str, meta: dict) -> list[dict]:
    """
    Chuyển đổi Markdown Table thành danh sách Semantic Chunks.

    Mỗi hàng dữ liệu → 1 chunk dạng câu văn tự nhiên có đầy đủ ngữ cảnh.
    Chunk tự chứa đủ thông tin để trả lời câu hỏi mà không cần hàng khác.

    Cột được mapping linh hoạt — thử nhiều tên cột có thể có:
        Tên ngành: "Tên ngành" | "Ngành" | "Tên Ngành đào tạo"
        Mã ngành:  "Mã ngành"  | "Mã số ngành" | "Mã"
        Điểm:      "Điểm chuẩn" | f"Điểm {year}" | "Điểm trúng tuyển"

    Args:
        table_md: Chuỗi Markdown Table (đầu ra của extract_tables_from_markdown).
        meta:     Dict metadata: {year, doc_type, scope, source_file, page, ...}

    Returns:
        Danh sách dict chunks: [{"content": str, "metadata": dict}, ...]
        Rỗng nếu bảng không parse được.
    """
    try:
        table_md = repair_mojibake(table_md)
        df = _parse_markdown_table(table_md)
        if df is None or df.empty:
            return []

        year      = meta.get("year", "")
        source    = repair_mojibake(str(meta.get("source_file", "Tài liệu ĐH Vinh")))
        page      = meta.get("page", "?")
        scope     = normalize_scope(meta.get("scope", meta.get("faculty", "all")))

        chunks = []
        summary_items = []
        for _, row in df.iterrows():
            # --- Trích xuất từng field với fallback tên cột ---
            name       = repair_mojibake(_get_col(row, ["Tên ngành", "Ngành", "Tên ngành đào tạo", "Tên Ngành", "Loại chỉ tiêu"]))
            code       = repair_mojibake(_get_col(row, ["Mã ngành", "Mã số", "Mã số ngành", "Mã"]))
            combo      = repair_mojibake(_get_col(row, ["Tổ hợp", "Tổ hợp môn", "Khối thi", "Tổ hợp xét tuyển"]))
            quota      = repair_mojibake(_get_col(row, ["Chỉ tiêu", "Số lượng", "CT"]))
            # Điểm chuẩn — thử tên có năm trước ("Điểm 2026"), rồi tên chung
            score_col_candidates = [f"Điểm {year}", f"Điểm chuẩn {year}",
                                    "Điểm chuẩn", "Điểm trúng tuyển", "Điểm"]
            score = repair_mojibake(_get_col(row, score_col_candidates))

            # Bỏ qua hàng rỗng hoàn toàn
            if not name and not code:
                continue

            # --- Dữ liệu cho Chunk Tổng hợp ---
            if name:
                item_desc = name
                if quota: item_desc += f" (Chỉ tiêu: {quota})"
                if score: item_desc += f" (Điểm: {score})"
                summary_items.append(item_desc)

            # --- Xây dựng câu văn semantic ---
            parts = []
            if name:
                parts.append(f"Ngành {name}")
            if code:
                parts.append(f"mã ngành {code}")
            if combo:
                parts.append(f"tổ hợp môn xét tuyển: {combo}")
            if score:
                parts.append(f"điểm chuẩn năm {year}: {score}" if year else f"điểm chuẩn: {score}")
            if quota:
                parts.append(f"chỉ tiêu: {quota} sinh viên")
            if scope and scope != "all":
                parts.append(f"thuộc {scope}")

            parts.append(f"cơ sở đào tạo: Trường Đại học Vinh")
            parts.append(f"nguồn: {source}, trang {page}")

            content = ". ".join(parts) + "."

            chunks.append({
                "content":  content,
                "metadata": {
                    **meta,
                    "major":      name,
                    "major_code": code,
                    "chunk_type": "table_row",
                },
            })

        # --- Thêm Chunk Tổng Hợp (Synthetic Chunk) ---
        if len(summary_items) > 3:
            title = f"Bảng danh sách tổng hợp {len(summary_items)} ngành/mục"
            if scope and scope != "all":
                title += f" thuộc {scope}"
            if year:
                title += f" năm {year}"
            
            summary_text = f"{title}, cơ sở đào tạo: Trường Đại học Vinh. Bao gồm: " + "; ".join(summary_items) + "."
            
            chunks.append({
                "content": summary_text,
                "metadata": {
                    **meta,
                    "chunk_type": "table_summary",
                    "row_count": len(summary_items)
                }
            })

        logger.debug(
            "[Chunker/Table] Parse thành công: %d rows → %d chunks (bao gồm summary) | trang %s",
            len(df), len(chunks), page,
        )
        return chunks

    except Exception as e:
        logger.error("[Chunker/Table] Lỗi parse bảng: %s", str(e), exc_info=True)
        return []


def text_chunks(markdown: str, meta: dict) -> list[dict]:
    """
    Trích xuất đoạn văn xuôi (sau khi đã loại bỏ bảng Markdown).

    Mỗi đoạn cách nhau bằng dòng trống (\n\n) là 1 chunk tiềm năng.
    Lọc bỏ:
        - Đoạn quá ngắn (< MIN_PARAGRAPH_LEN ký tự) — thường là header/footer rác
        - Đoạn chỉ là dấu gạch ngang hoặc dấu chấm lặp lại

    Args:
        markdown: Toàn bộ nội dung Markdown (có thể còn chứa bảng).
        meta:     Dict metadata để đính kèm vào mỗi chunk.

    Returns:
        Danh sách dict chunks từ đoạn văn xuôi.
    """
    # Xóa các bảng Markdown trước khi xử lý văn xuôi
    markdown = repair_mojibake(markdown)
    text_only = _TABLE_PATTERN.sub("", markdown).strip()

    if not text_only:
        return []

    # Tách theo đoạn (2+ dòng trống)
    paragraphs = re.split(r"\n{2,}", text_only)

    chunks = []
    for para in paragraphs:
        clean = repair_mojibake(para.strip())
        # Lọc đoạn quá ngắn hoặc chỉ là ký tự phân cách
        if len(clean) < MIN_PARAGRAPH_LEN:
            continue
        if re.match(r"^[-=_*#\s]+$", clean):
            continue

        chunks.append({
            "content":  clean,
            "metadata": {**meta, "chunk_type": "paragraph"},
        })

    logger.debug(
        "[Chunker/Text] %d đoạn văn → %d chunks hợp lệ | trang %s",
        len(paragraphs), len(chunks), meta.get("page", "?"),
    )
    return chunks


# ---------------------------------------------------------------------------
# Private Helpers
# ---------------------------------------------------------------------------

def _parse_markdown_table(table_md: str) -> Optional[pd.DataFrame]:
    """
    Parse Markdown Table → pandas DataFrame.

    Xử lý đặc thù của Markdown Table format:
    - Hàng đầu là header (| col1 | col2 | ...)
    - Hàng thứ 2 là separator (| --- | --- |) — cần loại bỏ
    - Các cột bắt đầu/kết thúc bằng | cần strip

    Returns:
        DataFrame đã clean, hoặc None nếu parse thất bại.
    """
    try:
        # Đọc bằng pandas với separator |
        df = pd.read_csv(
            StringIO(table_md),
            sep="|",
            skipinitialspace=True,
            engine="python",
        )

        # Bỏ cột NaN đầu/cuối (do | đứng đầu/cuối dòng)
        df = df.dropna(axis=1, how="all")

        # Clean tên cột
        df.columns = [str(c).strip() for c in df.columns]

        # Loại bỏ hàng separator (chứa toàn --- hoặc :--:)
        sep_mask = df.apply(
            lambda row: row.astype(str).str.match(r"^[-:\s]+$").all(), axis=1
        )
        df = df[~sep_mask].reset_index(drop=True)

        # Clean giá trị trong các ô
        df = df.apply(lambda col: col.astype(str).str.strip())
        # Thay "nan" thành ""
        df = df.replace("nan", "")

        return df if not df.empty else None

    except Exception as e:
        logger.debug("[Chunker] _parse_markdown_table thất bại: %s", str(e))
        return None


def _get_col(row: pd.Series, candidates: list[str]) -> str:
    """
    Lấy giá trị từ row theo danh sách tên cột ưu tiên (case-insensitive).

    Args:
        row:        pandas Series (một hàng DataFrame).
        candidates: Danh sách tên cột theo thứ tự ưu tiên.

    Returns:
        Chuỗi giá trị của cột đầu tiên tìm thấy, hoặc "" nếu không có.
    """
    row_lower = {k.lower(): v for k, v in row.items()}
    for candidate in candidates:
        val = row_lower.get(candidate.lower(), "")
        if val and val not in ("nan", "none", "-", ""):
            return str(val).strip()
    return ""
