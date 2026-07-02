import React, { useState, useRef, useEffect } from 'react';
import { X, Camera } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function DraggableStaffModal({ isOpen, onClose, staffData, onSuccess, showToast, isProfileMode = false }) {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    role: 'STAFF_NGANH',
    managed_programs: '',
    is_active: true,
    full_name: '',
    phone: '',
    unit_code: ''
  });
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreviewUrl, setAvatarPreviewUrl] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const avatarInputRef = useRef(null);

  // Drag logic
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const [institutes, setInstitutes] = useState([]);

  useEffect(() => {
    if (isOpen) {
      // Reset position when opened
      setPosition({ x: 0, y: 0 });
      if (staffData) {
        setFormData({
          email: staffData.email || '',
          password: '',
          role: staffData.role || 'STAFF_NGANH',
          managed_programs: staffData.managed_programs || '',
          is_active: staffData.is_active !== undefined ? staffData.is_active : true,
          full_name: staffData.full_name || '',
          phone: staffData.phone || '',
          unit_code: staffData.unit_code || '',
        });
        setAvatarPreviewUrl(staffData.avatar_url ? `${API_BASE}${staffData.avatar_url}` : null);
      } else {
        setFormData({ email: '', password: '', role: 'STAFF_NGANH', managed_programs: '', is_active: true, full_name: '', phone: '', unit_code: '' });
        setAvatarPreviewUrl(null);
      }
      setAvatarFile(null);

      if (institutes.length === 0) {
        fetch(`${API_BASE}/api/academic/tree`)
          .then(res => res.json())
          .then(data => setInstitutes(data))
          .catch(err => console.error("Lỗi lấy danh sách trường/viện", err));
      }
    }
  }, [isOpen, staffData]);

  const handleMouseDown = (e) => {
    setIsDragging(true);
    dragStart.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y
    };
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    } else {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  if (!isOpen) return null;

  const handleAvatarChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setAvatarFile(file);
      const url = URL.createObjectURL(file);
      setAvatarPreviewUrl(url);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.email) {
      if (showToast) showToast('Vui lòng nhập Email', 'error');
      else alert('Vui lòng nhập Email');
      return;
    }

    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append('email', formData.email);
      if (formData.password || !staffData) {
        fd.append('password', formData.password || '123');
      }
      fd.append('role', formData.role);
      fd.append('is_active', formData.is_active);
      if (formData.role === 'STAFF_NGANH' && formData.managed_programs?.trim()) {
        fd.append('managed_programs', formData.managed_programs.trim());
      }
      fd.append('full_name', formData.full_name || '');
      fd.append('phone', formData.phone || '');
      fd.append('unit_code', formData.unit_code || '');
      if (avatarFile) fd.append('avatar', avatarFile);

      const targetId = staffData?.id || staffData?.account_id;

      const url = targetId
        ? `${API_BASE}/api/staff/update/${targetId}`
        : `${API_BASE}/api/staff/create`;
      const method = targetId ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method,
        body: fd
      });

      const data = await res.json();
      if (res.ok) {
        if (showToast) showToast(targetId ? 'Cập nhật hồ sơ thành công!' : 'Thêm cán bộ thành công!', 'success');
        onClose();
        if (onSuccess) onSuccess(data);
      } else {
        if (showToast) showToast(data.detail || 'Có lỗi xảy ra', 'error');
        else alert(data.detail || 'Có lỗi xảy ra');
      }
    } catch (err) {
      if (showToast) showToast('Lỗi mạng, không kết nối được server.', 'error');
      else alert('Lỗi mạng, không kết nối được server.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: `translate(calc(-50% + ${position.x}px), calc(-50% + ${position.y}px))`,
      backgroundColor: '#fff',
      padding: '0',
      borderRadius: '12px',
      width: '500px',
      boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      maxHeight: '90vh',
      border: '1px solid #e2e8f0'
    }}>
      {/* Draggable Header */}
      <div
        onMouseDown={handleMouseDown}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 24px',
          borderBottom: '1px solid #f1f5f9',
          cursor: isDragging ? 'grabbing' : 'grab',
          backgroundColor: '#f8fafc',
          borderTopLeftRadius: '12px',
          borderTopRightRadius: '12px',
          userSelect: 'none'
        }}
      >
        <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#1e293b' }}>
          {staffData ? 'Hồ sơ Cán bộ' : 'Thêm Cán bộ'}
        </h3>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', padding: '4px' }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <X size={20} />
        </button>
      </div>

      {/* Form Content */}
      <div style={{ padding: '24px', overflowY: 'auto' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px' }}>
            <div
              onClick={() => avatarInputRef.current?.click()}
              style={{
                width: '90px', height: '90px', borderRadius: '50%',
                border: '2px dashed #cbd5e1', display: 'flex',
                justifyContent: 'center', alignItems: 'center',
                cursor: 'pointer', overflow: 'hidden', backgroundColor: '#f8fafc',
                position: 'relative'
              }}
              title="Nhấn để tải lên ảnh đại diện"
            >
              {avatarPreviewUrl ? (
                <img src={avatarPreviewUrl} alt="Avatar preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              ) : (
                <Camera size={32} color="#94a3b8" />
              )}
              <input
                type="file"
                accept="image/*"
                ref={avatarInputRef}
                style={{ display: 'none' }}
                onChange={handleAvatarChange}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '16px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Họ tên</label>
              <input
                type="text"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }}
                placeholder="Ví dụ: Nguyễn Văn A"
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Số điện thoại</label>
              <input
                type="text"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }}
                placeholder="Ví dụ: 0912345678"
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '16px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Đơn vị (Trường/Viện)</label>
              <select
                value={formData.unit_code}
                onChange={(e) => setFormData({ ...formData, unit_code: e.target.value })}
                style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#fff', boxSizing: 'border-box' }}
              >
                <option value="">-- Chọn đơn vị --</option>
                {institutes.map(inst => (
                  <option key={inst.institute_code} value={inst.institute_code}>
                    {inst.institute_name}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Email (*)</label>
              <input
                type="email"
                required
                disabled={!!staffData}
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', boxSizing: 'border-box', backgroundColor: staffData ? '#f1f5f9' : '#fff' }}
                placeholder="Ví dụ: nva@vinhuni.edu.vn"
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Mật khẩu {staffData && '(để trống nếu không đổi)'}</label>
            <input
              type="text"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }}
              placeholder={staffData ? "Nhập mật khẩu mới..." : "Mặc định: 123"}
            />
          </div>

          {!isProfileMode && (
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Vai trò (*)</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#fff', boxSizing: 'border-box' }}
              >
                <option value="STAFF_NGANH">Cấp Ngành (Phụ trách ngành cụ thể)</option>
                <option value="STAFF_TRUONG">Cấp Trường (Toàn quyền quản lý)</option>
                <option value="ADMIN">Cấp Hệ Thống (Quản trị viên)</option>
              </select>
            </div>
          )}

          {!isProfileMode && formData.role === 'STAFF_NGANH' && (
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.9rem', fontWeight: 500, color: '#475569' }}>Chương trình đào tạo (Các ngành quản lý)</label>
              <div style={{
                maxHeight: '200px',
                overflowY: 'auto',
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                padding: '10px',
                backgroundColor: '#f8fafc'
              }}>
                {institutes.map(inst => (
                  <div key={inst.institute_code} style={{ marginBottom: '12px' }}>
                    <div style={{ fontWeight: 600, color: '#334155', borderBottom: '1px solid #e2e8f0', paddingBottom: '4px', marginBottom: '8px', fontSize: '0.9rem' }}>
                      {inst.institute_name}
                    </div>
                    {inst.majors && inst.majors.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', paddingLeft: '8px' }}>
                        {inst.majors.map(major => {
                          const currentPrograms = formData.managed_programs ? formData.managed_programs.split(',').map(s => s.trim()).filter(Boolean) : [];
                          const isChecked = currentPrograms.includes(major.major_code);
                          return (
                            <label key={major.major_code} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', cursor: 'pointer', color: '#475569' }}>
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => {
                                  let newPrograms = [...currentPrograms];
                                  if (isChecked) {
                                    newPrograms = newPrograms.filter(c => c !== major.major_code);
                                  } else {
                                    newPrograms.push(major.major_code);
                                  }
                                  setFormData({ ...formData, managed_programs: newPrograms.join(', ') });
                                }}
                                style={{ cursor: 'pointer' }}
                              />
                              {major.major_name} ({major.major_code})
                            </label>
                          );
                        })}
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.8rem', color: '#94a3b8', paddingLeft: '8px' }}>Không có ngành nào</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!isProfileMode && staffData && (
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', fontWeight: 500, color: '#475569', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  style={{ cursor: 'pointer' }}
                />
                Tài khoản đang hoạt động
              </label>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button type="button" onClick={onClose} style={{ padding: '10px 16px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#fff', cursor: 'pointer', fontWeight: 500 }}>
              Hủy
            </button>
            <button type="submit" disabled={submitting} style={{ padding: '10px 16px', borderRadius: '6px', border: 'none', background: 'var(--primary-blue)', color: '#fff', cursor: submitting ? 'not-allowed' : 'pointer', fontWeight: 500 }}>
              {submitting ? 'Đang lưu...' : (staffData ? 'Cập nhật' : 'Thêm mới')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
