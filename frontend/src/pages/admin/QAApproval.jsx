import React, { useState, useEffect } from 'react';
import { message, Tabs, Tooltip } from 'antd';
import { CheckCircle2, Trash2, Upload, Loader2, RefreshCw, X, Save, Clock, ShieldCheck } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DeleteConfirmModal from '../../components/admin/DeleteConfirmModal';
import MarkdownEditor from '../../components/admin/MarkdownEditor';

export default function QAApproval() {
  const { showToast } = useOutletContext();
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  const [activeTab, setActiveTab] = useState('staging');
  
  // Staging Data State
  const [stagingData, setStagingData] = useState([]);
  const [stagingLoading, setStagingLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [sseStatus, setSseStatus] = useState('connecting');
  const [editingCell, setEditingCell] = useState(null); // { id, field }
  const [editValue, setEditValue] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Approved Data State
  const [approvedData, setApprovedData] = useState([]);
  const [approvedLoading, setApprovedLoading] = useState(false);
  const [importing, setImporting] = useState(false);

  // Delete Modal State
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, type: '', id: null, isDeleting: false });

  // Bulk Select States
  const [selectedStaging, setSelectedStaging] = useState([]);
  const [selectedApproved, setSelectedApproved] = useState([]);

  // FETCH STAGING DATA
  const fetchStagingData = async (page = 1, pageSize = 20) => {
    setStagingLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const res = await fetch(`${API_URL}/api/admin/qa-staging?skip=${skip}&limit=${pageSize}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
      });
      const json = await res.json();
      if (res.ok) {
        setStagingData(json.data || []);
        setPagination(prev => ({ ...prev, current: page, total: json.total, pageSize }));
        setSelectedStaging([]);
      } else {
        message.error(json.detail || 'Lỗi khi tải danh sách chờ duyệt');
      }
    } catch (error) {
      message.error('Lỗi khi tải dữ liệu');
    } finally {
      setStagingLoading(false);
    }
  };

  // FETCH APPROVED DATA
  const fetchApprovedData = async () => {
    setApprovedLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/qa-approved`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
      });
      const json = await res.json();
      if (res.ok) {
        setApprovedData(json.data || []);
        setSelectedApproved([]);
      } else {
        message.error(json.detail || 'Lỗi khi tải danh sách đã duyệt');
      }
    } catch (error) {
      message.error('Lỗi kết nối khi tải danh sách đã duyệt');
    } finally {
      setApprovedLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'staging') {
      fetchStagingData(pagination.current, pagination.pageSize);
    } else {
      fetchApprovedData();
    }
  }, [activeTab]);

  // SSE FOR STAGING
  useEffect(() => {
    const eventSource = new EventSource(`${API_URL}/api/admin/qa-staging/stream`);
    eventSource.onopen = () => setSseStatus('connected');
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event === 'new_qa' && activeTab === 'staging') {
          fetchStagingData(pagination.current, pagination.pageSize);
        }
      } catch (error) {
        console.error('Lỗi parse SSE:', error);
      }
    };
    eventSource.onerror = () => setSseStatus('error');
    return () => eventSource.close();
  }, [activeTab, pagination.current, pagination.pageSize]);


  // INLINE EDITING
  const handleEditClick = (record, field) => {
    setEditingCell({ id: record.id, field });
    setEditValue(record[field]);
  };

  const handleSaveEdit = async (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (!editingCell) return;
    setIsSaving(true);
    try {
      const { id, field } = editingCell;
      const payload = { [field]: editValue };
      
      const endpoint = activeTab === 'staging' 
        ? `${API_URL}/api/admin/qa-staging/${id}`
        : `${API_URL}/api/admin/qa-approved/${id}`;
        
      const res = await fetch(endpoint, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(payload)
      });
      
      const json = await res.json();
      if (res.ok) {
        showToast('Đã lưu nội dung cập nhật', 'success');
        if (activeTab === 'staging') {
          setStagingData(prev => prev.map(item => item.id === id ? { ...item, ...payload } : item));
        } else {
          setApprovedData(prev => prev.map(item => item.id === id ? { ...item, ...payload } : item));
        }
        setEditingCell(null);
      } else {
        showToast(json.detail || 'Lỗi cập nhật', 'error');
      }
    } catch (error) {
      showToast('Lỗi mạng khi cập nhật', 'error');
    } finally {
      setIsSaving(false);
      setEditingCell(null);
    }
  };

  const handleCancelEdit = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setEditingCell(null);
    setEditValue("");
  };

  // ACTIONS: APPROVE / REJECT STAGING
  const handleApprove = async (id) => {
    try {
      const res = await fetch(`${API_URL}/api/admin/qa-staging/${id}/approve`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
      });
      if (res.ok) {
        showToast('Đã duyệt vào Semantic Cache', 'success');
        fetchStagingData(pagination.current, pagination.pageSize);
        fetchApprovedData(); // Lấy dữ liệu mới cho tab approved
      } else {
        const json = await res.json();
        showToast(json.detail || 'Lỗi khi duyệt', 'error');
      }
    } catch (error) {
      showToast('Lỗi mạng', 'error');
    }
  };

  const handleReject = async (id) => {
    setDeleteModal(prev => ({ ...prev, isDeleting: true }));
    try {
      const res = await fetch(`${API_URL}/api/admin/qa-staging/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
      });
      if (res.ok) {
        showToast('Đã xóa bản ghi', 'success');
        fetchStagingData(pagination.current, pagination.pageSize);
      } else {
        showToast('Lỗi khi xóa', 'error');
      }
    } catch (error) {
      showToast('Lỗi mạng', 'error');
    } finally {
      setDeleteModal({ isOpen: false, type: '', id: null, isDeleting: false });
    }
  };

  // ACTIONS: DELETE APPROVED
  const handleDeleteApproved = async (id) => {
    setDeleteModal(prev => ({ ...prev, isDeleting: true }));
    try {
      const res = await fetch(`${API_URL}/api/admin/qa-approved/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
      });
      if (res.ok) {
        showToast('Đã xóa khỏi Vector DB', 'success');
        fetchApprovedData();
      } else {
        showToast('Lỗi khi xóa', 'error');
      }
    } catch (error) {
      showToast('Lỗi mạng', 'error');
    } finally {
      setDeleteModal({ isOpen: false, type: '', id: null, isDeleting: false });
    }
  };

  const confirmDelete = () => {
    if (deleteModal.type === 'staging') handleReject(deleteModal.id);
    else if (deleteModal.type === 'approved') handleDeleteApproved(deleteModal.id);
    else if (deleteModal.type === 'staging_bulk') handleBulkRejectStaging();
    else if (deleteModal.type === 'approved_bulk') handleBulkDeleteApproved();
  };

  const handleBulkRejectStaging = async () => {
    setDeleteModal(prev => ({ ...prev, isDeleting: true }));
    try {
      const res = await fetch(`${API_URL}/api/admin/qa-staging/bulk-delete`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ ids: selectedStaging })
      });
      if (res.ok) {
        showToast(`Đã xóa ${selectedStaging.length} bản ghi`, 'success');
        setSelectedStaging([]);
        fetchStagingData(pagination.current, pagination.pageSize);
      } else {
        showToast('Lỗi khi xóa hàng loạt', 'error');
      }
    } catch (error) {
      showToast('Lỗi mạng', 'error');
    } finally {
      setDeleteModal({ isOpen: false, type: '', id: null, isDeleting: false });
    }
  };

  const handleBulkDeleteApproved = async () => {
    setDeleteModal(prev => ({ ...prev, isDeleting: true }));
    try {
      const res = await fetch(`${API_URL}/api/admin/qa-approved/bulk-delete`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ ids: selectedApproved })
      });
      if (res.ok) {
        showToast(`Đã xóa ${selectedApproved.length} Q&A`, 'success');
        setSelectedApproved([]);
        fetchApprovedData();
      } else {
        showToast('Lỗi khi xóa hàng loạt', 'error');
      }
    } catch (error) {
      showToast('Lỗi mạng', 'error');
    } finally {
      setDeleteModal({ isOpen: false, type: '', id: null, isDeleting: false });
    }
  };

  // ACTIONS: IMPORT EXCEL
  const handleImportExcel = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setImporting(true);
    const form = new FormData();
    form.append('file', file);

    try {
      const res = await fetch(`${API_URL}/api/admin/qa-approved/import`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
        body: form
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message, 'success');
        fetchApprovedData();
      } else {
        showToast(data.detail || 'Lỗi import file', 'error');
      }
    } catch (error) {
      showToast('Lỗi mạng khi import', 'error');
    } finally {
      setImporting(false);
      e.target.value = ''; // Reset input
    }
  };

  // PAGINATION
  const handleNextPage = () => {
    if (pagination.current * pagination.pageSize < pagination.total) {
      fetchStagingData(pagination.current + 1, pagination.pageSize);
    }
  };

  const handlePrevPage = () => {
    if (pagination.current > 1) {
      fetchStagingData(pagination.current - 1, pagination.pageSize);
    }
  };

  return (
    <div className="admin-card" style={{ padding: '0', backgroundColor: 'transparent', boxShadow: 'none' }}>
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '24px' }}>
        
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Kiểm duyệt Q&A Cache</h3>
              {sseStatus === 'connected' && (
                <Tooltip title="Đang kết nối Realtime (SSE)">
                  <div className="flex items-center gap-2 bg-emerald-50 text-emerald-600 px-3 py-1 rounded-full text-xs font-medium border border-emerald-200">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                    </span>
                    Live
                  </div>
                </Tooltip>
              )}
              {sseStatus === 'error' && (
                <Tooltip title="Mất kết nối Realtime, đang thử lại...">
                  <div className="flex items-center gap-2 bg-red-50 text-red-600 px-3 py-1 rounded-full text-xs font-medium border border-red-200">
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                    Disconnected
                  </div>
                </Tooltip>
              )}
            </div>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
              Duyệt, chỉnh sửa và quản lý lịch sử hỏi đáp lưu trữ trong Semantic Cache (Vector DB).
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            {activeTab === 'staging' && selectedStaging.length > 0 && (
              <button 
                onClick={() => setDeleteModal({ isOpen: true, type: 'staging_bulk', id: null, isDeleting: false })} 
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#ef4444', color: 'white', borderRadius: '6px', border: 'none', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500 }}
              >
                <Trash2 size={16} /> Xóa {selectedStaging.length} mục
              </button>
            )}

            {activeTab === 'approved' && selectedApproved.length > 0 && (
              <button 
                onClick={() => setDeleteModal({ isOpen: true, type: 'approved_bulk', id: null, isDeleting: false })} 
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#ef4444', color: 'white', borderRadius: '6px', border: 'none', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500 }}
              >
                <Trash2 size={16} /> Xóa {selectedApproved.length} mục
              </button>
            )}

            <button 
              onClick={() => activeTab === 'staging' ? fetchStagingData(pagination.current, pagination.pageSize) : fetchApprovedData()} 
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#f1f5f9', color: '#475569', borderRadius: '6px', border: '1px solid #cbd5e1', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500 }}
            >
              <RefreshCw size={16} /> Làm mới
            </button>

            {activeTab === 'approved' && (
              <div style={{ position: 'relative' }}>
                <input
                  type="file"
                  accept=".xlsx, .xls"
                  id="upload-excel"
                  style={{ display: 'none' }}
                  onChange={handleImportExcel}
                  disabled={importing}
                />
                <label
                  htmlFor="upload-excel"
                  style={{
                    display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px',
                    backgroundColor: '#10b981', color: 'white', borderRadius: '6px', cursor: importing ? 'not-allowed' : 'pointer', fontWeight: '500', transition: 'background-color 0.2s', opacity: importing ? 0.7 : 1
                  }}
                >
                  {importing ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
                  {importing ? 'Đang Import...' : 'Import Excel'}
                </label>
              </div>
            )}
          </div>
        </div>

        {/* Tabs */}
        <Tabs 
          activeKey={activeTab} 
          onChange={(key) => setActiveTab(key)} 
          items={[
            { key: 'staging', label: <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Clock size={16} /> Chờ duyệt</span> },
            { key: 'approved', label: <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><ShieldCheck size={16} /> Đã duyệt</span> }
          ]} 
        />

        {/* TAB: CHỜ DUYỆT */}
        {activeTab === 'staging' && (
          <div style={{ overflowX: 'auto' }}>
            {stagingLoading && stagingData.length === 0 ? (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Đang tải dữ liệu...</div>
            ) : (
              <>
                <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid #e2e8f0', fontSize: '0.95rem' }}>
                  <thead>
                    <tr style={{ backgroundColor: '#f8fafc' }}>
                      <th style={{ border: '1px solid #e2e8f0', padding: '14px 16px', width: '40px', textAlign: 'center' }}>
                        <input 
                          type="checkbox" 
                          checked={stagingData.length > 0 && selectedStaging.length === stagingData.length}
                          onChange={(e) => setSelectedStaging(e.target.checked ? stagingData.map(d => d.id) : [])}
                          style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                        />
                      </th>
                      <th style={{ border: '1px solid #e2e8f0', padding: '14px 16px', width: '35%', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Câu hỏi (User)</th>
                      <th style={{ border: '1px solid #e2e8f0', padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Câu trả lời (Bot)</th>
                      <th style={{ border: '1px solid #e2e8f0', padding: '14px 16px', width: '150px', textAlign: 'center', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Tác vụ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stagingData.length === 0 ? (
                      <tr>
                        <td colSpan="4" style={{ border: '1px solid #e2e8f0', padding: '30px', textAlign: 'center', color: '#64748b' }}>Không có câu hỏi nào chờ duyệt.</td>
                      </tr>
                    ) : (
                      stagingData.map(record => (
                        <tr key={record.id} style={{ transition: 'background 0.2s', backgroundColor: selectedStaging.includes(record.id) ? '#f1f5f9' : '#fff' }} onMouseOver={e => e.currentTarget.style.backgroundColor = '#f8fafc'} onMouseOut={e => e.currentTarget.style.backgroundColor = selectedStaging.includes(record.id) ? '#f1f5f9' : '#fff'}>
                          <td style={{ border: '1px solid #e2e8f0', padding: '14px 16px', textAlign: 'center' }}>
                            <input 
                              type="checkbox" 
                              checked={selectedStaging.includes(record.id)}
                              onChange={(e) => {
                                if (e.target.checked) setSelectedStaging([...selectedStaging, record.id]);
                                else setSelectedStaging(selectedStaging.filter(id => id !== record.id));
                              }}
                              style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                            />
                          </td>
                          
                          {/* Khối chỉnh sửa Câu hỏi */}
                          <td style={{ border: '1px solid #e2e8f0', padding: '14px 16px', cursor: 'pointer', verticalAlign: 'top' }} onClick={() => editingCell?.id !== record.id && handleEditClick(record, 'question')}>
                            {editingCell?.id === record.id && editingCell?.field === 'question' ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }} onClick={e => e.stopPropagation()}>
                                <MarkdownEditor 
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  autoFocus={true}
                                  style={{ minHeight: '100px' }}
                                />
                                <div style={{ display: 'flex', gap: '8px' }}>
                                  <button onClick={(e) => handleSaveEdit(e)} disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}><Save size={14}/> Lưu</button>
                                  <button onClick={(e) => handleCancelEdit(e)} disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}><X size={14}/> Hủy</button>
                                </div>
                              </div>
                            ) : (
                              <Tooltip title="Nhấn để chỉnh sửa">
                                <div className="markdown-body" style={{ lineHeight: '1.5', minHeight: '40px', wordBreak: 'break-word' }}>
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{record.question}</ReactMarkdown>
                                </div>
                              </Tooltip>
                            )}
                          </td>

                          {/* Khối chỉnh sửa Câu trả lời */}
                          <td style={{ border: '1px solid #e2e8f0', padding: '14px 16px', cursor: 'pointer', verticalAlign: 'top' }} onClick={() => editingCell?.id !== record.id && handleEditClick(record, 'answer')}>
                            {editingCell?.id === record.id && editingCell?.field === 'answer' ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }} onClick={e => e.stopPropagation()}>
                                <MarkdownEditor 
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  autoFocus={true}
                                  style={{ minHeight: '150px' }}
                                />
                                <div style={{ display: 'flex', gap: '8px' }}>
                                  <button onClick={(e) => handleSaveEdit(e)} disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}><Save size={14}/> Lưu</button>
                                  <button onClick={(e) => handleCancelEdit(e)} disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}><X size={14}/> Hủy</button>
                                </div>
                              </div>
                            ) : (
                              <Tooltip title="Nhấn để chỉnh sửa">
                                <div className="markdown-body" style={{ lineHeight: '1.5', minHeight: '40px', wordBreak: 'break-word' }}>
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{record.answer}</ReactMarkdown>
                                </div>
                              </Tooltip>
                            )}
                          </td>

                          {/* Tác vụ */}
                          <td style={{ border: '1px solid #e2e8f0', padding: '14px 16px', textAlign: 'center' }}>
                            <div style={{ display: 'flex', gap: '8px', justifyContent: 'center' }}>
                              <button onClick={() => handleApprove(record.id)} style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', backgroundColor: '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }} title="Duyệt đưa vào Cache">
                                <CheckCircle2 size={16} /> Duyệt
                              </button>
                              <button onClick={() => setDeleteModal({ isOpen: true, type: 'staging', id: record.id, isDeleting: false })} style={{ display: 'flex', alignItems: 'center', padding: '6px 8px', backgroundColor: '#fef2f2', color: '#ef4444', border: '1px solid #fee2e2', borderRadius: '6px', cursor: 'pointer' }} title="Xóa bỏ">
                                <Trash2 size={16} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                
                {/* Pagination Controls for Staging */}
                {pagination.total > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', borderTop: '1px solid #e2e8f0', marginTop: '16px' }}>
                    <span style={{ fontSize: '0.9rem', color: '#64748b' }}>
                      Đang xem {((pagination.current - 1) * pagination.pageSize) + 1} - {Math.min(pagination.current * pagination.pageSize, pagination.total)} trong số {pagination.total} bản ghi
                    </span>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button onClick={handlePrevPage} disabled={pagination.current === 1} style={{ padding: '6px 12px', border: '1px solid #cbd5e1', borderRadius: '4px', backgroundColor: 'white', cursor: pagination.current === 1 ? 'not-allowed' : 'pointer', color: pagination.current === 1 ? '#94a3b8' : '#334155' }}>
                        Trang trước
                      </button>
                      <button onClick={handleNextPage} disabled={pagination.current * pagination.pageSize >= pagination.total} style={{ padding: '6px 12px', border: '1px solid #cbd5e1', borderRadius: '4px', backgroundColor: 'white', cursor: pagination.current * pagination.pageSize >= pagination.total ? 'not-allowed' : 'pointer', color: pagination.current * pagination.pageSize >= pagination.total ? '#94a3b8' : '#334155' }}>
                        Trang tiếp
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* TAB: ĐÃ DUYỆT */}
        {activeTab === 'approved' && (
          <div style={{ overflowX: 'auto' }}>
            {approvedLoading ? (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Đang tải dữ liệu...</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid #e2e8f0', fontSize: '0.95rem' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8fafc' }}>
                    <th style={{ border: '1px solid #e2e8f0', padding: '14px 16px', width: '40px', textAlign: 'center' }}>
                      <input 
                        type="checkbox" 
                        checked={approvedData.length > 0 && selectedApproved.length === approvedData.length}
                        onChange={(e) => setSelectedApproved(e.target.checked ? approvedData.map(d => d.id) : [])}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                    </th>
                    <th style={{ border: '1px solid #e2e8f0', padding: '14px 16px', width: '35%', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Câu hỏi (User)</th>
                    <th style={{ border: '1px solid #e2e8f0', padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Câu trả lời (Bot)</th>
                    <th style={{ border: '1px solid #e2e8f0', padding: '14px 16px', width: '150px', textAlign: 'center', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Ngày duyệt</th>
                    <th style={{ border: '1px solid #e2e8f0', padding: '14px 16px', width: '100px', textAlign: 'center', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Tác vụ</th>
                  </tr>
                </thead>
                <tbody>
                  {approvedData.length === 0 ? (
                    <tr>
                      <td colSpan="5" style={{ border: '1px solid #e2e8f0', padding: '30px', textAlign: 'center', color: '#64748b' }}>Không có câu hỏi nào đã duyệt.</td>
                    </tr>
                  ) : (
                    approvedData.map(record => (
                      <tr key={record.id} style={{ transition: 'background 0.2s', backgroundColor: selectedApproved.includes(record.id) ? '#f1f5f9' : '#fff' }} onMouseOver={e => e.currentTarget.style.backgroundColor = '#f8fafc'} onMouseOut={e => e.currentTarget.style.backgroundColor = selectedApproved.includes(record.id) ? '#f1f5f9' : '#fff'}>
                        <td style={{ border: '1px solid #e2e8f0', padding: '14px 16px', textAlign: 'center' }}>
                          <input 
                            type="checkbox" 
                            checked={selectedApproved.includes(record.id)}
                            onChange={(e) => {
                              if (e.target.checked) setSelectedApproved([...selectedApproved, record.id]);
                              else setSelectedApproved(selectedApproved.filter(id => id !== record.id));
                            }}
                            style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                          />
                        </td>
                        {/* Khối chỉnh sửa Câu hỏi (Đã duyệt) */}
                        <td style={{ border: '1px solid #e2e8f0', padding: '14px 16px', cursor: 'pointer', verticalAlign: 'top' }} onClick={() => editingCell?.id !== record.id && handleEditClick(record, 'question')}>
                          {editingCell?.id === record.id && editingCell?.field === 'question' ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }} onClick={e => e.stopPropagation()}>
                              <MarkdownEditor 
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                autoFocus={true}
                                style={{ minHeight: '100px' }}
                              />
                              <div style={{ display: 'flex', gap: '8px' }}>
                                <button onClick={(e) => handleSaveEdit(e)} disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}><Save size={14}/> Lưu</button>
                                <button onClick={(e) => handleCancelEdit(e)} disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}><X size={14}/> Hủy</button>
                              </div>
                            </div>
                          ) : (
                            <Tooltip title="Nhấn để chỉnh sửa">
                              <div className="markdown-body" style={{ lineHeight: '1.5', minHeight: '40px', wordBreak: 'break-word' }}>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{record.question}</ReactMarkdown>
                              </div>
                            </Tooltip>
                          )}
                        </td>

                        {/* Khối chỉnh sửa Câu trả lời (Đã duyệt) */}
                        <td style={{ border: '1px solid #e2e8f0', padding: '14px 16px', cursor: 'pointer', verticalAlign: 'top' }} onClick={() => editingCell?.id !== record.id && handleEditClick(record, 'answer')}>
                          {editingCell?.id === record.id && editingCell?.field === 'answer' ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }} onClick={e => e.stopPropagation()}>
                              <MarkdownEditor 
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                autoFocus={true}
                                style={{ minHeight: '150px' }}
                              />
                              <div style={{ display: 'flex', gap: '8px' }}>
                                <button onClick={(e) => handleSaveEdit(e)} disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}><Save size={14}/> Lưu</button>
                                <button onClick={(e) => handleCancelEdit(e)} disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}><X size={14}/> Hủy</button>
                              </div>
                            </div>
                          ) : (
                            <Tooltip title="Nhấn để chỉnh sửa">
                              <div className="markdown-body" style={{ lineHeight: '1.5', minHeight: '40px', wordBreak: 'break-word' }}>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{record.answer}</ReactMarkdown>
                              </div>
                            </Tooltip>
                          )}
                        </td>

                        <td style={{ border: '1px solid #e2e8f0', padding: '14px 16px', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
                          {record.created_at ? new Date(record.created_at).toLocaleDateString('vi-VN') : '-'}
                        </td>
                        <td style={{ border: '1px solid #e2e8f0', padding: '14px 16px', textAlign: 'center' }}>
                          <button onClick={() => setDeleteModal({ isOpen: true, type: 'approved', id: record.id, isDeleting: false })} style={{ padding: '6px 8px', backgroundColor: '#fef2f2', color: '#ef4444', border: '1px solid #fee2e2', borderRadius: '6px', cursor: 'pointer' }} title="Xóa khỏi Vector DB">
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}
          </div>
        )}

      </div>

      <DeleteConfirmModal
        isOpen={deleteModal.isOpen}
        onClose={() => setDeleteModal({ isOpen: false, type: '', id: null, isDeleting: false })}
        onConfirm={confirmDelete}
        title={deleteModal.type.includes('bulk') ? "Xác nhận xóa hàng loạt" : "Xác nhận xóa"}
        description={
          deleteModal.type === 'staging_bulk' ? `Bạn có chắc chắn muốn xóa vĩnh viễn ${selectedStaging.length} câu hỏi khỏi danh sách chờ duyệt?` :
          deleteModal.type === 'approved_bulk' ? `Bạn có chắc chắn muốn xóa vĩnh viễn ${selectedApproved.length} Q&A khỏi Vector DB (Qdrant)?` :
          deleteModal.type === 'staging' ? "Bạn có chắc chắn muốn từ chối và xóa câu hỏi này khỏi danh sách chờ duyệt?" : 
          "Bạn có chắc chắn muốn xóa vĩnh viễn Q&A này khỏi Vector DB (Qdrant)?"
        }
        isDeleting={deleteModal.isDeleting}
      />
    </div>
  );
}
