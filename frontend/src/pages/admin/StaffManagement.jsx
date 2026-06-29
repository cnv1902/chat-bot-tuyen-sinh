import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Users, Upload, Search, Shield, Building, Library, Plus, X, Trash2, Edit } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function StaffManagement() {
  const { showToast } = useOutletContext();
  const [staffList, setStaffList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [filterText, setFilterText] = useState('');
  
  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editingStaffId, setEditingStaffId] = useState(null);
  const [availableInstitutes, setAvailableInstitutes] = useState([]);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    role: 'STAFF_NGANH',
    major_codes: [],
    is_active: true
  });
  
  const [selectedRows, setSelectedRows] = useState([]);

  const fileInputRef = useRef(null);

  const fetchStaff = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/staff/list`);
      if (res.ok) {
        const data = await res.json();
        setStaffList(data);
      } else {
        const err = await res.json();
        showToast(err.detail || 'Lỗi lấy danh sách cán bộ', 'error');
      }
    } catch (error) {
      showToast('Lỗi kết nối tới máy chủ API.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const fetchInstitutes = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/academic/tree`);
      if (res.ok) {
        const data = await res.json();
        setAvailableInstitutes(data);
      }
    } catch (error) {
      console.error("Lỗi lấy danh sách ngành:", error);
    }
  };

  useEffect(() => {
    fetchStaff();
    fetchInstitutes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/api/staff/import`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (res.ok) {
        showToast(`Import thành công ${data.imported_count} cán bộ!`, 'success');
        fetchStaff();
      } else {
        showToast(data.detail || 'Lỗi khi import file Excel.', 'error');
      }
    } catch (err) {
      showToast('Lỗi mạng, không upload được file.', 'error');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const filteredStaff = staffList.filter(staff => {
    if (!filterText) return true;
    const lowerFilter = filterText.toLowerCase();
    return (
      (staff.email && staff.email.toLowerCase().includes(lowerFilter)) ||
      (staff.role && staff.role.toLowerCase().includes(lowerFilter))
    );
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.email) {
      showToast('Vui lòng nhập Email', 'error');
      return;
    }
    
    setSubmitting(true);
    try {
      const payload = {
        email: formData.email,
        password: formData.password || (editingStaffId ? null : '123'),
        role: formData.role,
        major_codes: formData.role === 'STAFF_NGANH' ? formData.major_codes : [],
        is_active: formData.is_active
      };

      const url = editingStaffId 
        ? `${API_BASE}/api/staff/update/${editingStaffId}` 
        : `${API_BASE}/api/staff/create`;
      const method = editingStaffId ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      if (res.ok) {
        showToast(editingStaffId ? 'Cập nhật cán bộ thành công!' : 'Thêm cán bộ thành công!', 'success');
        closeModal();
        fetchStaff();
      } else {
        showToast(data.detail || 'Có lỗi xảy ra', 'error');
      }
    } catch (err) {
      showToast('Lỗi mạng, không kết nối được server.', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Bạn có chắc chắn muốn xóa cán bộ này?')) return;
    try {
      const res = await fetch(`${API_BASE}/api/staff/delete/${id}`, { method: 'DELETE' });
      if (res.ok) {
        showToast('Xóa cán bộ thành công', 'success');
        fetchStaff();
      } else {
        showToast('Lỗi xóa cán bộ', 'error');
      }
    } catch (err) {
      showToast('Lỗi mạng', 'error');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedRows.length === 0) return;
    if (!window.confirm(`Xóa ${selectedRows.length} cán bộ đã chọn?`)) return;

    try {
      const res = await fetch(`${API_BASE}/api/staff/bulk-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedRows })
      });
      if (res.ok) {
        showToast(`Đã xóa ${selectedRows.length} cán bộ`, 'success');
        setSelectedRows([]);
        fetchStaff();
      } else {
        showToast('Lỗi xóa hàng loạt', 'error');
      }
    } catch (err) {
      showToast('Lỗi mạng', 'error');
    }
  };

  const openAddModal = () => {
    setEditingStaffId(null);
    setFormData({ email: '', password: '', role: 'STAFF_NGANH', major_codes: [], is_active: true });
    setIsModalOpen(true);
  };

  const openEditModal = (staff) => {
    setEditingStaffId(staff.id);
    setFormData({
      email: staff.email,
      password: '',
      role: staff.role,
      major_codes: staff.major_codes || [],
      is_active: staff.is_active
    });
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingStaffId(null);
  };

  const toggleSelectAll = () => {
    if (selectedRows.length === filteredStaff.length && filteredStaff.length > 0) {
      setSelectedRows([]);
    } else {
      setSelectedRows(filteredStaff.map(s => s.id));
    }
  };

  const toggleSelectRow = (id) => {
    if (selectedRows.includes(id)) {
      setSelectedRows(selectedRows.filter(rid => rid !== id));
    } else {
      setSelectedRows([...selectedRows, id]);
    }
  };

  const handleToggleMajor = (majorCode) => {
    setFormData(prev => {
      const isSelected = prev.major_codes.includes(majorCode);
      if (isSelected) {
        return { ...prev, major_codes: prev.major_codes.filter(c => c !== majorCode) };
      } else {
        return { ...prev, major_codes: [...prev.major_codes, majorCode] };
      }
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="admin-card" style={{ padding: '24px', backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              Quản lý Cán bộ
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
              Quản lý tài khoản và phân quyền cán bộ tư vấn tuyển sinh (Cấp Trường / Cấp Ngành).
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{ position: 'relative' }}>
              <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
              <input
                type="text"
                placeholder="Tìm Email hoặc Vai trò..."
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                style={{
                  padding: '10px 14px 10px 38px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '0.9rem',
                  outline: 'none',
                  width: '250px'
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              {selectedRows.length > 0 && (
                <button
                  onClick={handleBulkDelete}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '8px',
                    backgroundColor: '#ef4444', color: '#fff', padding: '10px 16px',
                    borderRadius: '6px', fontWeight: 'bold', fontSize: '0.9rem', border: 'none', cursor: 'pointer'
                  }}
                >
                  <Trash2 size={18} />
                  Xóa ({selectedRows.length})
                </button>
              )}

              <button
                onClick={openAddModal}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  backgroundColor: '#10b981',
                  color: '#fff',
                  padding: '10px 16px',
                  borderRadius: '6px',
                  fontWeight: 'bold',
                  fontSize: '0.9rem',
                  border: 'none',
                  cursor: 'pointer'
                }}
              >
                <Plus size={18} />
                Thêm mới
              </button>
              
              <input
                type="file"
                accept=".xlsx, .xls"
                ref={fileInputRef}
                style={{ display: 'none' }}
                onChange={handleImport}
                disabled={uploading}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  backgroundColor: uploading ? '#9ca3af' : 'var(--primary-blue)',
                  color: '#fff',
                  padding: '10px 16px',
                  borderRadius: '6px',
                  fontWeight: 'bold',
                  fontSize: '0.9rem',
                  border: 'none',
                  cursor: uploading ? 'not-allowed' : 'pointer'
                }}
              >
                <Upload size={18} />
                {uploading ? 'Đang import...' : 'Import Excel'}
              </button>
            </div>
          </div>
        </div>

        {/* DATA TABLE */}
        <div style={{ overflowX: 'auto' }}>
          {loading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
              Đang tải dữ liệu...
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.95rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '14px 16px', width: '40px', textAlign: 'center' }}>
                    <input 
                      type="checkbox" 
                      style={{ cursor: 'pointer' }}
                      checked={selectedRows.length > 0 && selectedRows.length === filteredStaff.length}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Email</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Vai trò</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Ngành phụ trách</th>
                  <th style={{ padding: '14px 16px', textAlign: 'center', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Trạng thái</th>
                  <th style={{ padding: '14px 16px', textAlign: 'center', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredStaff.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ padding: '30px', textAlign: 'center', color: '#64748b' }}>
                      Không tìm thấy dữ liệu cán bộ.
                    </td>
                  </tr>
                ) : (
                  filteredStaff.map(staff => (
                    <tr key={staff.id} style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.2s', backgroundColor: selectedRows.includes(staff.id) ? '#f0fdf4' : 'transparent' }} onMouseOver={e => {if(!selectedRows.includes(staff.id)) e.currentTarget.style.backgroundColor = '#f8fafc'}} onMouseOut={e => {if(!selectedRows.includes(staff.id)) e.currentTarget.style.backgroundColor = 'transparent'}}>
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <input 
                          type="checkbox" 
                          style={{ cursor: 'pointer' }}
                          checked={selectedRows.includes(staff.id)}
                          onChange={() => toggleSelectRow(staff.id)}
                        />
                      </td>
                      <td style={{ padding: '14px 16px', fontWeight: 500, color: '#0f172a' }}>
                        {staff.email}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        {staff.role === 'STAFF_TRUONG' ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#e0e7ff', color: '#4338ca', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 600 }}>
                            <Building size={14} /> CẤP TRƯỜNG
                          </span>
                        ) : (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#dcfce7', color: '#166534', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 600 }}>
                            <Library size={14} /> CẤP NGÀNH
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {staff.major_codes && staff.major_codes.length > 0 ? (
                            staff.major_codes.map(mc => (
                              <span key={mc} style={{ display: 'inline-flex', padding: '2px 8px', backgroundColor: '#f1f5f9', color: '#334155', border: '1px solid #cbd5e1', borderRadius: '4px', fontSize: '0.8rem', fontWeight: 500 }}>
                                {mc}
                              </span>
                            ))
                          ) : (
                            <span style={{ color: '#9ca3af', fontStyle: 'italic', fontSize: '0.85rem' }}>-</span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: staff.is_active ? '#dcfce7' : '#fee2e2', color: staff.is_active ? '#166534' : '#991b1b', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 600 }}>
                          {staff.is_active ? 'HOẠT ĐỘNG' : 'BỊ KHÓA'}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <button onClick={() => openEditModal(staff)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary-blue)', marginRight: '10px' }} title="Sửa">
                          <Edit size={18} />
                        </button>
                        <button onClick={() => handleDelete(staff.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }} title="Xóa">
                          <Trash2 size={18} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
      
      {/* ADD NEW MODAL */}
      {isModalOpen && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: '#fff', padding: '24px', borderRadius: '12px', width: '450px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.15)', maxHeight: '90vh', overflowY: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#1e293b' }}>{editingStaffId ? 'Sửa Cán bộ' : 'Thêm Cán bộ'}</h3>
              <button onClick={closeModal} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b' }}>
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Email (*)</label>
                <input 
                  type="email" 
                  required
                  disabled={!!editingStaffId}
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }}
                  placeholder="Ví dụ: nva@vinhuni.edu.vn"
                />
              </div>
              
              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Mật khẩu {editingStaffId && '(để trống nếu không đổi)'}</label>
                <input 
                  type="text" 
                  value={formData.password}
                  onChange={(e) => setFormData({...formData, password: e.target.value})}
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }}
                  placeholder={editingStaffId ? "Nhập mật khẩu mới..." : "Mặc định: 123"}
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Vai trò (*)</label>
                <select 
                  value={formData.role}
                  onChange={(e) => setFormData({...formData, role: e.target.value})}
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#fff', boxSizing: 'border-box' }}
                >
                  <option value="STAFF_NGANH">Cấp Ngành (Phụ trách ngành cụ thể)</option>
                  <option value="STAFF_TRUONG">Cấp Trường (Toàn quyền quản lý)</option>
                </select>
              </div>

              {formData.role === 'STAFF_NGANH' && (
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Ngành phụ trách (chọn nhiều)</label>
                  <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '10px', backgroundColor: '#f8fafc' }}>
                    {availableInstitutes.length === 0 ? (
                      <span style={{ color: '#64748b', fontSize: '0.85rem' }}>Đang tải danh sách ngành...</span>
                    ) : (
                      availableInstitutes.map(inst => (
                        <div key={inst.institute_code} style={{ marginBottom: '12px' }}>
                          <div style={{ fontWeight: 600, color: 'var(--primary-blue)', marginBottom: '6px', fontSize: '0.85rem' }}>{inst.institute_name}</div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', paddingLeft: '8px' }}>
                            {inst.majors.map(m => (
                              <label key={m.major_code} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', cursor: 'pointer', color: '#334155' }}>
                                <input 
                                  type="checkbox" 
                                  checked={formData.major_codes.includes(m.major_code)}
                                  onChange={() => handleToggleMajor(m.major_code)}
                                  style={{ cursor: 'pointer' }}
                                />
                                {m.major_name}
                              </label>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {editingStaffId && (
                <div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', fontWeight: 500, color: '#475569', cursor: 'pointer' }}>
                    <input 
                      type="checkbox" 
                      checked={formData.is_active}
                      onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                      style={{ cursor: 'pointer' }}
                    />
                    Tài khoản đang hoạt động
                  </label>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button type="button" onClick={closeModal} style={{ padding: '10px 16px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#fff', cursor: 'pointer', fontWeight: 500 }}>
                  Hủy
                </button>
                <button type="submit" disabled={submitting} style={{ padding: '10px 16px', borderRadius: '6px', border: 'none', background: 'var(--primary-blue)', color: '#fff', cursor: submitting ? 'not-allowed' : 'pointer', fontWeight: 500 }}>
                  {submitting ? 'Đang lưu...' : (editingStaffId ? 'Cập nhật' : 'Thêm mới')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
