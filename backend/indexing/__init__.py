"""
indexing/ — Pipeline ETL Offline cho Chatbot Tuyển sinh ĐH Vinh.

Thứ tự xử lý:
    pdf_to_images.py   → [1] PDF → JPEG 200dpi
    vision_extractor.py → [2] JPEG → JSON (Gemini Vision)
    validator.py        → [3] Kiểm duyệt số liệu bằng Regex
    chunker.py          → [4] Markdown → Semantic chunks
    indexer.py          → [5] Chunks → Qdrant (content-hash UUID)
    run_pipeline.py     → Entry point điều phối toàn bộ

Chạy:
    python indexing/run_pipeline.py --pdf data/DeAn2026.pdf
"""
