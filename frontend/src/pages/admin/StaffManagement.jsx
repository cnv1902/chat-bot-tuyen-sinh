import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Users, Upload, Search, Shield, Building, Library, Plus, X, Trash2, Edit, Loader2, Camera } from 'lucide-react';
import DeleteConfirmModal from '../../components/admin/DeleteConfirmModal';
import DraggableStaffModal from '../../components/admin/DraggableStaffModal';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function StaffManagement() {
  const { showToast } = useOutletContext();
  const [staffList, setStaffList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, type: '', id: null, isDeleting: false });
  const [filterText, setFilterText] = useState('');
  const [institutes, setInstitutes] = useState([]);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingStaffData, setEditingStaffData] = useState(null);

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
        setInstitutes(data);
      }
    } catch (error) {
      console.error("Lỗi lấy danh sách trường/viện", error);
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
    const fd = new FormData();
    fd.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/api/staff/import`, {
        method: 'POST',
        body: fd
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
      (staff.role && staff.role.toLowerCase().includes(lowerFilter)) ||
      (staff.full_name && staff.full_name.toLowerCase().includes(lowerFilter))
    );
  });



  const handleDelete = async (id) => {
    setDeleteModal(prev => ({ ...prev, isDeleting: true }));
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
    } finally {
      setDeleteModal({ isOpen: false, type: '', id: null, isDeleting: false });
    }
  };

  const handleBulkDelete = async () => {
    setDeleteModal(prev => ({ ...prev, isDeleting: true }));
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
    } finally {
      setDeleteModal({ isOpen: false, type: '', id: null, isDeleting: false });
    }
  };

  const confirmDelete = () => {
    if (deleteModal.type === 'single') handleDelete(deleteModal.id);
    else if (deleteModal.type === 'bulk') handleBulkDelete();
  };

  const openAddModal = () => {
    setEditingStaffData(null);
    setIsModalOpen(true);
  };

  const openEditModal = (staff) => {
    setEditingStaffData(staff);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingStaffData(null);
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



  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="admin-card" style={{ padding: '24px', backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Cán bộ</h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
              Quản lý tài khoản và phân quyền cán bộ tư vấn tuyển sinh (Cấp Trường / Cấp Ngành).
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{ position: 'relative' }}>
              <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
              <input
                type="text"
                placeholder="Tìm Tên, Email hoặc Vai trò..."
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
                  onClick={() => setDeleteModal({ isOpen: true, type: 'bulk', id: null, isDeleting: false })}
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
                {uploading ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
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
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Họ tên</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Số điện thoại</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Email</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Đơn vị</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Vai trò</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Chương trình đào tạo</th>
                  <th style={{ padding: '14px 16px', textAlign: 'center', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Trạng thái</th>
                  <th style={{ padding: '14px 16px', textAlign: 'center', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredStaff.length === 0 ? (
                  <tr>
                    <td colSpan="9" style={{ padding: '30px', textAlign: 'center', color: '#64748b' }}>
                      Không tìm thấy dữ liệu cán bộ.
                    </td>
                  </tr>
                ) : (
                  filteredStaff.map(staff => (
                    <tr key={staff.id} style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.2s', backgroundColor: selectedRows.includes(staff.id) ? '#f0fdf4' : 'transparent' }} onMouseOver={e => { if (!selectedRows.includes(staff.id)) e.currentTarget.style.backgroundColor = '#f8fafc' }} onMouseOut={e => { if (!selectedRows.includes(staff.id)) e.currentTarget.style.backgroundColor = 'transparent' }}>
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          style={{ cursor: 'pointer' }}
                          checked={selectedRows.includes(staff.id)}
                          onChange={() => toggleSelectRow(staff.id)}
                        />
                      </td>
                      <td style={{ padding: '14px 16px', fontWeight: 500, color: '#0f172a' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <img
                            src={staff.avatar_url ? `${API_BASE}${staff.avatar_url}` : 'https://ui-avatars.com/api/?name=' + (staff.full_name || staff.email)}
                            alt="avatar"
                            style={{ width: '32px', height: '32px', borderRadius: '50%', objectFit: 'cover' }}
                          />
                          {staff.full_name || '-'}
                        </div>
                      </td>
                      <td style={{ padding: '14px 16px', color: '#334155' }}>
                        {staff.phone || '-'}
                      </td>
                      <td style={{ padding: '14px 16px', color: '#334155' }}>
                        {staff.email}
                      </td>
                      <td style={{ padding: '14px 16px', color: '#334155' }}>
                        {institutes.find(inst => inst.institute_code === staff.unit_code)?.institute_name || staff.unit_code || '-'}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        {staff.role === 'ADMIN' ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#fef3c7', color: '#b45309', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 600 }}>
                            <Shield size={14} /> CẤP HỆ THỐNG
                          </span>
                        ) : staff.role === 'STAFF_TRUONG' ? (
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
                          {staff.managed_programs ? (
                            staff.managed_programs.split(',').map((p, i) => (
                              <span key={i} style={{ display: 'inline-flex', padding: '2px 8px', backgroundColor: '#f1f5f9', color: '#334155', border: '1px solid #cbd5e1', borderRadius: '4px', fontSize: '0.8rem', fontWeight: 500 }}>
                                {p.trim()}
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
                        <button
                          onClick={() => setDeleteModal({ isOpen: true, type: 'single', id: staff.id, isDeleting: false })}
                          style={{ border: 'none', background: 'none', color: '#ef4444', cursor: 'pointer', padding: '4px' }}
                          title="Xóa"
                        >
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

      {/* ADD/EDIT MODAL */}
      <DraggableStaffModal
        isOpen={isModalOpen}
        onClose={closeModal}
        staffData={editingStaffData}
        onSuccess={fetchStaff}
        showToast={showToast}
      />

      <DeleteConfirmModal
        isOpen={deleteModal.isOpen}
        onClose={() => setDeleteModal({ isOpen: false, type: '', id: null, isDeleting: false })}
        onConfirm={confirmDelete}
        title="Xác nhận xóa cán bộ"
        description={deleteModal.type === 'bulk' ? `Bạn có chắc chắn muốn xóa ${selectedRows.length} cán bộ đã chọn? Hành động này không thể hoàn tác.` : "Bạn có chắc chắn muốn xóa cán bộ này? Hành động này không thể hoàn tác."}
        isDeleting={deleteModal.isDeleting}
      />
    </div>
  );
}
