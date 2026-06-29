import React, { useState, useEffect } from 'react';
import { Upload, Search, Calendar, Hash, Tag, FileText, Layers, List, Bookmark, Plus, Edit, Trash2, X, AlertCircle } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';

export default function AdmissionManagement() {
  const { showToast } = useOutletContext();
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  // ================= STATE =================
  const [activeTab, setActiveTab] = useState('plans'); // 'plans', 'methods', 'combinations'
  const [data, setData] = useState({
    plans: [],
    methods: [],
    combinations: []
  });
  
  const [loading, setLoading] = useState(false);
  const [uploadingState, setUploadingState] = useState({ combinations: false, methods: false, plans: false });
  const [filterText, setFilterText] = useState('');
  const [filterYear, setFilterYear] = useState('2026');
  const [selectedItems, setSelectedItems] = useState([]);

  // Modal State
  const [modalState, setModalState] = useState({
    isOpen: false,
    type: 'add', // 'add', 'edit', 'delete'
    tab: 'plans', // Which tab the modal belongs to
    data: null // Data to edit/delete
  });
  const [formData, setFormData] = useState({});

  // ================= FETCH DATA =================
  const fetchData = async () => {
    setLoading(true);
    try {
      const endpoints = {
        plans: `${API_URL}/api/admission/plans?year=${filterYear}`,
        methods: `${API_URL}/api/admission/methods?year=${filterYear}`,
        combinations: `${API_URL}/api/admission/combinations`
      };

      const res = await fetch(endpoints[activeTab]);
      if (!res.ok) throw new Error('Không thể tải dữ liệu');
      const result = await res.json();
      
      setData(prev => ({ ...prev, [activeTab]: result }));
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setSelectedItems([]);
    fetchData();
  }, [activeTab, filterYear]);

  // ================= UPLOAD =================
  const handleFileUpload = async (event, type) => {
    const file = event.target.files[0];
    if (!file) return;

    const endpoints = {
      combinations: `${API_URL}/api/admission/import-combinations`,
      methods: `${API_URL}/api/admission/import-methods`,
      plans: `${API_URL}/api/admission/import-plans`
    };

    setUploadingState(prev => ({ ...prev, [type]: true }));
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(endpoints[type], {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || 'Có lỗi xảy ra khi upload');
      }

      showToast(result.message, 'success');
      if (type === activeTab) fetchData(); 
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setUploadingState(prev => ({ ...prev, [type]: false }));
      event.target.value = null;
    }
  };

  // ================= MODAL LOGIC =================
  const openModal = (type, tab, rowData = null) => {
    setModalState({ isOpen: true, type, tab, data: rowData });
    if (type === 'add') {
      if (tab === 'plans') setFormData({ year: filterYear, major_code: '', methods: '', combinations: '', target_quota: '' });
      if (tab === 'methods') setFormData({ year: filterYear, method_code: '', method_name: '' });
      if (tab === 'combinations') setFormData({ combo_code: '', subjects: '' });
    } else if (type === 'edit' && rowData) {
      if (tab === 'plans') setFormData({ ...rowData, methods: rowData.methods.map(m => m.code).join(', '), combinations: rowData.combinations.map(c => c.code).join(', ') });
      if (tab === 'methods') setFormData({ ...rowData });
      if (tab === 'combinations') setFormData({ ...rowData });
    }
  };

  const closeModal = () => {
    setModalState({ isOpen: false, type: 'add', tab: 'plans', data: null });
    setFormData({});
  };

  const submitForm = async (e) => {
    e.preventDefault();
    const { type, tab, data: rowData } = modalState;
    let url = '';
    let method = type === 'add' ? 'POST' : 'PUT';
    let payload = { ...formData };

    try {
      if (tab === 'methods') {
        url = type === 'add' ? `${API_URL}/api/admission_crud/methods` : `${API_URL}/api/admission_crud/methods/${rowData.id}`;
        payload.year = parseInt(payload.year);
      } else if (tab === 'combinations') {
        url = type === 'add' ? `${API_URL}/api/admission_crud/combinations` : `${API_URL}/api/admission_crud/combinations/${rowData.combo_code}`;
      } else if (tab === 'plans') {
        url = type === 'add' ? `${API_URL}/api/admission_crud/plans` : `${API_URL}/api/admission_crud/plans/${rowData.id}`;
        payload.year = parseInt(payload.year);
        payload.target_quota = payload.target_quota ? parseInt(payload.target_quota) : null;
        payload.methods = payload.methods.split(',').map(s => s.trim()).filter(s => s);
        payload.combinations = payload.combinations.split(',').map(s => s.trim()).filter(s => s);
      }

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Lỗi thao tác');

      showToast(result.message, 'success');
      closeModal();
      fetchData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const deleteRecord = async () => {
    const { tab, data: rowData } = modalState;
    let url = '';
    
    if (tab === 'methods') url = `${API_URL}/api/admission_crud/methods/${rowData.id}`;
    if (tab === 'combinations') url = `${API_URL}/api/admission_crud/combinations/${rowData.combo_code}`;
    if (tab === 'plans') url = `${API_URL}/api/admission_crud/plans/${rowData.id}`;

    try {
      const res = await fetch(url, { method: 'DELETE' });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Lỗi khi xóa');

      showToast(result.message, 'success');
      closeModal();
      fetchData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const submitBulkDelete = async () => {
    if (selectedItems.length === 0) return;
    const { tab } = modalState;
    let url = '';
    
    if (tab === 'methods') url = `${API_URL}/api/admission_crud/methods/bulk-delete`;
    if (tab === 'combinations') url = `${API_URL}/api/admission_crud/combinations/bulk-delete`;
    if (tab === 'plans') url = `${API_URL}/api/admission_crud/plans/bulk-delete`;

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedItems })
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Lỗi khi xóa hàng loạt');

      showToast(result.message, 'success');
      setSelectedItems([]);
      closeModal();
      fetchData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  // ================= FILTER & RENDER =================
  const filteredData = data[activeTab].filter(item => {
    if (!filterText) return true;
    const lowerFilter = filterText.toLowerCase();
    if (activeTab === 'plans') {
      return item.major_code?.toLowerCase().includes(lowerFilter) || item.major_name?.toLowerCase().includes(lowerFilter);
    }
    if (activeTab === 'methods') {
      return item.method_code?.toLowerCase().includes(lowerFilter) || item.method_name?.toLowerCase().includes(lowerFilter);
    }
    if (activeTab === 'combinations') {
      return item.combo_code?.toLowerCase().includes(lowerFilter) || item.subjects?.toLowerCase().includes(lowerFilter);
    }
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header & Tabs */}
      <div className="admin-card" style={{ padding: '24px', backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ marginBottom: '16px' }}>
          <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Quản lý Đề án Tuyển sinh</h3>
        </div>

        <div style={{ display: 'flex', borderBottom: '2px solid #e5e7eb', marginBottom: '24px' }}>
          <div 
            onClick={() => { setActiveTab('plans'); setFilterText(''); }}
            style={{ padding: '12px 24px', cursor: 'pointer', borderBottom: activeTab === 'plans' ? '2px solid var(--primary-color)' : '2px solid transparent', color: activeTab === 'plans' ? 'var(--primary-color)' : '#6b7280', fontWeight: activeTab === 'plans' ? 600 : 500, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '-2px' }}>
            <FileText size={18} /> Đề án Tuyển sinh
          </div>
          <div 
            onClick={() => { setActiveTab('methods'); setFilterText(''); }}
            style={{ padding: '12px 24px', cursor: 'pointer', borderBottom: activeTab === 'methods' ? '2px solid var(--primary-color)' : '2px solid transparent', color: activeTab === 'methods' ? 'var(--primary-color)' : '#6b7280', fontWeight: activeTab === 'methods' ? 600 : 500, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '-2px' }}>
            <Layers size={18} /> Phương thức
          </div>
          <div 
            onClick={() => { setActiveTab('combinations'); setFilterText(''); }}
            style={{ padding: '12px 24px', cursor: 'pointer', borderBottom: activeTab === 'combinations' ? '2px solid var(--primary-color)' : '2px solid transparent', color: activeTab === 'combinations' ? 'var(--primary-color)' : '#6b7280', fontWeight: activeTab === 'combinations' ? 600 : 500, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '-2px' }}>
            <List size={18} /> Tổ hợp môn
          </div>
        </div>

        {/* Toolbar */}
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          {(activeTab === 'plans' || activeTab === 'methods') && (
            <div style={{ display: 'flex', alignItems: 'center', backgroundColor: '#f9fafb', border: '1px solid #d1d5db', borderRadius: '6px', padding: '0 12px' }}>
              <Calendar size={18} color="#6b7280" style={{ marginRight: '8px' }} />
              <select 
                value={filterYear}
                onChange={(e) => setFilterYear(e.target.value)}
                style={{ border: 'none', background: 'transparent', padding: '10px 0', outline: 'none', color: '#374151', fontWeight: 500 }}>
                <option value="2026">Năm 2026</option>
                <option value="2025">Năm 2025</option>
                <option value="2024">Năm 2024</option>
              </select>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', backgroundColor: '#f9fafb', border: '1px solid #d1d5db', borderRadius: '6px', padding: '0 12px', flex: 1, minWidth: '250px' }}>
            <Search size={18} color="#6b7280" />
            <input 
              type="text" 
              placeholder={activeTab === 'plans' ? "Tìm theo mã/tên ngành..." : activeTab === 'methods' ? "Tìm phương thức..." : "Tìm tổ hợp môn..."}
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              style={{ border: 'none', background: 'transparent', padding: '10px', width: '100%', outline: 'none', color: '#374151' }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {/* Bulk Delete Button */}
            {selectedItems.length > 0 && (
              <button onClick={() => openModal('bulk_delete', activeTab)} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#ef4444', color: 'white', borderRadius: '6px', border: 'none', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500, transition: 'all 0.2s' }}>
                <Trash2 size={16} /> Xóa ({selectedItems.length})
              </button>
            )}

            {/* Add Button */}
            <button onClick={() => openModal('add', activeTab)} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#10b981', color: 'white', borderRadius: '6px', border: 'none', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500, transition: 'all 0.2s' }}>
              <Plus size={16} /> Thêm Mới
            </button>

            {/* Upload Buttons */}
            {activeTab === 'plans' && (
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#3b82f6', color: 'white', borderRadius: '6px', cursor: uploadingState.plans ? 'not-allowed' : 'pointer', fontSize: '0.9rem', fontWeight: 500, transition: 'all 0.2s' }}>
                <Upload size={16} /> {uploadingState.plans ? 'Đang tải...' : 'Import Đề án'}
                <input type="file" accept=".xlsx" style={{ display: 'none' }} onChange={(e) => handleFileUpload(e, 'plans')} disabled={uploadingState.plans} />
              </label>
            )}
            {activeTab === 'methods' && (
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#3b82f6', color: 'white', borderRadius: '6px', cursor: uploadingState.methods ? 'not-allowed' : 'pointer', fontSize: '0.9rem', fontWeight: 500, transition: 'all 0.2s' }}>
                <Upload size={16} /> {uploadingState.methods ? 'Đang tải...' : 'Import Phương thức'}
                <input type="file" accept=".xlsx" style={{ display: 'none' }} onChange={(e) => handleFileUpload(e, 'methods')} disabled={uploadingState.methods} />
              </label>
            )}
            {activeTab === 'combinations' && (
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#3b82f6', color: 'white', borderRadius: '6px', cursor: uploadingState.combinations ? 'not-allowed' : 'pointer', fontSize: '0.9rem', fontWeight: 500, transition: 'all 0.2s' }}>
                <Upload size={16} /> {uploadingState.combinations ? 'Đang tải...' : 'Import Tổ hợp'}
                <input type="file" accept=".xlsx" style={{ display: 'none' }} onChange={(e) => handleFileUpload(e, 'combinations')} disabled={uploadingState.combinations} />
              </label>
            )}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="admin-card" style={{ padding: '0', backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
              <tr>
                <th style={{ padding: '12px 16px', width: '40px' }}>
                  <input 
                    type="checkbox" 
                    checked={filteredData.length > 0 && selectedItems.length === filteredData.length}
                    onChange={(e) => {
                      if (e.target.checked) setSelectedItems(filteredData.map(item => item.id || item.combo_code));
                      else setSelectedItems([]);
                    }}
                  />
                </th>
                {activeTab === 'plans' && (
                  <>
                    <th style={{ padding: '12px 16px', color: '#4b5563', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Mã Ngành</th>
                    <th style={{ padding: '12px 16px', color: '#4b5563', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Phương Thức</th>
                    <th style={{ padding: '12px 16px', color: '#4b5563', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Tổ Hợp</th>
                    <th style={{ padding: '12px 16px', color: '#4b5563', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', textAlign: 'center' }}>Chỉ tiêu</th>
                  </>
                )}
                {activeTab === 'methods' && (
                  <>
                    <th style={{ padding: '12px 16px', color: '#4b5563', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Mã PT</th>
                    <th style={{ padding: '12px 16px', color: '#4b5563', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Tên Phương thức</th>
                  </>
                )}
                {activeTab === 'combinations' && (
                  <>
                    <th style={{ padding: '12px 16px', color: '#4b5563', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Mã Tổ hợp</th>
                    <th style={{ padding: '12px 16px', color: '#4b5563', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Môn học</th>
                  </>
                )}
                <th style={{ padding: '12px 16px', color: '#4b5563', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', textAlign: 'right' }}>Hành động</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="6" style={{ padding: '30px', textAlign: 'center', color: '#6b7280' }}>Đang tải dữ liệu...</td>
                </tr>
              ) : filteredData.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ padding: '30px', textAlign: 'center', color: '#6b7280' }}>Không tìm thấy dữ liệu.</td>
                </tr>
              ) : (
                filteredData.map((item, idx) => (
                  <tr key={item.id || item.combo_code} style={{ borderBottom: idx !== filteredData.length - 1 ? '1px solid #e5e7eb' : 'none', backgroundColor: idx % 2 === 0 ? '#ffffff' : '#f9fafb' }}>
                    <td style={{ padding: '12px 16px' }}>
                      <input 
                        type="checkbox"
                        checked={selectedItems.includes(item.id || item.combo_code)}
                        onChange={(e) => {
                          const id = item.id || item.combo_code;
                          if (e.target.checked) setSelectedItems([...selectedItems, id]);
                          else setSelectedItems(selectedItems.filter(i => i !== id));
                        }}
                      />
                    </td>
                    {activeTab === 'plans' && (
                      <>
                        <td style={{ padding: '12px 16px' }}>
                          <div style={{ fontWeight: 600, color: '#111827', fontSize: '0.95rem' }}>{item.major_code}</div>
                          <div style={{ color: '#6b7280', fontSize: '0.85rem', marginTop: '2px' }}>{item.major_name}</div>
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                            {item.methods && item.methods.length > 0 ? item.methods.map(method => (
                              <div key={method.code} title={method.name} style={{ cursor: 'help', backgroundColor: '#f3f4f6', padding: '4px 8px', borderRadius: '6px', border: '1px solid #e5e7eb' }}>
                                <span style={{ fontWeight: 600, color: '#111827', fontSize: '0.85rem' }}>{method.code}</span>
                              </div>
                            )) : <span style={{ color: '#9ca3af', fontStyle: 'italic', fontSize: '0.85rem' }}>-</span>}
                          </div>
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                            {item.combinations && item.combinations.length > 0 ? item.combinations.map(combo => (
                              <span key={combo.code} title={combo.subjects} style={{ cursor: 'help', display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#e0f2fe', color: '#0369a1', padding: '2px 8px', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 600 }}>
                                {combo.code}
                              </span>
                            )) : <span style={{ color: '#9ca3af', fontStyle: 'italic', fontSize: '0.85rem' }}>-</span>}
                          </div>
                        </td>
                        <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                          {item.target_quota ? <span style={{ fontWeight: 600, color: '#059669', backgroundColor: '#d1fae5', padding: '4px 12px', borderRadius: '6px', fontSize: '0.9rem' }}>{item.target_quota}</span> : <span style={{ color: '#9ca3af' }}>-</span>}
                        </td>
                      </>
                    )}
                    
                    {activeTab === 'methods' && (
                      <>
                        <td style={{ padding: '12px 16px' }}>
                          <span style={{ fontWeight: 600, color: '#111827', backgroundColor: '#f3f4f6', padding: '2px 8px', borderRadius: '6px', fontSize: '0.9rem' }}>{item.method_code}</span>
                        </td>
                        <td style={{ padding: '12px 16px', color: '#111827' }}>{item.method_name}</td>
                      </>
                    )}

                    {activeTab === 'combinations' && (
                      <>
                        <td style={{ padding: '12px 16px' }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#e0f2fe', color: '#0369a1', padding: '2px 8px', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 600 }}>{item.combo_code}</span>
                        </td>
                        <td style={{ padding: '12px 16px', color: '#111827' }}>{item.subjects}</td>
                      </>
                    )}

                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                        <button onClick={() => openModal('edit', activeTab, item)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary-blue)', marginRight: '10px' }} title="Sửa">
                          <Edit size={18} />
                        </button>
                        <button onClick={() => openModal('delete', activeTab, item)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }} title="Xóa">
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ================= MODALS ================= */}
      {modalState.isOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          
        {modalState.type === 'bulk_delete' ? (
          <div style={{ backgroundColor: 'white', padding: '24px', borderRadius: '12px', width: '400px', boxShadow: '0 10px 25px rgba(0,0,0,0.1)' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#dc2626', marginBottom: '16px', marginTop: 0 }}>
              <AlertCircle size={24} /> Xác nhận xóa hàng loạt
            </h3>
            <p style={{ color: '#4b5563', marginBottom: '24px', lineHeight: 1.5 }}>
              Bạn có chắc chắn muốn xóa <strong>{selectedItems.length}</strong> mục đã chọn? Thao tác này không thể hoàn tác.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button onClick={closeModal} style={{ padding: '8px 16px', backgroundColor: '#f3f4f6', color: '#4b5563', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}>Hủy</button>
              <button onClick={submitBulkDelete} style={{ padding: '8px 16px', backgroundColor: '#dc2626', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}>Xóa hàng loạt</button>
            </div>
          </div>
        ) : (
          <div style={{ backgroundColor: '#fff', borderRadius: '12px', width: '100%', maxWidth: '500px', padding: '24px', boxShadow: '0 10px 25px rgba(0,0,0,0.15)' }}>
            
            {modalState.type === 'delete' ? (
              // Delete Modal
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px', color: '#ef4444' }}>
                  <AlertCircle size={28} />
                  <h3 style={{ margin: 0, fontSize: '1.2rem' }}>Xác nhận xóa</h3>
                </div>
                <p style={{ color: '#4b5563', marginBottom: '24px' }}>Bạn có chắc chắn muốn xóa bản ghi này không? Hành động này không thể hoàn tác.</p>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                  <button onClick={closeModal} style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #d1d5db', backgroundColor: '#fff', cursor: 'pointer', fontWeight: 500 }}>Hủy</button>
                  <button onClick={deleteRecord} style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', backgroundColor: '#ef4444', color: '#fff', cursor: 'pointer', fontWeight: 500 }}>Xóa ngay</button>
                </div>
              </div>
            ) : (
              // Add/Edit Form Modal
              <form onSubmit={submitForm}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#111827' }}>
                    {modalState.type === 'add' ? 'Thêm mới ' : 'Cập nhật '} 
                    {modalState.tab === 'plans' ? 'Đề án' : modalState.tab === 'methods' ? 'Phương thức' : 'Tổ hợp'}
                  </h3>
                  <button type="button" onClick={closeModal} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280' }}><X size={20} /></button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '24px' }}>
                  
                  {modalState.tab === 'plans' && (
                    <>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Năm</label>
                        <input required type="number" value={formData.year || ''} onChange={e => setFormData({...formData, year: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} />
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Mã Ngành</label>
                        <input required type="text" value={formData.major_code || ''} onChange={e => setFormData({...formData, major_code: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} placeholder="VD: 7480101" />
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Mã Phương thức (cách nhau bởi dấu phẩy)</label>
                        <input required type="text" value={formData.methods || ''} onChange={e => setFormData({...formData, methods: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} placeholder="VD: 100, 200, 301" />
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Mã Tổ hợp (cách nhau bởi dấu phẩy)</label>
                        <input type="text" value={formData.combinations || ''} onChange={e => setFormData({...formData, combinations: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} placeholder="VD: A00, A01, D01" />
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Chỉ tiêu</label>
                        <input type="number" value={formData.target_quota || ''} onChange={e => setFormData({...formData, target_quota: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} />
                      </div>
                    </>
                  )}

                  {modalState.tab === 'methods' && (
                    <>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Năm</label>
                        <input required type="number" value={formData.year || ''} onChange={e => setFormData({...formData, year: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} />
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Mã Phương thức</label>
                        <input required type="text" value={formData.method_code || ''} onChange={e => setFormData({...formData, method_code: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} />
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Tên Phương thức</label>
                        <input required type="text" value={formData.method_name || ''} onChange={e => setFormData({...formData, method_name: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} />
                      </div>
                    </>
                  )}

                  {modalState.tab === 'combinations' && (
                    <>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Mã Tổ hợp</label>
                        <input required type="text" value={formData.combo_code || ''} onChange={e => setFormData({...formData, combo_code: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} />
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#374151' }}>Các môn học</label>
                        <input required type="text" value={formData.subjects || ''} onChange={e => setFormData({...formData, subjects: e.target.value})} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }} placeholder="VD: Toán, Vật lí, Hóa học" />
                      </div>
                    </>
                  )}

                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                  <button type="button" onClick={closeModal} style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #d1d5db', backgroundColor: '#fff', cursor: 'pointer', fontWeight: 500 }}>Hủy</button>
                  <button type="submit" style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', backgroundColor: '#3b82f6', color: '#fff', cursor: 'pointer', fontWeight: 500 }}>Lưu lại</button>
                </div>
              </form>
            )}
            
          </div>
        )}
        </div>
      )}

    </div>
  );
}
