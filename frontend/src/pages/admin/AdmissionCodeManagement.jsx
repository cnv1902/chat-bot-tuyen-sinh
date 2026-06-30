import React, { useState, useMemo, useEffect } from 'react';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';
import { Upload, Search, FileText, Hash, BookOpen, Edit, Trash2, AlertCircle, ChevronDown, ChevronRight, School } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function AdmissionCodeManagement() {
  const { showToast } = useOutletContext();
  const [data, setData] = useState([]);
  const [institutes, setInstitutes] = useState([]);
  const [searchText, setSearchText] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [expandedNodes, setExpandedNodes] = useState(new Set());

  // Modal states
  const [modalState, setModalState] = useState({
    isOpen: false,
    type: '', // 'edit', 'delete', 'bulk_delete'
    data: null
  });
  
  const [formData, setFormData] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [admRes, instRes] = await Promise.all([
        fetch(`${API_BASE}/api/admissions`, { headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } }),
        fetch(`${API_BASE}/api/academic/tree`, { headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } })
      ]);
      
      if (!admRes.ok) throw new Error('Không thể tải dữ liệu xét tuyển');
      if (!instRes.ok) throw new Error('Không thể tải dữ liệu cơ cấu đào tạo');
      
      const admData = await admRes.json();
      const instData = await instRes.json();
      
      setData(admData);
      setInstitutes(instData);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const isCsv = file.type === 'text/csv' || file.name.endsWith('.csv');
    const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls');

    if (!isCsv && !isExcel) {
      showToast('Vui lòng chọn file định dạng CSV hoặc Excel (.xlsx, .xls)', 'error');
      e.target.value = null;
      return;
    }

    setLoading(true);

    try {
      let rawData = [];

      if (isCsv) {
        rawData = await new Promise((resolve, reject) => {
          Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            complete: (results) => resolve(results.data),
            error: (error) => reject(error)
          });
        });
      } else {
        const arrayBuffer = await file.arrayBuffer();
        const workbook = XLSX.read(arrayBuffer, { type: 'array' });
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];
        rawData = XLSX.utils.sheet_to_json(worksheet, { defval: "" });
      }

      const transformed = rawData.map(row => {
        const keys = Object.keys(row);
        const admissionKey = keys.find(k => k.trim().toLowerCase() === 'mã xét tuyển' || k.trim().toLowerCase().includes('xét tuyển'));
        const majorKey = keys.find(k => k.trim().toLowerCase() === 'mã ngành2' || k.trim().toLowerCase() === 'mã ngành' || k.trim().toLowerCase().includes('ngành'));
        const programKey = keys.find(k => k.trim().toLowerCase() === 'tên chương trình' || k.trim().toLowerCase().includes('chương trình'));

        return {
          admissionCode: String(row[admissionKey || 'Mã xét tuyển'] || '').trim(),
          majorCode: String(row[majorKey || 'Mã Ngành2'] || '').trim(),
          programName: String(row[programKey || 'Tên Chương Trình'] || '').trim()
        };
      }).filter(item => item.admissionCode && item.majorCode && item.programName);

      if (transformed.length === 0) {
        throw new Error('Không tìm thấy dữ liệu hợp lệ. Vui lòng kiểm tra lại tên các cột phải chứa: "Mã xét tuyển", "Mã Ngành2", "Tên Chương Trình".');
      }

      const res = await fetch(`${API_BASE}/api/admissions/import`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(transformed)
      });

      const result = await res.json();
      if (!res.ok) {
        if (Array.isArray(result.detail)) {
          const msgs = result.detail.map(e => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join('; ');
          throw new Error(`Dữ liệu không hợp lệ (${msgs})`);
        }
        throw new Error(result.detail || 'Có lỗi xảy ra khi import');
      }

      showToast(`Import thành công: ${result.success} bản ghi, thất bại: ${result.failed}`, 'success');
      if (result.errors && result.errors.length > 0) {
        showToast("Có một số bản ghi bị lỗi, xem Console để biết chi tiết.", "warning");
      }
      fetchData();
    } catch (error) {
      showToast(`Lỗi khi xử lý file: ${error.message || 'Không xác định'}`, 'error');
    } finally {
      setLoading(false);
      e.target.value = null;
    }
  };

  const toggleNode = (code, e) => {
    if (e.target.closest('input') || e.target.closest('button')) return;
    
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(code)) {
      newExpanded.delete(code);
    } else {
      newExpanded.add(code);
    }
    setExpandedNodes(newExpanded);
  };

  const handleSelect = (e, admissionCode) => {
    if (e.target.checked) {
      setSelectedIds([...selectedIds, admissionCode]);
    } else {
      setSelectedIds(selectedIds.filter(id => id !== admissionCode));
    }
  };

  const handleSelectGroup = (e, groupAdmissions) => {
    const groupIds = groupAdmissions.map(a => a.admissionCode);
    if (e.target.checked) {
      const newIds = new Set([...selectedIds, ...groupIds]);
      setSelectedIds(Array.from(newIds));
    } else {
      setSelectedIds(selectedIds.filter(id => !groupIds.includes(id)));
    }
  };

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      // Select all visible admissions based on search
      const visibleIds = groupedData.flatMap(g => g.admissions).map(a => a.admissionCode);
      setSelectedIds(visibleIds);
    } else {
      setSelectedIds([]);
    }
  };

  const openModal = (type, item = null) => {
    setModalState({ isOpen: true, type, data: item });
    if (type === 'edit' && item) {
      setFormData({
        admissionCode: item.admissionCode,
        majorCode: item.majorCode,
        programName: item.programName
      });
    } else {
      setFormData({});
    }
  };

  const closeModal = () => {
    setModalState({ isOpen: false, type: '', data: null });
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/admissions/${formData.admissionCode}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          majorCode: formData.majorCode,
          programName: formData.programName
        })
      });
      
      const resData = await res.json();
      if (!res.ok) throw new Error(resData.detail || 'Có lỗi xảy ra');
      
      showToast('Cập nhật thành công', 'success');
      fetchData();
      closeModal();
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/admissions/${modalState.data.admissionCode}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      const resData = await res.json();
      if (!res.ok) throw new Error(resData.detail || 'Có lỗi xảy ra');
      
      showToast('Xóa thành công', 'success');
      setSelectedIds(selectedIds.filter(id => id !== modalState.data.admissionCode));
      fetchData();
      closeModal();
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleBulkDeleteConfirm = async () => {
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/admissions/bulk-delete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({ ids: selectedIds })
      });
      
      const resData = await res.json();
      if (!res.ok) throw new Error(resData.detail || 'Có lỗi xảy ra');
      
      showToast(resData.message || 'Xóa thành công', 'success');
      setSelectedIds([]);
      fetchData();
      closeModal();
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Build grouped data
  const groupedData = useMemo(() => {
    const majorToInst = {};
    institutes.forEach(inst => {
      inst.majors.forEach(m => {
        majorToInst[m.major_code] = inst;
      });
    });

    const groups = {};
    institutes.forEach(inst => {
      groups[inst.institute_code] = {
        institute_code: inst.institute_code,
        institute_name: inst.institute_name,
        admissions: []
      };
    });

    groups['OTHER'] = {
      institute_code: 'OTHER',
      institute_name: 'Khác (Không thuộc Trường/Viện nào)',
      admissions: []
    };

    const lowerSearch = searchText.toLowerCase();
    let matchCount = 0;

    data.forEach(adm => {
      const matchesSearch = !searchText.trim() || 
        adm.admissionCode.toLowerCase().includes(lowerSearch) || 
        adm.programName.toLowerCase().includes(lowerSearch);
        
      if (!matchesSearch) return;
      matchCount++;

      const inst = majorToInst[adm.majorCode];
      if (inst && groups[inst.institute_code]) {
        groups[inst.institute_code].admissions.push(adm);
      } else {
        groups['OTHER'].admissions.push(adm);
      }
    });

    return Object.values(groups).filter(g => g.admissions.length > 0);
  }, [data, institutes, searchText]);

  const totalFilteredCount = groupedData.reduce((sum, g) => sum + g.admissions.length, 0);
  const isAllSelected = totalFilteredCount > 0 && selectedIds.length === totalFilteredCount;

  return (
    <div className="admin-card" style={{ padding: '0', backgroundColor: 'transparent', boxShadow: 'none' }}>
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '24px', marginBottom: '24px' }}>
        
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
          <div>
            <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Quản lý Xét Tuyển</h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
              Quản lý danh sách mã xét tuyển theo Trường/Viện.
            </p>
          </div>
          
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            {selectedIds.length > 0 && (
              <button 
                onClick={() => openModal('bulk_delete')}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#ef4444', color: 'white', borderRadius: '6px', border: 'none', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500, transition: 'all 0.2s' }}
              >
                <Trash2 size={16} /> Xóa ({selectedIds.length})
              </button>
            )}

            <div style={{ display: 'flex', alignItems: 'center', backgroundColor: '#f9fafb', border: '1px solid #d1d5db', borderRadius: '6px', padding: '0 12px', width: '300px' }}>
              <Search size={18} color="#6b7280" />
              <input 
                type="text" 
                placeholder="Tìm mã xét tuyển hoặc tên CTĐT..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                style={{ border: 'none', background: 'transparent', padding: '10px', width: '100%', outline: 'none', color: '#374151' }}
              />
            </div>

            <div style={{ position: 'relative' }}>
              <input
                type="file"
                accept=".csv, .xlsx, .xls"
                id="upload-csv"
                style={{ display: 'none' }}
                onChange={handleFileUpload}
                disabled={loading}
              />
              <label
                htmlFor="upload-csv"
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px',
                  backgroundColor: '#3b82f6', color: 'white', borderRadius: '6px', cursor: loading ? 'not-allowed' : 'pointer', fontWeight: '500', transition: 'background-color 0.2s', opacity: loading ? 0.7 : 1
                }}
              >
                <Upload size={18} />
                {loading ? 'Đang xử lý...' : 'Import CSV/Excel'}
              </label>
            </div>
          </div>
        </div>

        {/* Tree View */}
        <div>
          {loading && data.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>Đang tải dữ liệu...</div>
          ) : data.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>
              <FileText size={48} style={{ margin: '0 auto 12px auto', opacity: 0.3 }} />
              <p style={{ margin: 0 }}>Chưa có dữ liệu. Vui lòng import file CSV/Excel để bắt đầu.</p>
            </div>
          ) : groupedData.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px', color: '#6b7280' }}>
              Không tìm thấy kết quả nào phù hợp.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* Header */}
              <div style={{ display: 'flex', padding: '0 16px 8px 16px', color: '#6b7280', fontSize: '0.9rem', fontWeight: 500, borderBottom: '1px solid #e5e7eb', marginBottom: '8px' }}>
                <div style={{ width: '32px', display: 'flex', alignItems: 'center' }}>
                  <input 
                    type="checkbox" 
                    checked={isAllSelected}
                    onChange={handleSelectAll}
                    style={{ cursor: 'pointer' }}
                  />
                </div>
                <div style={{ flex: 1 }}>Cơ cấu tổ chức</div>
                <div style={{ width: '80px', textAlign: 'right', paddingRight: '8px' }}>Thao tác</div>
              </div>

              {groupedData.map((group) => {
                const groupAdmissions = group.admissions;
                const isGroupSelected = groupAdmissions.length > 0 && groupAdmissions.every(a => selectedIds.includes(a.admissionCode));

                return (
                  <div key={group.institute_code} style={{ border: '1px solid #e5e7eb', borderRadius: '6px', overflow: 'hidden' }}>
                    {/* Institute Row */}
                    <div 
                      onClick={(e) => toggleNode(group.institute_code, e)}
                      style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', backgroundColor: '#f9fafb', cursor: 'pointer', userSelect: 'none' }}
                    >
                      <div style={{ marginRight: '12px', display: 'flex', alignItems: 'center' }}>
                        <input 
                          type="checkbox" 
                          checked={isGroupSelected}
                          onChange={(e) => handleSelectGroup(e, groupAdmissions)}
                          onClick={(e) => e.stopPropagation()}
                          style={{ cursor: 'pointer' }}
                        />
                      </div>
                      <div style={{ marginRight: '12px', color: '#6b7280' }}>
                        {expandedNodes.has(group.institute_code) ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                      </div>
                      <School size={20} style={{ marginRight: '12px', color: group.institute_code === 'OTHER' ? '#9ca3af' : '#3b82f6' }} />
                      <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                        <span style={{ fontWeight: '600', color: '#1f2937' }}>{group.institute_name}</span>
                        {group.institute_code !== 'OTHER' && (
                          <span style={{ marginLeft: '8px', fontSize: '12px', color: '#6b7280', backgroundColor: '#e5e7eb', padding: '2px 6px', borderRadius: '4px' }}>
                            {group.institute_code}
                          </span>
                        )}
                        <div style={{ fontSize: '12px', color: '#10b981', fontWeight: '600', backgroundColor: '#d1fae5', padding: '2px 8px', borderRadius: '12px', marginLeft: '12px' }}>
                          {groupAdmissions.length} mã xét tuyển
                        </div>
                      </div>
                    </div>

                    {/* Admission Codes List */}
                    {expandedNodes.has(group.institute_code) && (
                      <div style={{ borderTop: '1px solid #e5e7eb' }}>
                        {groupAdmissions.map((item, index) => (
                          <div 
                            key={item.admissionCode} 
                            style={{ 
                              display: 'flex', alignItems: 'center', padding: '12px 16px',
                              borderBottom: index < groupAdmissions.length - 1 ? '1px solid #f3f4f6' : 'none',
                              backgroundColor: 'white'
                            }}
                          >
                            <div style={{ marginRight: '12px', marginLeft: '28px', display: 'flex', alignItems: 'center' }}>
                              <input 
                                type="checkbox" 
                                checked={selectedIds.includes(item.admissionCode)}
                                onChange={(e) => handleSelect(e, item.admissionCode)}
                                style={{ cursor: 'pointer' }}
                              />
                            </div>
                            <BookOpen size={18} style={{ marginRight: '12px', color: '#10b981' }} />
                            <div style={{ flex: 1 }}>
                              <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                                <span style={{ fontWeight: '500', color: '#374151' }}>{item.programName}</span>
                                <span style={{ fontSize: '12px', color: '#6b7280', backgroundColor: '#f3f4f6', padding: '2px 6px', borderRadius: '4px' }}>
                                  Mã Ngành: {item.majorCode}
                                </span>
                                <span style={{ fontSize: '12px', color: '#0369a1', backgroundColor: '#e0f2fe', padding: '2px 6px', borderRadius: '4px', fontWeight: '500' }}>
                                  Mã XT: {item.admissionCode}
                                </span>
                              </div>
                            </div>
                            
                            <div style={{ display: 'flex', gap: '12px', width: '80px', justifyContent: 'flex-end' }}>
                              <button 
                                onClick={() => openModal('edit', item)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary-blue)' }}
                                title="Sửa"
                              >
                                <Edit size={18} />
                              </button>
                              <button 
                                onClick={() => openModal('delete', item)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }}
                                title="Xóa"
                              >
                                <Trash2 size={18} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          
          {totalFilteredCount > 0 && (
            <div style={{ padding: '16px', color: '#64748b', fontSize: '0.9rem', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', marginTop: '12px' }}>
              <span>Hiển thị <strong>{totalFilteredCount}</strong> kết quả</span>
            </div>
          )}
        </div>
      </div>

      {/* MODALS */}
      {modalState.isOpen && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
          backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000, 
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <div style={{
            backgroundColor: 'white', borderRadius: '12px', width: '500px', 
            maxWidth: '90%', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)'
          }}>
            
            {/* Edit Modal */}
            {modalState.type === 'edit' && (
              <form onSubmit={handleEditSubmit}>
                <div style={{ padding: '20px', borderBottom: '1px solid #e2e8f0' }}>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#1e293b' }}>Sửa thông tin Xét tuyển</h3>
                </div>
                <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500, color: '#475569' }}>Mã xét tuyển (Khóa chính)</label>
                    <input 
                      type="text" 
                      value={formData.admissionCode} 
                      disabled
                      style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#f1f5f9', color: '#94a3b8', boxSizing: 'border-box' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500, color: '#475569' }}>Mã ngành</label>
                    <input 
                      type="text" 
                      value={formData.majorCode || ''} 
                      onChange={e => setFormData({...formData, majorCode: e.target.value})}
                      required
                      style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500, color: '#475569' }}>Tên chương trình đào tạo</label>
                    <input 
                      type="text" 
                      value={formData.programName || ''} 
                      onChange={e => setFormData({...formData, programName: e.target.value})}
                      required
                      style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }}
                    />
                  </div>
                </div>
                <div style={{ padding: '20px', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                  <button type="button" onClick={closeModal} style={{ padding: '8px 16px', border: '1px solid #cbd5e1', borderRadius: '6px', background: 'white', cursor: 'pointer' }}>Hủy</button>
                  <button type="submit" disabled={submitting} style={{ padding: '8px 16px', border: 'none', borderRadius: '6px', background: 'var(--primary-blue)', color: 'white', cursor: submitting ? 'not-allowed' : 'pointer' }}>
                    {submitting ? 'Đang lưu...' : 'Lưu thay đổi'}
                  </button>
                </div>
              </form>
            )}

            {/* Delete Modal */}
            {modalState.type === 'delete' && (
              <div>
                <div style={{ padding: '20px', borderBottom: '1px solid #e2e8f0', display: 'flex', gap: '12px', alignItems: 'center' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '50%', backgroundColor: '#fee2e2', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444' }}>
                    <AlertCircle size={24} />
                  </div>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#1e293b' }}>Xác nhận xóa</h3>
                </div>
                <div style={{ padding: '20px', color: '#475569' }}>
                  Bạn có chắc chắn muốn xóa mã xét tuyển <strong>{modalState.data?.admissionCode}</strong>? Hành động này không thể hoàn tác.
                </div>
                <div style={{ padding: '20px', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                  <button onClick={closeModal} style={{ padding: '8px 16px', border: '1px solid #cbd5e1', borderRadius: '6px', background: 'white', cursor: 'pointer' }}>Hủy</button>
                  <button onClick={handleDeleteConfirm} disabled={submitting} style={{ padding: '8px 16px', border: 'none', borderRadius: '6px', background: '#ef4444', color: 'white', cursor: submitting ? 'not-allowed' : 'pointer' }}>
                    {submitting ? 'Đang xóa...' : 'Xóa dữ liệu'}
                  </button>
                </div>
              </div>
            )}

            {/* Bulk Delete Modal */}
            {modalState.type === 'bulk_delete' && (
              <div>
                <div style={{ padding: '20px', borderBottom: '1px solid #e2e8f0', display: 'flex', gap: '12px', alignItems: 'center' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '50%', backgroundColor: '#fee2e2', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444' }}>
                    <AlertCircle size={24} />
                  </div>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#1e293b' }}>Xác nhận xóa hàng loạt</h3>
                </div>
                <div style={{ padding: '20px', color: '#475569' }}>
                  Bạn có chắc chắn muốn xóa <strong>{selectedIds.length}</strong> mục đã chọn? Hành động này không thể hoàn tác.
                </div>
                <div style={{ padding: '20px', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                  <button onClick={closeModal} style={{ padding: '8px 16px', border: '1px solid #cbd5e1', borderRadius: '6px', background: 'white', cursor: 'pointer' }}>Hủy</button>
                  <button onClick={handleBulkDeleteConfirm} disabled={submitting} style={{ padding: '8px 16px', border: 'none', borderRadius: '6px', background: '#ef4444', color: 'white', cursor: submitting ? 'not-allowed' : 'pointer' }}>
                    {submitting ? 'Đang xóa...' : 'Xóa dữ liệu'}
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      )}
    </div>
  );
}
