import React, { useState, useEffect } from 'react';
import { Upload, ChevronDown, ChevronRight, School, BookOpen, Edit, Trash2, Plus, AlertCircle } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function AcademicStructure() {
  const { showToast } = useOutletContext();
  const [treeData, setTreeData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadingInstitute, setUploadingInstitute] = useState(false);
  const [uploadingMajor, setUploadingMajor] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  
  const [selectedInstitutes, setSelectedInstitutes] = useState([]);
  const [selectedMajors, setSelectedMajors] = useState([]);

  // Modal states
  const [modalState, setModalState] = useState({
    isOpen: false,
    type: '', // 'edit_institute', 'edit_major', 'delete_institute', 'delete_major', 'bulk_delete'
    data: null
  });
  
  const [formData, setFormData] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const fetchTree = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/academic/tree`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      if (!res.ok) throw new Error('Không thể tải dữ liệu');
      const data = await res.json();
      setTreeData(data);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTree();
    setSelectedInstitutes([]);
    setSelectedMajors([]);
  }, []);

  const handleFileUpload = async (event, endpoint, setUploadingState) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploadingState(true);
    const form = new FormData();
    form.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/api/academic/${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: form
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Có lỗi xảy ra khi tải file');

      showToast(data.message, 'success');
      fetchTree(); // Reload the tree data
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setUploadingState(false);
      event.target.value = ''; // Reset input
    }
  };

  const toggleNode = (code, e) => {
    // Prevent toggle if clicking on checkbox or buttons
    if (e.target.closest('input') || e.target.closest('button')) return;
    
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(code)) {
      newExpanded.delete(code);
    } else {
      newExpanded.add(code);
    }
    setExpandedNodes(newExpanded);
  };

  const handleSelectInstitute = (e, instituteCode, majors) => {
    e.stopPropagation();
    const majorCodes = majors ? majors.map(m => m.major_code) : [];
    
    if (e.target.checked) {
      setSelectedInstitutes([...selectedInstitutes, instituteCode]);
      // Tự động chọn tất cả các ngành con
      setSelectedMajors([...new Set([...selectedMajors, ...majorCodes])]);
    } else {
      setSelectedInstitutes(selectedInstitutes.filter(c => c !== instituteCode));
      // Bỏ chọn tất cả các ngành con
      setSelectedMajors(selectedMajors.filter(c => !majorCodes.includes(c)));
    }
  };

  const handleSelectMajor = (e, majorCode) => {
    e.stopPropagation();
    if (e.target.checked) {
      setSelectedMajors([...selectedMajors, majorCode]);
    } else {
      setSelectedMajors(selectedMajors.filter(c => c !== majorCode));
    }
  };

  const openModal = (type, data = null) => {
    setModalState({ isOpen: true, type, data });
    if (type === 'edit_institute') {
      setFormData({ institute_name: data.institute_name });
    } else if (type === 'edit_major') {
      setFormData({ major_name: data.major_name, institute_code: data.institute_code });
    }
  };

  const closeModal = () => {
    setModalState({ isOpen: false, type: '', data: null });
    setFormData({});
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const token = localStorage.getItem('access_token');
      let url = '';
      let method = '';
      let body = null;

      if (modalState.type === 'edit_institute') {
        url = `${API_BASE}/api/academic/institutes/${modalState.data.institute_code}`;
        method = 'PUT';
        body = JSON.stringify({ institute_name: formData.institute_name });
      } else if (modalState.type === 'edit_major') {
        url = `${API_BASE}/api/academic/majors/${modalState.data.major_code}`;
        method = 'PUT';
        body = JSON.stringify({ major_name: formData.major_name, institute_code: formData.institute_code });
      } else if (modalState.type === 'delete_institute') {
        url = `${API_BASE}/api/academic/institutes/${modalState.data.institute_code}`;
        method = 'DELETE';
      } else if (modalState.type === 'delete_major') {
        url = `${API_BASE}/api/academic/majors/${modalState.data.major_code}`;
        method = 'DELETE';
      } else if (modalState.type === 'bulk_delete') {
        url = `${API_BASE}/api/academic/bulk-delete`;
        method = 'POST';
        body = JSON.stringify({
          institute_codes: selectedInstitutes,
          major_codes: selectedMajors
        });
      }

      const res = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Thao tác thất bại');

      showToast(data.message || 'Thành công', 'success');
      
      if (modalState.type === 'bulk_delete' || modalState.type === 'delete_institute' || modalState.type === 'delete_major') {
        setSelectedInstitutes([]);
        setSelectedMajors([]);
      }
      
      fetchTree();
      closeModal();
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="admin-card" style={{ padding: '0', backgroundColor: 'transparent', boxShadow: 'none' }}>
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
          <div>
            <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Cơ cấu Đào tạo</h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
              Quản lý danh sách Trường/Viện và các Ngành đào tạo.
            </p>
          </div>
          
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            {/* Bulk Delete Button */}
            {(selectedInstitutes.length > 0 || selectedMajors.length > 0) && (
              <button 
                onClick={() => openModal('bulk_delete')} 
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#ef4444', color: 'white', borderRadius: '6px', border: 'none', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 500, transition: 'all 0.2s' }}
              >
                <Trash2 size={16} /> Xóa ({selectedInstitutes.length + selectedMajors.length})
              </button>
            )}

            {/* Upload Institute Button */}
            <div style={{ position: 'relative' }}>
              <input
                type="file"
                accept=".xlsx"
                id="upload-institute"
                style={{ display: 'none' }}
                onChange={(e) => handleFileUpload(e, 'import-institutes', setUploadingInstitute)}
                disabled={uploadingInstitute}
              />
              <label
                htmlFor="upload-institute"
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px',
                  backgroundColor: '#3b82f6', color: 'white', borderRadius: '6px', cursor: uploadingInstitute ? 'not-allowed' : 'pointer', fontWeight: '500', transition: 'background-color 0.2s', opacity: uploadingInstitute ? 0.7 : 1
                }}
              >
                <Upload size={18} />
                {uploadingInstitute ? 'Đang xử lý...' : 'Nhập Trường/Viện'}
              </label>
            </div>

            {/* Upload Major Button */}
            <div style={{ position: 'relative' }}>
              <input
                type="file"
                accept=".xlsx"
                id="upload-major"
                style={{ display: 'none' }}
                onChange={(e) => handleFileUpload(e, 'import-majors', setUploadingMajor)}
                disabled={uploadingMajor}
              />
              <label
                htmlFor="upload-major"
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px',
                  backgroundColor: '#10b981', color: 'white', borderRadius: '6px', cursor: uploadingMajor ? 'not-allowed' : 'pointer', fontWeight: '500', transition: 'background-color 0.2s', opacity: uploadingMajor ? 0.7 : 1
                }}
              >
                <Upload size={18} />
                {uploadingMajor ? 'Đang xử lý...' : 'Nhập Ngành'}
              </label>
            </div>
          </div>
        </div>

        {/* Tree View */}
        <div>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>Đang tải dữ liệu...</div>
          ) : treeData.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>
              Chưa có dữ liệu. Vui lòng tải file Excel lên.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* Checkbox "Chọn tất cả" or info header */}
              <div style={{ display: 'flex', padding: '0 16px 8px 16px', color: '#6b7280', fontSize: '0.9rem', fontWeight: 500, borderBottom: '1px solid #e5e7eb', marginBottom: '8px' }}>
                <div style={{ width: '32px' }}></div>
                <div style={{ flex: 1 }}>Cơ cấu tổ chức</div>
                <div style={{ width: '120px', textAlign: 'right', paddingRight: '8px' }}>Thao tác</div>
              </div>

              {treeData.map((institute) => (
                <div key={institute.institute_code} style={{ border: '1px solid #e5e7eb', borderRadius: '6px', overflow: 'hidden' }}>
                  {/* Institute Row */}
                  <div 
                    onClick={(e) => toggleNode(institute.institute_code, e)}
                    style={{ 
                      display: 'flex', alignItems: 'center', padding: '12px 16px', backgroundColor: '#f9fafb', cursor: 'pointer', userSelect: 'none'
                    }}
                  >
                    <div style={{ marginRight: '12px', display: 'flex', alignItems: 'center' }}>
                      <input 
                        type="checkbox" 
                        checked={selectedInstitutes.includes(institute.institute_code)}
                        onChange={(e) => handleSelectInstitute(e, institute.institute_code, institute.majors)}
                        onClick={(e) => e.stopPropagation()}
                        style={{ cursor: 'pointer' }}
                      />
                    </div>
                    <div style={{ marginRight: '12px', color: '#6b7280' }}>
                      {expandedNodes.has(institute.institute_code) ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                    </div>
                    <School size={20} style={{ marginRight: '12px', color: '#3b82f6' }} />
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                      <span style={{ fontWeight: '600', color: '#1f2937' }}>{institute.institute_name}</span>
                      <span style={{ marginLeft: '8px', fontSize: '12px', color: '#6b7280', backgroundColor: '#e5e7eb', padding: '2px 6px', borderRadius: '4px' }}>
                        {institute.institute_code}
                      </span>
                      <div style={{ fontSize: '12px', color: '#10b981', fontWeight: '600', backgroundColor: '#d1fae5', padding: '2px 8px', borderRadius: '12px', marginLeft: '12px' }}>
                        {institute.majors?.length || 0} ngành
                      </div>
                    </div>
                    
                    {/* Action buttons */}
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button onClick={(e) => { e.stopPropagation(); openModal('edit_institute', institute); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary-blue)' }} title="Sửa Trường/Viện">
                        <Edit size={18} />
                      </button>
                      <button onClick={(e) => { e.stopPropagation(); openModal('delete_institute', institute); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }} title="Xóa Trường/Viện">
                        <Trash2 size={18} />
                      </button>
                    </div>
                  </div>

                  {/* Majors List */}
                  {expandedNodes.has(institute.institute_code) && institute.majors && institute.majors.length > 0 && (
                    <div style={{ borderTop: '1px solid #e5e7eb' }}>
                      {institute.majors.map((major, index) => (
                        <div 
                          key={major.major_code} 
                          style={{ 
                            display: 'flex', alignItems: 'center', padding: '12px 16px 12px 16px',
                            borderBottom: index < institute.majors.length - 1 ? '1px solid #f3f4f6' : 'none',
                            backgroundColor: 'white'
                          }}
                        >
                          <div style={{ marginRight: '12px', marginLeft: '28px', display: 'flex', alignItems: 'center' }}>
                            <input 
                              type="checkbox" 
                              checked={selectedMajors.includes(major.major_code)}
                              onChange={(e) => handleSelectMajor(e, major.major_code)}
                              style={{ cursor: 'pointer' }}
                            />
                          </div>
                          <BookOpen size={18} style={{ marginRight: '12px', color: '#10b981' }} />
                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                              <span style={{ fontWeight: '500', color: '#374151' }}>{major.major_name}</span>
                              <span style={{ marginLeft: '8px', fontSize: '12px', color: '#6b7280', backgroundColor: '#f3f4f6', padding: '2px 6px', borderRadius: '4px' }}>
                                {major.major_code}
                              </span>
                            </div>
                          </div>
                          
                          {/* Action buttons */}
                          <div style={{ display: 'flex', gap: '12px' }}>
                            <button onClick={() => openModal('edit_major', { ...major, institute_code: institute.institute_code })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary-blue)' }} title="Sửa Ngành">
                              <Edit size={18} />
                            </button>
                            <button onClick={() => openModal('delete_major', major)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }} title="Xóa Ngành">
                              <Trash2 size={18} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ================= MODALS ================= */}
      {modalState.isOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          
          {modalState.type === 'bulk_delete' || modalState.type === 'delete_institute' || modalState.type === 'delete_major' ? (
            <div style={{ backgroundColor: 'white', padding: '24px', borderRadius: '12px', width: '400px', boxShadow: '0 10px 25px rgba(0,0,0,0.1)' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#dc2626', marginBottom: '16px', marginTop: 0 }}>
                <AlertCircle size={24} /> Xác nhận xóa
              </h3>
              <p style={{ color: '#4b5563', marginBottom: '24px', lineHeight: 1.5 }}>
                {modalState.type === 'bulk_delete' ? `Bạn có chắc chắn muốn xóa ${selectedInstitutes.length} Trường/Viện và ${selectedMajors.length} Ngành đã chọn?` : 
                 modalState.type === 'delete_institute' ? `Bạn có chắc chắn muốn xóa Trường/Viện "${modalState.data?.institute_name}" không? Toàn bộ ngành trực thuộc sẽ bị xóa.` :
                 `Bạn có chắc chắn muốn xóa Ngành "${modalState.data?.major_name}" không?`}
                <br /><br />Thao tác này không thể hoàn tác.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button onClick={closeModal} disabled={submitting} style={{ padding: '8px 16px', backgroundColor: '#f3f4f6', color: '#4b5563', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}>Hủy</button>
                <button onClick={handleSubmit} disabled={submitting} style={{ padding: '8px 16px', backgroundColor: '#dc2626', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}>
                  {submitting ? 'Đang xóa...' : 'Xóa dữ liệu'}
                </button>
              </div>
            </div>
          ) : (
            <div style={{ backgroundColor: '#fff', borderRadius: '12px', width: '100%', maxWidth: '500px', padding: '24px', boxShadow: '0 10px 25px rgba(0,0,0,0.15)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid #e5e7eb', paddingBottom: '16px' }}>
                <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#111827' }}>
                  {modalState.type === 'edit_institute' ? `Sửa Trường/Viện: ${modalState.data?.institute_code}` : `Sửa Ngành: ${modalState.data?.major_code}`}
                </h3>
              </div>
              
              <form onSubmit={handleSubmit}>
                {modalState.type === 'edit_institute' ? (
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', color: '#374151', fontWeight: 500 }}>Tên Trường/Viện <span style={{ color: 'red' }}>*</span></label>
                    <input 
                      type="text" 
                      required
                      value={formData.institute_name || ''}
                      onChange={(e) => setFormData({...formData, institute_name: e.target.value})}
                      style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #d1d5db', outline: 'none' }}
                      placeholder="Nhập tên trường/viện..."
                    />
                  </div>
                ) : (
                  <>
                    <div style={{ marginBottom: '16px' }}>
                      <label style={{ display: 'block', marginBottom: '8px', color: '#374151', fontWeight: 500 }}>Tên Ngành <span style={{ color: 'red' }}>*</span></label>
                      <input 
                        type="text" 
                        required
                        value={formData.major_name || ''}
                        onChange={(e) => setFormData({...formData, major_name: e.target.value})}
                        style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #d1d5db', outline: 'none' }}
                        placeholder="Nhập tên ngành..."
                      />
                    </div>
                    <div style={{ marginBottom: '16px' }}>
                      <label style={{ display: 'block', marginBottom: '8px', color: '#374151', fontWeight: 500 }}>Mã Trường/Viện trực thuộc <span style={{ color: 'red' }}>*</span></label>
                      <select 
                        required
                        value={formData.institute_code || ''}
                        onChange={(e) => setFormData({...formData, institute_code: e.target.value})}
                        style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid #d1d5db', outline: 'none', backgroundColor: 'white' }}
                      >
                        {treeData.map(inst => (
                          <option key={inst.institute_code} value={inst.institute_code}>{inst.institute_code} - {inst.institute_name}</option>
                        ))}
                      </select>
                    </div>
                  </>
                )}
                
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px', borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
                  <button type="button" onClick={closeModal} disabled={submitting} style={{ padding: '8px 16px', backgroundColor: '#f3f4f6', color: '#4b5563', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}>
                    Hủy bỏ
                  </button>
                  <button type="submit" disabled={submitting} style={{ padding: '8px 16px', backgroundColor: 'var(--primary-blue)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}>
                    {submitting ? 'Đang lưu...' : 'Lưu thay đổi'}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
