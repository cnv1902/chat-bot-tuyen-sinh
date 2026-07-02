import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { FileText, FolderOpen, Key, Cpu, Activity, ArrowLeft, Users, UserCheck, Hash, MessageCircle } from 'lucide-react';

export default function AdminSidebar({ isMobileMenuOpen, setIsMobileMenuOpen }) {
  const navigate = useNavigate();

  const handleNavClick = () => {
    setIsMobileMenuOpen(false);
  };

  return (
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
            <h2 style={{ fontSize: '1rem', color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>
              Bộ phận tuyển sinh
            </h2>
          </div>
        </div>
      </div>

      <nav className="admin-sidebar-menu">
        <NavLink
          to="/admin/documents"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <FileText size={18} />
          Quản lý & Upload Tài liệu
        </NavLink>
        <NavLink
          to="/admin/qa-approval"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <Activity size={18} />
          Kiểm duyệt Q&A Cache
        </NavLink>
        <NavLink
          to="/admin/support"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <MessageCircle size={18} />
          Hỗ trợ trực tuyến
        </NavLink>
        <NavLink
          to="/admin/academic-structure"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <FolderOpen size={18} />
          Cơ cấu Đào tạo
        </NavLink>
        <NavLink
          to="/admin/admission-codes"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <Hash size={18} />
          Quản lý Mã Xét Tuyển
        </NavLink>
        <NavLink
          to="/admin/admission-plans"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <FileText size={18} />
          Đề án Tuyển sinh
        </NavLink>
        <NavLink
          to="/admin/staff"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <Users size={18} />
          Quản lý Cán bộ
        </NavLink>
        <NavLink
          to="/admin/candidates"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <UserCheck size={18} />
          Quản lý Thí sinh
        </NavLink>
        <NavLink
          to="/admin/providers"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <Key size={18} />
          Cấu hình API Keys
        </NavLink>

        <NavLink
          to="/admin/slots"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <Cpu size={18} />
          Cấu hình Model Slots
        </NavLink>

        <NavLink
          to="/admin/status"
          className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          onClick={handleNavClick}
        >
          <Activity size={18} />
          Trạng thái hệ thống
        </NavLink>
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
            fontWeight: 'bold',
            cursor: 'pointer'
          }}
          onMouseOver={e => e.currentTarget.style.backgroundColor = 'var(--border-color)'}
          onMouseOut={e => e.currentTarget.style.backgroundColor = 'var(--bg-main)'}
        >
          <ArrowLeft size={16} />
          QUAY LẠI CHATBOT
        </button>
      </div>
    </aside>
  );
}
