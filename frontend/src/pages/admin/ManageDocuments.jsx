import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { RefreshCw, FileText, Trash2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function ManageDocuments() {
  const { showToast } = useOutletContext();
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [deletingId, setDeletingId] = useState(null);
  const [deleteModal, setDeleteModal] = useState({ open: false, doc: null });
  const pollingRef = useRef(null);

  const fetchUploadedDocs = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/upload/documents?limit=50`);
      if (res.ok) setUploadedDocs(await res.json());
    } catch (_) {/* silent */}
  };

  useEffect(() => {
    fetchUploadedDocs();
  }, []);

  useEffect(() => {
    const hasProcessing = uploadedDocs.some(d => d.status === 'processing');
    if (hasProcessing) {
      pollingRef.current = setInterval(fetchUploadedDocs, 5000);
    } else {
      clearInterval(pollingRef.current);
    }
    return () => clearInterval(pollingRef.current);
  }, [uploadedDocs]);

  const handleDeleteDoc = (doc) => {
    setDeleteModal({ open: true, doc });
  };

  const handleConfirmDelete = async () => {
    const doc = deleteModal.doc;
    if (!doc) return;
    setDeleteModal({ open: false, doc: null });
    setDeletingId(doc.id);
    try {
      const res = await fetch(`${API_BASE}/api/upload/documents/${doc.id}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`Đã xóa "${doc.filename}" thành công. Qdrant: ${data.summary?.qdrant_vectors_deleted ?? '?'} vectors, ảnh OCR: ${data.summary?.tmp_images_deleted ?? 0} files.`);
        await fetchUploadedDocs();
      } else {
        showToast(data.detail || 'Lỗi khi xóa tài liệu.', 'error');
      }
    } catch (err) {
      showToast('Lỗi kết nối máy chủ khi xóa.', 'error');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="admin-card">
      <div style={{ borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase' }}>Quản lý Danh sách Tài liệu</h3>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px' }}>
          Xem toàn bộ tài liệu đã nạp. Thao tác <strong style={{ color: '#dc2626' }}>Xóa</strong> sẽ xóa vĩnh viễn file gốc, ảnh OCR, dữ liệu vector trong Qdrant và bản ghi trong Database.
        </p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '16px' }}>
        <button
          onClick={fetchUploadedDocs}
          style={{
            background: 'none',
            border: '1.5px solid var(--border-color)',
            padding: '8px 14px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.82rem',
            color: 'var(--text-muted)',
            fontWeight: 'bold'
          }}
        >
          <RefreshCw size={14} />
          Làm mới
        </button>
      </div>

      {uploadedDocs.length === 0 ? (
        <div style={{
          textAlign: 'center',
          color: 'var(--text-muted)',
          padding: '40px',
          border: '1.5px dashed var(--border-color)',
          fontSize: '0.9rem'
        }}>
          Chưa có tài liệu nào được nạp vào hệ thống.
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc' }}>
                {['#', 'Tên tài liệu', 'Năm', 'Thời điểm nạp', 'Trạng thái', 'Kết quả / Mô tả', 'Hành động'].map(h => (
                  <th key={h} style={{
                    textAlign: 'left',
                    padding: '10px 14px',
                    fontWeight: 700,
                    fontSize: '0.75rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: 'var(--text-muted)',
                    borderBottom: '1.5px solid var(--border-color)',
                    whiteSpace: 'nowrap'
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {uploadedDocs.map((doc, idx) => {
                const statusConfig = {
                  processing: { label: 'ĐANG XỬ LÝ', bg: '#fefce8', color: '#854d0e', border: '#fde047', dot: '#eab308' },
                  success: { label: 'THÀNH CÔNG', bg: '#f0fdf4', color: '#166534', border: '#bbf7d0', dot: '#22c55e' },
                  failed: { label: 'THẤT BẠI', bg: '#fef2f2', color: '#991b1b', border: '#fecaca', dot: '#ef4444' },
                };
                const st = statusConfig[doc.status] || statusConfig.processing;
                const createdAt = doc.created_at
                  ? new Date(doc.created_at).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
                  : '—';
                const isDeleting = deletingId === doc.id;
                const isProcessing = doc.status === 'processing';
                return (
                  <tr key={doc.id} style={{
                    borderBottom: '1px solid #f1f5f9',
                    backgroundColor: isDeleting ? '#fff5f5' : idx % 2 === 0 ? '#ffffff' : '#fafafa',
                    transition: 'background 0.15s',
                    opacity: isDeleting ? 0.6 : 1
                  }}>
                    <td style={{ padding: '12px 14px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>{doc.id}</td>
                    <td style={{ padding: '12px 14px', fontWeight: 500, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileText size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                        <span title={doc.filename}>{doc.filename}</span>
                      </div>
                    </td>
                    <td style={{ padding: '12px 14px', color: 'var(--text-muted)' }}>{doc.year}</td>
                    <td style={{ padding: '12px 14px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{createdAt}</td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '3px 10px',
                        backgroundColor: st.bg,
                        color: st.color,
                        border: `1px solid ${st.border}`,
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        letterSpacing: '0.05em',
                        whiteSpace: 'nowrap'
                      }}>
                        <span style={{
                          width: 7, height: 7,
                          borderRadius: '50%',
                          backgroundColor: st.dot,
                          display: 'inline-block',
                          ...(doc.status === 'processing' ? { animation: 'pulse 1.5s infinite' } : {})
                        }} />
                        {st.label}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px', color: 'var(--text-muted)', fontSize: '0.82rem', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span title={doc.message || ''}>{doc.message || '—'}</span>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <button
                        id={`btn-delete-doc-${doc.id}`}
                        onClick={() => handleDeleteDoc(doc)}
                        disabled={isDeleting}
                        title={isProcessing ? 'Hủy và xóa vĩnh viễn' : `Xóa vĩnh viễn "${doc.filename}"`}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '7px 14px',
                          backgroundColor: isDeleting ? '#f1f5f9' : '#fef2f2',
                          color: isDeleting ? '#94a3b8' : '#dc2626',
                          border: `1.5px solid ${isDeleting ? '#e2e8f0' : '#fecaca'}`,
                          fontWeight: 'bold',
                          fontSize: '0.78rem',
                          cursor: isDeleting ? 'not-allowed' : 'pointer',
                          transition: 'all 0.15s'
                        }}
                        onMouseOver={e => {
                          if (!isDeleting) {
                            e.currentTarget.style.backgroundColor = '#dc2626';
                            e.currentTarget.style.color = '#ffffff';
                            e.currentTarget.style.borderColor = '#dc2626';
                          }
                        }}
                        onMouseOut={e => {
                          if (!isDeleting) {
                            e.currentTarget.style.backgroundColor = '#fef2f2';
                            e.currentTarget.style.color = '#dc2626';
                            e.currentTarget.style.borderColor = '#fecaca';
                          }
                        }}
                      >
                        <Trash2 size={14} />
                        {isDeleting ? 'Đang xóa...' : 'Xóa'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div style={{
            marginTop: '16px',
            padding: '12px 16px',
            backgroundColor: '#fef9c3',
            border: '1px solid #fde047',
            borderLeft: '4px solid #f59e0b',
            fontSize: '0.82rem',
            color: '#854d0e'
          }}>
            <strong>⚠️ Lưu ý:</strong> Bạn có thể xóa tài liệu ngay cả khi đang <strong>"Đang xử lý"</strong>. Khi đó tiến trình xử lý ngầm sẽ bị hủy bỏ ngay lập tức. Thao tác xóa không thể hoàn tác.
          </div>
        </div>
      )}

      {/* ── DELETE CONFIRMATION MODAL ── */}
      {deleteModal.open && deleteModal.doc && (
        <div
          id="delete-confirm-modal-overlay"
          onClick={(e) => { if (e.target === e.currentTarget) setDeleteModal({ open: false, doc: null }); }}
          style={{
            position: 'fixed', inset: 0,
            backgroundColor: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(3px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 10000,
            animation: 'fadeIn 0.15s ease'
          }}
        >
          <div
            id="delete-confirm-modal"
            style={{
              backgroundColor: '#ffffff',
              border: '1.5px solid #e2e8f0',
              boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
              padding: '0',
              width: '100%',
              maxWidth: '480px',
              margin: '16px',
              animation: 'slideUp 0.2s ease',
              overflow: 'hidden'
            }}
          >
            {/* Modal Header */}
            <div style={{
              backgroundColor: '#7f1d1d',
              padding: '20px 24px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}>
              <div style={{
                width: '36px', height: '36px',
                backgroundColor: 'rgba(255,255,255,0.15)',
                borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0
              }}>
                <Trash2 size={18} color="#ffffff" />
              </div>
              <div>
                <div style={{ color: '#ffffff', fontWeight: 800, fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Xóa vĩnh viễn tài liệu
                </div>
                <div style={{ color: '#fca5a5', fontSize: '0.78rem', marginTop: '2px' }}>
                  Hành động này không thể hoàn tác
                </div>
              </div>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '24px' }}>
              <p style={{ fontSize: '0.9rem', color: '#374151', marginBottom: '16px', lineHeight: '1.6' }}>
                Bạn đang chuẩn bị xóa tài liệu:
              </p>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '12px 16px',
                backgroundColor: '#f8fafc',
                border: '1.5px solid #e2e8f0',
                marginBottom: '20px'
              }}>
                <FileText size={18} color="#64748b" style={{ flexShrink: 0 }} />
                <span style={{ fontWeight: 700, color: '#1e293b', fontSize: '0.95rem', wordBreak: 'break-all' }}>
                  {deleteModal.doc.filename}
                </span>
              </div>

              <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '12px', fontWeight: 600 }}>
                Các dữ liệu sau sẽ bị xóa hoàn toàn:
              </p>
              <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 20px 0', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {[
                  'File PDF/DOCX gốc trên server',
                  'Ảnh OCR tạm trong thư mục tmp\_images',
                  'Toàn bộ dữ liệu AI vector trong Qdrant',
                  'Bản ghi lịch sử trong PostgreSQL'
                ].map((item, i) => (
                  <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: '0.85rem', color: '#374151' }}>
                    <span style={{
                      width: '6px', height: '6px', borderRadius: '50%',
                      backgroundColor: '#dc2626', flexShrink: 0, marginTop: '6px'
                    }} />
                    {item}
                  </li>
                ))}
              </ul>

              <div style={{
                padding: '10px 14px',
                backgroundColor: '#fef9c3',
                border: '1px solid #fde047',
                borderLeft: '4px solid #f59e0b',
                fontSize: '0.8rem',
                color: '#854d0e',
                marginBottom: '24px'
              }}>
                <strong>⚠️ Hành động này KHÔNG THỂ HOÀN TÁC.</strong> Xác nhận trước khi tiếp tục.
              </div>

              {/* Modal Actions */}
              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button
                  id="btn-cancel-delete"
                  onClick={() => setDeleteModal({ open: false, doc: null })}
                  style={{
                    padding: '10px 24px',
                    border: '1.5px solid #e2e8f0',
                    backgroundColor: '#ffffff',
                    color: '#374151',
                    fontWeight: 700,
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                  onMouseOver={e => { e.currentTarget.style.backgroundColor = '#f8fafc'; }}
                  onMouseOut={e => { e.currentTarget.style.backgroundColor = '#ffffff'; }}
                >
                  HỦY Bỏ
                </button>
                <button
                  id="btn-confirm-delete"
                  onClick={handleConfirmDelete}
                  style={{
                    padding: '10px 24px',
                    border: '1.5px solid #dc2626',
                    backgroundColor: '#dc2626',
                    color: '#ffffff',
                    fontWeight: 700,
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    transition: 'all 0.15s'
                  }}
                  onMouseOver={e => { e.currentTarget.style.backgroundColor = '#b91c1c'; e.currentTarget.style.borderColor = '#b91c1c'; }}
                  onMouseOut={e => { e.currentTarget.style.backgroundColor = '#dc2626'; e.currentTarget.style.borderColor = '#dc2626'; }}
                >
                  <Trash2 size={15} />
                  XÁC NHẬN XÓA
                </button>
              </div>
            </div>
          </div>
          <style>{`
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            @keyframes slideUp { from { transform: translateY(16px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
          `}</style>
        </div>
      )}
    </div>
  );
}
