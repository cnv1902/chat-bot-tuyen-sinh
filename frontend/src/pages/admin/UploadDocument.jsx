import React, { useState, useRef, useEffect } from 'react';
import { UploadCloud, FileText, X, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function UploadDocument() {
  const [file, setFile] = useState(null);
  const [year, setYear] = useState(2026);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const [uploadError, setUploadError] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const [uploadedDocs, setUploadedDocs] = useState([]);
  const pollingRef = useRef(null);

  const fetchUploadedDocs = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/upload/documents?limit=5`);
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

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      const ext = droppedFile.name.split('.').pop().toLowerCase();
      if (ext === 'pdf' || ext === 'docx') {
        setFile(droppedFile);
        setUploadMsg('');
        setUploadError(false);
      } else {
        setUploadMsg('Hệ thống chỉ hỗ trợ tệp tin định dạng .pdf hoặc .docx.');
        setUploadError(true);
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setUploadMsg('Vui lòng chọn file tài liệu (.pdf, .docx).');
      setUploadError(true);
      return;
    }

    setUploadLoading(true);
    setUploadMsg('');
    setUploadError(false);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('year', year);

    try {
      const response = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();

      if (response.ok) {
        setUploadMsg(data.message || 'Nạp tài liệu thành công. Pipeline AI đang xử lý ngầm.');
        setUploadError(false);
        setFile(null);
        e.target.reset();
        setTimeout(fetchUploadedDocs, 800);
      } else {
        setUploadMsg(data.detail || 'Lỗi xử lý tài liệu.');
        setUploadError(true);
      }
    } catch (err) {
      setUploadMsg('Lỗi kết nối tới máy chủ API.');
      setUploadError(true);
    } finally {
      setUploadLoading(false);
    }
  };

  return (
    <div className="admin-card">
      <div style={{ borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase' }}>Ingest PDF/DOCX</h3>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px' }}>
          Xử lý OCR tài liệu, lọc mojibake tiếng Việt, chia semantic chunk và đưa vào Qdrant Vector database.
        </p>
      </div>

      <form onSubmit={handleUploadSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontWeight: 'bold', fontSize: '0.85rem', color: 'var(--text-main)' }}>FILE TÀI LIỆU (PDF/DOCX) <span style={{ color: 'red' }}>*</span></label>

          <input
            type="file"
            ref={fileInputRef}
            accept=".pdf,.docx"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />

          {!file ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current.click()}
              style={{
                border: isDragging ? '2px dashed var(--primary-blue)' : '1.5px dashed var(--border-color)',
                padding: '40px 24px',
                textAlign: 'center',
                backgroundColor: isDragging ? 'rgba(56, 122, 195, 0.05)' : 'var(--bg-main)',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseOver={e => {
                if (!isDragging) e.currentTarget.style.borderColor = 'var(--primary-blue)';
              }}
              onMouseOut={e => {
                if (!isDragging) e.currentTarget.style.borderColor = 'var(--border-color)';
              }}
            >
              <UploadCloud size={44} color="var(--primary-blue)" style={{ margin: '0 auto 12px auto' }} />
              <p style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--text-main)', margin: 0 }}>
                Kéo thả file tài liệu vào đây hoặc <span style={{ color: 'var(--primary-blue)', textDecoration: 'underline' }}>chọn tệp</span>
              </p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '8px' }}>
                Hỗ trợ định dạng PDF và DOCX (Tối đa 50MB)
              </p>
            </div>
          ) : (
            <div style={{
              border: '1.5px solid var(--border-color)',
              padding: '20px 24px',
              backgroundColor: '#f8fafc',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{
                  width: '48px',
                  height: '48px',
                  backgroundColor: 'rgba(56, 122, 195, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--primary-blue)'
                }}>
                  <FileText size={24} />
                </div>
                <div>
                  <p style={{ fontWeight: 'bold', color: 'var(--text-main)', fontSize: '0.95rem', margin: 0 }}>{file.name}</p>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
                    {(file.size / 1024).toFixed(1)} KB · Sẵn sàng tải lên
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setFile(null)}
                style={{
                  backgroundColor: 'transparent',
                  color: '#ef4444',
                  border: 'none',
                  padding: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer'
                }}
                onMouseOver={e => e.currentTarget.style.color = '#b91c1c'}
                onMouseOut={e => e.currentTarget.style.color = '#ef4444'}
              >
                <X size={20} />
              </button>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontWeight: 'bold', fontSize: '0.85rem', color: 'var(--text-main)' }}>NĂM TUYỂN SINH MẶC ĐỊNH <span style={{ color: 'red' }}>*</span></label>
          <input
            type="number"
            value={year}
            onChange={e => setYear(parseInt(e.target.value, 10) || 2026)}
            style={{
              border: '1.5px solid var(--border-color)',
              padding: '12px 16px',
              backgroundColor: 'var(--bg-main)',
              fontSize: '1rem',
              width: '100%',
              maxWidth: '300px'
            }}
          />
        </div>

        <button
          type="submit"
          disabled={uploadLoading}
          style={{
            backgroundColor: uploadLoading ? 'var(--text-muted)' : 'var(--primary-blue)',
            color: '#ffffff',
            padding: '16px 32px',
            fontWeight: 'bold',
            alignSelf: 'flex-start',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            cursor: uploadLoading ? 'not-allowed' : 'pointer',
            border: 'none',
            borderRadius: '4px'
          }}
        >
          {uploadLoading ? 'ĐANG TIẾN HÀNH XỬ LÝ...' : 'NẠP VÀO CƠ SỞ DỮ LIỆU TRI THỨC'}
        </button>
      </form>

      {uploadMsg && (
        <div style={{
          marginTop: '24px',
          padding: '16px',
          backgroundColor: uploadError ? '#fef2f2' : '#f0fdf4',
          border: `1.5px solid ${uploadError ? '#fecaca' : '#bbf7d0'}`,
          borderLeftWidth: '6px',
          borderLeftColor: uploadError ? '#ef4444' : '#22c55e',
          color: uploadError ? '#991b1b' : '#166534',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontWeight: '500'
        }}>
          {uploadError ? <AlertCircle size={20} /> : <CheckCircle2 size={20} />}
          <span>{uploadMsg}</span>
        </div>
      )}

      {/* BẢNG LỊCH SỬ NẠP TÀI LIỆU (Mini) */}
      <div style={{ marginTop: '36px' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1.5px solid var(--border-color)',
          paddingBottom: '12px',
          marginBottom: '16px'
        }}>
          <h3 style={{ fontSize: '1.05rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Tài liệu nạp gần đây
          </h3>
          <button
            onClick={fetchUploadedDocs}
            title="Làm mới"
            style={{
              background: 'none',
              border: '1.5px solid var(--border-color)',
              padding: '6px 10px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
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
            padding: '32px',
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
                  {['Tên tài liệu', 'Năm', 'Thời điểm nạp', 'Trạng thái', 'Kết quả'].map(h => (
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
                  return (
                    <tr key={doc.id} style={{
                      borderBottom: '1px solid #f1f5f9',
                      backgroundColor: idx % 2 === 0 ? '#ffffff' : '#fafafa',
                      transition: 'background 0.15s'
                    }}>
                      <td style={{ padding: '12px 14px', fontWeight: 500, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
                      <td style={{ padding: '12px 14px', color: 'var(--text-muted)', fontSize: '0.82rem', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <span title={doc.message || ''}>{doc.message || '—'}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
