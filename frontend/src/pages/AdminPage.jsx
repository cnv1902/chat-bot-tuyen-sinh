import React, { useState, useEffect, useRef } from 'react';
import {
  Database,
  UploadCloud,
  AlertCircle,
  CheckCircle2,
  ArrowLeft,
  Menu,
  X,
  Key,
  Cpu,
  Activity,
  FileText,
  RefreshCw,
  Trash2,
  FolderOpen,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PROVIDERS_LIST = [
  { id: 'gemini', label: 'Google Gemini', color: '#4285f4', needsEndpoint: false },
  { id: 'openai', label: 'OpenAI GPT', color: '#10a37f', needsEndpoint: false },
  { id: 'groq', label: 'Groq Cloud', color: '#f97316', needsEndpoint: false },
  { id: 'vllm', label: 'vLLM Server', color: '#8b5cf6', needsEndpoint: true },
];

export default function AdminPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('document'); // document | manage | providers | slots | status
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Tab 1: Upload Document state
  const [file, setFile] = useState(null);
  const [year, setYear] = useState(2026);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const [uploadError, setUploadError] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  // Tab: Delete state
  const [deletingId, setDeletingId] = useState(null);

  // Delete confirmation modal state
  const [deleteModal, setDeleteModal] = useState({ open: false, doc: null });

  // Tab 1b: Uploaded Documents history + status
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const pollingRef = useRef(null);

  const fetchUploadedDocs = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/upload/documents?limit=50`);
      if (res.ok) setUploadedDocs(await res.json());
    } catch (_) {/* silent */ }
  };

  const handleDeleteDoc = (doc) => {
    // Mở modal xác nhận thay vì dùng window.confirm
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

  // Tab 2: Providers Credentials state
  const [providersData, setProvidersData] = useState([]);
  const [providerKeys, setProviderKeys] = useState({
    gemini: '', openai: '', groq: '', vllm: ''
  });
  const [providerEndpoints, setProviderEndpoints] = useState({
    vllm: ''
  });
  const [provLoading, setProvLoading] = useState(false);

  // Tab 3: Slots configurations state
  const [slotsData, setSlotsData] = useState([]);
  const [selectedProviders, setSelectedProviders] = useState({ ocr: 'gemini', chat: 'gemini' });
  const [selectedModels, setSelectedModels] = useState({ ocr: '', chat: '' });
  const [modelsList, setModelsList] = useState({ ocr: [], chat: [] });
  const [modelsLoading, setModelsLoading] = useState({ ocr: false, chat: false });
  const [slotsLoading, setSlotsLoading] = useState(false);

  // System general feedback toast/message
  const [toast, setToast] = useState({ show: false, message: '', type: 'success' });

  const showToast = (message, type = 'success') => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast({ show: false, message: '', type: 'success' }), 4000);
  };

  // Handle file input change
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  // Fetch all credentials, slots, status
  const loadSystemConfig = async () => {
    try {
      // Load providers
      const provRes = await fetch(`${API_BASE}/admin/providers`);
      if (provRes.ok) {
        const data = await provRes.json();
        setProvidersData(data);
        // Fill endpoints if any
        const vllmProv = data.find(p => p.provider === 'vllm');
        if (vllmProv && vllmProv.endpoint) {
          setProviderEndpoints(prev => ({ ...prev, vllm: vllmProv.endpoint }));
        }
      }

      // Load slots
      const slotsRes = await fetch(`${API_BASE}/admin/slots`);
      if (slotsRes.ok) {
        const data = await slotsRes.json();
        setSlotsData(data);

        // Populate slots forms
        const ocrSlot = data.find(s => s.slot === 'ocr');
        const chatSlot = data.find(s => s.slot === 'chat');

        if (ocrSlot) {
          setSelectedProviders(prev => ({ ...prev, ocr: ocrSlot.provider }));
          setSelectedModels(prev => ({ ...prev, ocr: ocrSlot.model_name }));
        }
        if (chatSlot) {
          setSelectedProviders(prev => ({ ...prev, chat: chatSlot.provider }));
          setSelectedModels(prev => ({ ...prev, chat: chatSlot.model_name }));
        }
      }
    } catch (err) {
      showToast('Lỗi tải cấu hình hệ thống từ Backend.', 'error');
    }
  };

  useEffect(() => {
    loadSystemConfig();
    fetchUploadedDocs();
  }, []);

  // Polling: tự động refresh bảng lịch sử khi có file đang xử lý
  useEffect(() => {
    const hasProcessing = uploadedDocs.some(d => d.status === 'processing');
    if (hasProcessing) {
      pollingRef.current = setInterval(fetchUploadedDocs, 5000);
    } else {
      clearInterval(pollingRef.current);
    }
    return () => clearInterval(pollingRef.current);
  }, [uploadedDocs]);

  // Handle upload submit
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
        // Refresh bảng lịch sử ngay sau khi upload thành công
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

  // Handle Provider Save
  const handleSaveProvider = async (providerId) => {
    const key = providerKeys[providerId].trim();
    const endpoint = PROVIDERS_LIST.find(p => p.id === providerId).needsEndpoint
      ? providerEndpoints[providerId].trim()
      : null;

    setProvLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/providers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: providerId,
          api_key: key || null,
          endpoint: endpoint || null,
          is_active: true
        })
      });

      if (res.ok) {
        showToast(`Đã cập nhật cấu hình cho ${providerId.toUpperCase()}.`);
        setProviderKeys(prev => ({ ...prev, [providerId]: '' }));
        await loadSystemConfig();
      } else {
        const data = await res.json();
        showToast(data.detail || 'Lỗi cập nhật credentials.', 'error');
      }
    } catch (err) {
      showToast('Lỗi mạng, không lưu được credentials.', 'error');
    } finally {
      setProvLoading(false);
    }
  };

  // Test provider connection / list models
  const handleLoadModelsForSlot = async (slotType, forceProvider = null) => {
    const provider = forceProvider || selectedProviders[slotType];
    setModelsLoading(prev => ({ ...prev, [slotType]: true }));
    try {
      const res = await fetch(`${API_BASE}/admin/models/${provider}`);
      if (res.ok) {
        const data = await res.json();
        if (data.models && data.models.length > 0) {
          setModelsList(prev => ({ ...prev, [slotType]: data.models }));
          showToast(`Đã kết nối và lấy thành công ${data.models.length} models của ${provider.toUpperCase()}.`);
        } else {
          setModelsList(prev => ({ ...prev, [slotType]: [] }));
          showToast(`Đã kết nối tới ${provider.toUpperCase()} thành công (vui lòng nhập tên model thủ công).`, 'success');
        }
      } else {
        const errData = await res.json();
        showToast(errData.detail || `Kết nối tới ${provider} thất bại.`, 'error');
      }
    } catch (err) {
      showToast(`Không kết nối được tới provider API.`, 'error');
    } finally {
      setModelsLoading(prev => ({ ...prev, [slotType]: false }));
    }
  };

  // Fetch models automatically when viewing slots tab
  useEffect(() => {
    if (activeTab === 'slots') {
      if (modelsList.ocr.length === 0) handleLoadModelsForSlot('ocr');
      if (modelsList.chat.length === 0) handleLoadModelsForSlot('chat');
    }
  }, [activeTab]);

  // Save slot configuration
  const handleSaveSlot = async (slotType) => {
    const provider = selectedProviders[slotType];
    const model = selectedModels[slotType].trim();

    if (!model) {
      showToast('Vui lòng chọn hoặc nhập tên model.', 'error');
      return;
    }

    setSlotsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/slots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slot: slotType,
          provider,
          model_name: model
        })
      });

      if (res.ok) {
        showToast(`Đã lưu phân công slot "${slotType.toUpperCase()}" thành công.`);
        await loadSystemConfig();
      } else {
        const data = await res.json();
        showToast(data.detail || 'Lỗi cập nhật slot configuration.', 'error');
      }
    } catch (err) {
      showToast('Lỗi kết nối lưu slot.', 'error');
    } finally {
      setSlotsLoading(false);
    }
  };

  return (
    <div className="admin-layout">

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
      {toast.show && (
        <div style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          zIndex: 9999,
          padding: '16px 24px',
          backgroundColor: toast.type === 'success' ? '#14532d' : '#7f1d1d',
          color: toast.type === 'success' ? '#dcfce7' : '#fee2e2',
          border: `1.5px solid ${toast.type === 'success' ? '#22c55e' : '#ef4444'}`,
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          boxShadow: '8px 8px 0px rgba(0,0,0,0.3)',
          transition: 'all 0.3s ease'
        }}>
          {toast.type === 'success' ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
          <span style={{ fontWeight: 'bold', fontSize: '0.95rem' }}>{toast.message}</span>
        </div>
      )}

      {/* SIDEBAR MENU */}
      <aside className={`admin-sidebar ${isMobileMenuOpen ? 'mobile-open' : ''}`}>
        <div className="admin-sidebar-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <div style={{
              width: '40px',
              height: '40px'
            }}>
              <img src="/dhv_logo.png" alt="Đại học Vinh Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
            </div>
            <div>
              <h2 style={{ fontSize: '1rem', color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>Bộ phận tuyển sinh</h2>
            </div>
          </div>
        </div>

        <nav className="admin-sidebar-menu">
          <button
            className={`menu-item ${activeTab === 'document' ? 'active' : ''}`}
            onClick={() => { setActiveTab('document'); setIsMobileMenuOpen(false); }}
          >
            <FileText size={18} />
            Nạp tài liệu tuyển sinh
          </button>

          <button
            className={`menu-item ${activeTab === 'manage' ? 'active' : ''}`}
            onClick={() => { setActiveTab('manage'); setIsMobileMenuOpen(false); }}
          >
            <FolderOpen size={18} />
            Quản lý tài liệu
          </button>

          <button
            className={`menu-item ${activeTab === 'providers' ? 'active' : ''}`}
            onClick={() => { setActiveTab('providers'); setIsMobileMenuOpen(false); }}
          >
            <Key size={18} />
            Cấu hình API Keys
          </button>

          <button
            className={`menu-item ${activeTab === 'slots' ? 'active' : ''}`}
            onClick={() => { setActiveTab('slots'); setIsMobileMenuOpen(false); }}
          >
            <Cpu size={18} />
            Cấu hình Model Slots
          </button>

          <button
            className={`menu-item ${activeTab === 'status' ? 'active' : ''}`}
            onClick={() => { setActiveTab('status'); setIsMobileMenuOpen(false); }}
          >
            <Activity size={18} />
            Trạng thái hệ thống
          </button>
        </nav>

        <div className="admin-sidebar-footer">
          <button
            onClick={() => navigate('/')}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '12px',
              backgroundColor: 'var(--bg-main)',
              color: 'var(--text-main)',
              border: '1.5px solid var(--border-color)',
              fontSize: '0.88rem',
              fontWeight: 'bold'
            }}
            onMouseOver={e => e.currentTarget.style.backgroundColor = 'var(--border-color)'}
            onMouseOut={e => e.currentTarget.style.backgroundColor = 'var(--bg-main)'}
          >
            <ArrowLeft size={16} />
            QUAY LẠI CHATBOT
          </button>
        </div>
      </aside>

      {/* MAIN CONTAINER */}
      <div className="admin-main">
        {/* HEADER */}
        <header className="admin-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              className="mobile-toggle"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              style={{
                background: 'none',
                color: 'var(--text-main)',
                padding: '8px',
                display: 'none',
              }}
            >
              {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
            <style>{`
              @media (max-width: 992px) {
                .mobile-toggle { display: block !important; }
              }
            `}</style>
            <div>
              <h1 style={{ fontSize: '1.25rem', color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                {activeTab === 'document' && 'Nạp tài liệu tuyển sinh'}
                {activeTab === 'manage' && 'Quản lý danh sách tài liệu'}
                {activeTab === 'providers' && 'Cấu hình API Credentials'}
                {activeTab === 'slots' && 'Phân chia nhiệm vụ Slots'}
                {activeTab === 'status' && 'Trạng thái tích hợp'}
              </h1>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{
              fontSize: '0.8rem',
              backgroundColor: '#e2e8f0',
              padding: '4px 10px',
              fontWeight: 'bold',
              color: 'var(--text-main)'
            }}>
              POSTGRES ONLINE
            </div>
          </div>
        </header>

        {/* CONTENT BODY */}
        <main className="admin-body">

          {/* TAB 1: UPLOAD DOCUMENT */}
          {activeTab === 'document' && (
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

                  {/* Thực tế ẩn input file */}
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
                          justifyContent: 'center'
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
                    gap: '12px'
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

              {/* ── BẢNG LỊCH SỬ NẠP TÀI LIỆU ── */}
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
                    Lịch sử nạp tài liệu tri thức
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
                          {['Tên tài liệu', 'Năm', 'Thời điểm nạp', 'Trạng thái', 'Kết quả / Mô tả'].map(h => (
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
          )}

          {/* TAB: QUẢN LÝ TÀI LIỆU */}
          {activeTab === 'manage' && (
            <div className="admin-card">
              <div style={{ borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
                <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase' }}>Quản lý Danh sách Tài liệu</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                  Xem toàn bộ tài liệu đã nạp. Thao tác <strong style={{ color: '#dc2626' }}>Xóa</strong> sẽ xóa vĩnh viễn file gốc, ảnh OCR, dữ liệu vector trong Qdrant và bản ghi trong Database.
                </p>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '16px' }}>
                <button
                  id="btn-refresh-docs"
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
                            <td style={{ padding: '12px 14px', color: 'var(--text-muted)', fontSize: '0.82rem', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
                </div>
              )}

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

          {/* TAB 2: PROVIDERS CREDENTIALS */}
          {activeTab === 'providers' && (
            <div className="admin-card">
              <div style={{ borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
                <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase' }}>Cấu hình API Keys</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                  Cung cấp API keys để kích hoạt các model AI. Khóa bảo mật được mã hóa lưu trữ.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
                {PROVIDERS_LIST.map((provider) => {
                  const dbInfo = providersData.find(p => p.provider === provider.id) || {};
                  return (
                    <div
                      key={provider.id}
                      style={{
                        padding: '24px',
                        border: '1.5px solid var(--border-color)',
                        backgroundColor: '#f8fafc',
                        position: 'relative'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                        <span style={{ fontWeight: 'bold', fontSize: '1.1rem', color: provider.color }}>
                          {provider.label}
                        </span>
                        <span style={{
                          fontSize: '0.75rem',
                          padding: '4px 10px',
                          fontWeight: 'bold',
                          backgroundColor: dbInfo.has_key ? '#dcfce7' : '#f1f5f9',
                          color: dbInfo.has_key ? '#166534' : 'var(--text-muted)',
                          border: `1px solid ${dbInfo.has_key ? '#22c55e' : 'var(--border-color)'}`
                        }}>
                          {dbInfo.has_key ? 'ĐÃ ĐƯỢC THIẾT LẬP KEY' : 'CHƯA CÓ KEY'}
                        </span>
                      </div>

                      {provider.needsEndpoint && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
                          <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>VLLM SERVER URL ENDPOINT</label>
                          <input
                            type="text"
                            placeholder="Ví dụ: http://10.0.0.5:8080"
                            value={providerEndpoints[provider.id] || ''}
                            onChange={e => setProviderEndpoints(prev => ({ ...prev, [provider.id]: e.target.value }))}
                            style={{
                              border: '1.5px solid var(--border-color)',
                              padding: '10px 14px',
                              backgroundColor: '#ffffff',
                              fontSize: '0.9rem',
                              width: '100%'
                            }}
                          />
                        </div>
                      )}

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
                        <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>
                          API KEY {dbInfo.has_key && '(Nhập mới nếu muốn thay đổi khóa cũ)'}
                        </label>
                        <input
                          type="password"
                          placeholder="••••••••••••••••"
                          value={providerKeys[provider.id]}
                          onChange={e => setProviderKeys(prev => ({ ...prev, [provider.id]: e.target.value }))}
                          style={{
                            border: '1.5px solid var(--border-color)',
                            padding: '10px 14px',
                            backgroundColor: '#ffffff',
                            fontSize: '0.9rem',
                            width: '100%'
                          }}
                        />
                      </div>

                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          onClick={() => handleSaveProvider(provider.id)}
                          disabled={provLoading}
                          style={{
                            backgroundColor: 'var(--primary-blue)',
                            color: '#ffffff',
                            padding: '10px 20px',
                            fontWeight: 'bold',
                            fontSize: '0.85rem'
                          }}
                        >
                          LƯU CREDENTIALS
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 3: SLOTS CONFIGURATIONS */}
          {activeTab === 'slots' && (
            <div className="admin-card">
              <div style={{ borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
                <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase' }}>Phân công nhiệm vụ LLM</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                  Phân phối model AI cụ thể cho 2 công đoạn: OCR trích xuất PDF và Chat suy luận RAG.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }} className="slot-grid-layout">
                {/* SLOT OCR */}
                <div style={{ padding: '24px', border: '1.5px solid var(--border-color)', backgroundColor: '#f8fafc' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--primary-blue)', letterSpacing: '0.5px', marginBottom: '4px' }}>SLOT 1</div>
                  <h4 style={{ fontSize: '1.1rem', marginBottom: '12px' }}>📄 OCR (Đọc & trích xuất PDF)</h4>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div>
                      <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>CHỌN PROVIDER</label>
                      <select
                        value={selectedProviders.ocr}
                        onChange={e => {
                          const val = e.target.value;
                          setSelectedProviders(prev => ({ ...prev, ocr: val }));
                          handleLoadModelsForSlot('ocr', val);
                        }}
                        style={{
                          border: '1.5px solid var(--border-color)',
                          padding: '10px 14px',
                          backgroundColor: '#ffffff',
                          fontSize: '0.9rem',
                          width: '100%',
                          marginTop: '4px'
                        }}
                      >
                        {PROVIDERS_LIST.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
                      </select>
                    </div>

                    <div>
                      <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>MODEL NAME</label>
                      {selectedProviders.ocr === 'vllm' ? (
                        <input
                          type="text"
                          placeholder="Ví dụ: Qwen/Qwen2.5-32B-Instruct"
                          value={selectedModels.ocr}
                          onChange={e => setSelectedModels(prev => ({ ...prev, ocr: e.target.value }))}
                          style={{
                            border: '1.5px solid var(--border-color)',
                            padding: '10px 14px',
                            backgroundColor: '#ffffff',
                            fontSize: '0.9rem',
                            width: '100%',
                            marginTop: '4px'
                          }}
                        />
                      ) : (
                        <>
                          <select
                            value={selectedModels.ocr}
                            onChange={e => setSelectedModels(prev => ({ ...prev, ocr: e.target.value }))}
                            disabled={modelsLoading.ocr}
                            style={{
                              border: '1.5px solid var(--border-color)',
                              padding: '10px 14px',
                              backgroundColor: '#ffffff',
                              fontSize: '0.9rem',
                              width: '100%',
                              marginTop: '4px'
                            }}
                          >
                            <option value="">-- Chọn Model --</option>
                            {modelsList.ocr.map(m => (
                              <option key={m} value={m}>{m}</option>
                            ))}
                            {selectedModels.ocr && !modelsList.ocr.includes(selectedModels.ocr) && (
                              <option value={selectedModels.ocr}>{selectedModels.ocr} (đang sử dụng)</option>
                            )}
                          </select>
                          {modelsLoading.ocr && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--primary-blue)', marginTop: '4px' }}>Đang tải danh sách model...</div>
                          )}
                        </>
                      )}
                    </div>

                    <button
                      onClick={() => handleSaveSlot('ocr')}
                      disabled={slotsLoading}
                      style={{
                        backgroundColor: 'var(--primary-blue)',
                        color: '#ffffff',
                        padding: '12px 24px',
                        fontWeight: 'bold',
                        fontSize: '0.9rem',
                        marginTop: '8px'
                      }}
                    >
                      LƯU CẤU HÌNH OCR
                    </button>
                  </div>
                </div>

                {/* SLOT CHAT */}
                <div style={{ padding: '24px', border: '1.5px solid var(--border-color)', backgroundColor: '#f8fafc' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--primary-blue)', letterSpacing: '0.5px', marginBottom: '4px' }}>SLOT 2</div>
                  <h4 style={{ fontSize: '1.1rem', marginBottom: '12px' }}>💬 Chat (Suy luận RAG)</h4>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div>
                      <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>CHỌN PROVIDER</label>
                      <select
                        value={selectedProviders.chat}
                        onChange={e => {
                          const val = e.target.value;
                          setSelectedProviders(prev => ({ ...prev, chat: val }));
                          handleLoadModelsForSlot('chat', val);
                        }}
                        style={{
                          border: '1.5px solid var(--border-color)',
                          padding: '10px 14px',
                          backgroundColor: '#ffffff',
                          fontSize: '0.9rem',
                          width: '100%',
                          marginTop: '4px'
                        }}
                      >
                        {PROVIDERS_LIST.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
                      </select>
                    </div>

                    <div>
                      <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>MODEL NAME</label>
                      {selectedProviders.chat === 'vllm' ? (
                        <input
                          type="text"
                          placeholder="Ví dụ: Qwen/Qwen2.5-32B-Instruct"
                          value={selectedModels.chat}
                          onChange={e => setSelectedModels(prev => ({ ...prev, chat: e.target.value }))}
                          style={{
                            border: '1.5px solid var(--border-color)',
                            padding: '10px 14px',
                            backgroundColor: '#ffffff',
                            fontSize: '0.9rem',
                            width: '100%',
                            marginTop: '4px'
                          }}
                        />
                      ) : (
                        <>
                          <select
                            value={selectedModels.chat}
                            onChange={e => setSelectedModels(prev => ({ ...prev, chat: e.target.value }))}
                            disabled={modelsLoading.chat}
                            style={{
                              border: '1.5px solid var(--border-color)',
                              padding: '10px 14px',
                              backgroundColor: '#ffffff',
                              fontSize: '0.9rem',
                              width: '100%',
                              marginTop: '4px'
                            }}
                          >
                            <option value="">-- Chọn Model --</option>
                            {modelsList.chat.map(m => (
                              <option key={m} value={m}>{m}</option>
                            ))}
                            {selectedModels.chat && !modelsList.chat.includes(selectedModels.chat) && (
                              <option value={selectedModels.chat}>{selectedModels.chat} (đang sử dụng)</option>
                            )}
                          </select>
                          {modelsLoading.chat && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--primary-blue)', marginTop: '4px' }}>Đang tải danh sách model...</div>
                          )}
                        </>
                      )}
                    </div>

                    <button
                      onClick={() => handleSaveSlot('chat')}
                      disabled={slotsLoading}
                      style={{
                        backgroundColor: 'var(--primary-blue)',
                        color: '#ffffff',
                        padding: '12px 24px',
                        fontWeight: 'bold',
                        fontSize: '0.9rem',
                        marginTop: '8px'
                      }}
                    >
                      LƯU CẤU HÌNH CHAT
                    </button>
                  </div>
                </div>
              </div>

              <style>{`
                .spin-anim {
                  animation: spin 1s linear infinite;
                }
                @keyframes spin {
                  100% { transform: rotate(360deg); }
                }
                @media (max-width: 768px) {
                  .slot-grid-layout { grid-template-columns: 1fr !important; }
                }
              `}</style>
            </div>
          )}

          {/* TAB 4: SYSTEM STATUS */}
          {activeTab === 'status' && (
            <div className="admin-card">
              <div style={{ borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
                <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase' }}>Cấu hình đang chạy trong DB</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                  Phản ánh trạng thái thiết lập model hiện tại. Đọc trực tiếp từ PostgreSQL Database.
                </p>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border-color)' }}>
                      <th style={{ textAlign: 'left', padding: '12px', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>SLOT NHIỆM VỤ</th>
                      <th style={{ textAlign: 'left', padding: '12px', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>LLM PROVIDER</th>
                      <th style={{ textAlign: 'left', padding: '12px', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>MODEL ĐANG DÙNG</th>
                      <th style={{ textAlign: 'left', padding: '12px', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>THỜI GIAN CẬP NHẬT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slotsData.length === 0 ? (
                      <tr>
                        <td colSpan="4" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                          Chưa có cấu hình slots nào được thiết lập.
                        </td>
                      </tr>
                    ) : (
                      slotsData.map((slot) => (
                        <tr key={slot.slot} style={{ borderBottom: '1px solid var(--border-color)' }}>
                          <td style={{ padding: '12px', fontWeight: 'bold', textTransform: 'uppercase' }}>{slot.slot}</td>
                          <td style={{ padding: '12px' }}>
                            <span style={{
                              backgroundColor: 'var(--bg-main)',
                              padding: '4px 8px',
                              fontWeight: '500',
                              fontSize: '0.85rem'
                            }}>
                              {slot.provider.toUpperCase()}
                            </span>
                          </td>
                          <td style={{ padding: '12px', fontFamily: 'monospace', fontWeight: '600', color: 'var(--primary-blue)' }}>
                            {slot.model_name}
                          </td>
                          <td style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                            {slot.updated_at ? new Date(slot.updated_at).toLocaleString('vi-VN') : '—'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  );
}
