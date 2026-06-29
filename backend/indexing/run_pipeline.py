"""
indexing/run_pipeline.py
========================
Entry Point — Điều phối toàn bộ 5 bước ETL Pipeline.

Chạy:
    # Xử lý một file PDF:
    python indexing/run_pipeline.py --pdf data/DeAn2026.pdf

    # Xử lý toàn bộ thư mục:
    python indexing/run_pipeline.py --dir data/

    # Tùy chỉnh collection và fallback metadata:
    python indexing/run_pipeline.py --pdf data/QuyCheTD.pdf \\
        --year 2026 --doc_type quy_che --collection tuyen_sinh_dhv

Đầu ra:
    - Chunks được upsert vào Qdrant (idempotent)
    - needs_review.json: danh sách trang có dữ liệu đáng ngờ
    - Log chi tiết từng bước ra stdout

Cấu trúc luồng:
    PDF/DOCX → [1]Images → [2]Gemini JSON → [3]Validate → [4]Chunks → [5]Qdrant
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Thêm root dir vào sys.path để import các module core/ và indexing/
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

# Setup logging sớm
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")

from qdrant_client import QdrantClient

from indexing.pdf_to_images import pdf_to_images
from indexing.vision_extractor import extract_page_with_gemini  # backward-compat; delegate sang get_ocr_provider() trong DB
from indexing.validator import validate_markdown
from indexing.chunker import (
    extract_tables_from_markdown, 
    table_to_semantic_chunks, 
    text_chunks,
    create_boundary_chunks,
    verify_boundary_sync,
    apply_verification
)
from indexing.indexer import get_embed_model, index_chunks
from indexing.text_utils import normalize_scope, repair_mojibake, repair_text_tree
from core.vectordb import setup_collection


# ---------------------------------------------------------------------------
# Pipeline Core
# ---------------------------------------------------------------------------

def process_pdf(
    pdf_path: str,
    qdrant: QdrantClient,
    collection: str,
    fallback_year: int,
    fallback_doc_type: str,
    tmp_dir: str = "./tmp_images",
) -> dict:
    """
    Xử lý một file PDF qua toàn bộ 5 bước pipeline.

    Args:
        pdf_path:         Đường dẫn tới file PDF.
        qdrant:           QdrantClient đã kết nối.
        collection:       Tên collection Qdrant.
        fallback_year:    Năm mặc định nếu Gemini không nhận diện được.
        fallback_doc_type: Loại tài liệu mặc định.
        tmp_dir:          Thư mục tạm cho ảnh JPEG.

    Returns:
        {
            "file":         str,
            "pages":        int,
            "chunks":       int,
            "indexed":      int,
            "needs_review": list[dict]
        }
    """
    pdf_name = Path(pdf_path).name
    logger.info("═" * 60)
    logger.info("📄 XỬ LÝ FILE: %s", pdf_name)
    logger.info("═" * 60)

    model = get_embed_model()

    # ── Bước 1: PDF → Ảnh ──
    logger.info("[1/5] PDF → JPEG images...")
    images = pdf_to_images(pdf_path, output_dir=tmp_dir)
    logger.info("[1/5] Tạo %d trang ảnh.", len(images))

    all_chunks: list[dict] = []
    page_chunks_by_page: list[list[dict]] = []
    needs_review: list[dict] = []

    # ── Bước 2-4: Xử lý từng trang ──
    for i, img_path in enumerate(images):
        page_num = i + 1
        logger.info("── Trang %d/%d: %s ──", page_num, len(images), Path(img_path).name)

        # Bước 2: Gemini Vision → JSON
        logger.info("  [2/5] Gemini Vision extraction...")
        extracted = extract_page_with_gemini(img_path)
        content = repair_mojibake(str(extracted.get("content", "")))
        gemini_meta = repair_text_tree(extracted.get("metadata", {}))
        if not isinstance(gemini_meta, dict):
            gemini_meta = {}

        if not content.strip():
            logger.warning("  [2/5] Trang %d không có nội dung — bỏ qua.", page_num)
            continue

        # Xây dựng metadata tổng hợp (Gemini ưu tiên, fallback từ args)
        meta = {
            "source_file": pdf_name,
            "page":        page_num,
            "year":        _coalesce(gemini_meta.get("year"), fallback_year),
            "doc_type":    _coalesce(gemini_meta.get("doc_type"), fallback_doc_type),
            "scope":       normalize_scope(_coalesce(gemini_meta.get("scope"), gemini_meta.get("faculty"), "all")),
        }

        # Bước 3: Validator
        logger.info("  [3/5] Kiểm duyệt số liệu...")
        validation = validate_markdown(
            content, source_hint=f"{pdf_name} trang {page_num}"
        )
        if not validation["valid"]:
            review_entry = {
                "file":   pdf_name,
                "page":   page_num,
                "issues": validation["issues"],
            }
            needs_review.append(review_entry)
            logger.warning(
                "  [3/5] ⚠️  %d vi phạm phát hiện — đã ghi vào needs_review.",
                len(validation["issues"]),
            )
        else:
            logger.info("  [3/5] ✅ Dữ liệu hợp lệ.")

        # Bước 4: Chunking
        logger.info("  [4/5] Phân rã thành Semantic Chunks...")
        page_chunks: list[dict] = []

        tables = extract_tables_from_markdown(content)
        for tbl in tables:
            page_chunks.extend(table_to_semantic_chunks(tbl, meta))

        page_chunks.extend(text_chunks(content, meta))
        page_chunks_by_page.append(page_chunks)
        all_chunks.extend(page_chunks)

        logger.info(
            "  [4/5] Trang %d: %d bảng → %d table chunks + %d text chunks = %d tổng",
            page_num,
            len(tables),
            len([c for c in page_chunks if c.get("metadata", {}).get("chunk_type") == "table_row"]),
            len([c for c in page_chunks if c.get("metadata", {}).get("chunk_type") == "paragraph"]),
            len(page_chunks),
        )

    # ── Bước Boundary Chunking ──
    from indexing.vision_extractor import _MAIN_LOOP
    if _MAIN_LOOP is not None and _MAIN_LOOP.is_running():
        boundary_chunks = create_boundary_chunks(page_chunks_by_page)
        if boundary_chunks:
            logger.info("[4.5/5] Đã tạo %d boundary chunks. Chờ LLM xác minh (Timeout 60s)...", len(boundary_chunks))
            verify_results = verify_boundary_sync(boundary_chunks, _MAIN_LOOP)
            verified_count = sum(1 for v in verify_results.values() if v is True)
            skipped_count = len(boundary_chunks) - verified_count
            logger.info("[4.5/5] Xác minh xong: Tổng %d boundary chunks | %d chunks hợp lệ (True) được nối | %d chunks bị bỏ qua (False/Lỗi)", len(boundary_chunks), verified_count, skipped_count)
            all_chunks = apply_verification(all_chunks, boundary_chunks, verify_results)
    else:
        logger.warning("[4.5/5] Bỏ qua Boundary Chunking do không tìm thấy Event Loop hợp lệ.")

    # ── Bước 5: Index toàn bộ chunks ──
    logger.info("[5/5] Upsert %d chunks vào Qdrant collection '%s'...", len(all_chunks), collection)
    indexed_count = index_chunks(all_chunks, qdrant, model, collection)
    logger.info("[5/5] ✅ Đã index %d/%d chunks.", indexed_count, len(all_chunks))

    return {
        "file":         pdf_name,
        "pages":        len(images),
        "chunks":       len(all_chunks),
        "indexed":      indexed_count,
        "needs_review": needs_review,
    }


def run(args: argparse.Namespace) -> None:
    """
    Entry point chính — xử lý file đơn hoặc cả thư mục.
    """
    # Khởi tạo Qdrant
    qdrant = QdrantClient(
        host=args.qdrant_host,
        port=int(args.qdrant_port),
        timeout=30,
    )

    # Đảm bảo collection tồn tại
    setup_collection(collection_name=args.collection_name)

    # Thu thập danh sách file PDF cần xử lý
    pdf_files: list[str] = []

    if args.pdf:
        pdf_files.append(args.pdf)
    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.is_dir():
            logger.error("Thư mục không tồn tại: %s", args.dir)
            sys.exit(1)
        pdf_files = [str(p) for p in sorted(dir_path.glob("*.pdf"))]
        if not pdf_files:
            logger.warning("Không tìm thấy file PDF nào trong: %s", args.dir)
            sys.exit(0)
        logger.info("Tìm thấy %d file PDF trong %s", len(pdf_files), args.dir)

    if not pdf_files:
        logger.error("Phải cung cấp --pdf hoặc --dir")
        sys.exit(1)

    # Xử lý từng file và gom kết quả
    all_needs_review: list[dict] = []
    total_chunks = 0
    total_indexed = 0

    for pdf_path in pdf_files:
        result = process_pdf(
            pdf_path=pdf_path,
            qdrant=qdrant,
            collection=args.collection_name,
            fallback_year=int(args.year),
            fallback_doc_type=args.doc_type,
            tmp_dir=args.tmp_dir,
        )
        total_chunks  += result["chunks"]
        total_indexed += result["indexed"]
        all_needs_review.extend(result["needs_review"])

    # Lưu needs_review.json
    if all_needs_review:
        review_path = Path(args.review_output)
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump(all_needs_review, f, ensure_ascii=False, indent=2)
        logger.warning(
            "⚠️  %d trang cần rà soát thủ công → %s",
            len(all_needs_review), review_path,
        )
    else:
        logger.info("✅ Không có trang nào cần rà soát thủ công.")

    # Tổng kết
    logger.info("═" * 60)
    logger.info("🏁 PIPELINE HOÀN THÀNH")
    logger.info("   Files xử lý : %d", len(pdf_files))
    logger.info("   Tổng chunks  : %d", total_chunks)
    logger.info("   Đã index     : %d", total_indexed)
    logger.info("   Cần rà soát  : %d trang", len(all_needs_review))
    logger.info("═" * 60)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coalesce(*values):
    """Trả về giá trị đầu tiên không phải None/rỗng trong danh sách."""
    for v in values:
        if v is not None and str(v).strip() not in ("", "None", "null"):
            return v
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline Indexing Tài liệu Tuyển sinh — ĐH Vinh",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  # Xử lý một file:
  python indexing/run_pipeline.py --pdf data/DeAn2026.pdf

  # Xử lý cả thư mục:
  python indexing/run_pipeline.py --dir data/

  # Tùy chỉnh đầy đủ:
  python indexing/run_pipeline.py --pdf data/QuyCheTD.pdf \\
      --year 2026 --doc_type quy_che \\
      --qdrant-host localhost --qdrant-port 6333 \\
      --collection tuyen_sinh_dhv
        """,
    )

    # Nguồn tài liệu (chọn 1 trong 2)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--pdf", help="Đường dẫn tới file PDF đơn lẻ")
    source_group.add_argument("--dir", help="Thư mục chứa nhiều file PDF")

    # Metadata fallback
    parser.add_argument("--year",     default=2026,      help="Năm tuyển sinh fallback (mặc định: 2026)")
    parser.add_argument("--doc_type", default="quy_che", help="Loại tài liệu fallback (mặc định: quy_che)")

    # Hạ tầng
    parser.add_argument("--qdrant-host",  default=os.getenv("QDRANT_HOST", "localhost"))
    parser.add_argument("--qdrant-port",  default=os.getenv("QDRANT_PORT", "6333"))
    parser.add_argument("--collection_name", default=os.getenv("QDRANT_COLLECTION", "tuyen_sinh_dhv"))

    # Cấu hình pipeline
    parser.add_argument("--tmp-dir",       default="./tmp_images",      help="Thư mục tạm cho ảnh JPEG")
    parser.add_argument("--review-output", default="./needs_review.json", help="File output danh sách cần rà soát")

    args = parser.parse_args()
    run(args)
