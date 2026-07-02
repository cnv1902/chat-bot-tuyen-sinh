import React, { useState, useEffect } from 'react';
import { Menu, X, User, LogOut } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import DraggableStaffModal from './DraggableStaffModal';

export default function AdminNavbar({ isMobileMenuOpen, setIsMobileMenuOpen, showToast }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [showDropdown, setShowDropdown] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
    navigate('/admin/login');
  };

  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [userInfo, setUserInfo] = useState(() => {
    const str = localStorage.getItem('user_info');
    return str ? JSON.parse(str) : null;
  });

  useEffect(() => {
    const fetchMe = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/auth/me`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setUserInfo(data);
          localStorage.setItem('user_info', JSON.stringify(data));
        }
      } catch (err) {
        console.error("Lỗi lấy thông tin user", err);
      }
    };
    fetchMe();
  }, []);
  const handleProfileUpdated = () => {
    // Bỏ qua việc lưu object trả về (vì API chỉ trả về {"message": "..."})
    // Thay vào đó, tải lại trang để useEffect tự động gọi /api/auth/me và lưu bản cập nhật chính xác
    window.location.reload(); 
  };

  const getInitial = () => {
    if (!userInfo) return 'U';
    const nameStr = userInfo.full_name || userInfo.email || 'User';
    const words = nameStr.trim().split(' ');
    const lastWord = words[words.length - 1];
    return lastWord.charAt(0).toUpperCase();
  };

  return (
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
            border: 'none',
            cursor: 'pointer'
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
            Quản trị hệ thống
          </h1>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', position: 'relative' }}>
        <div
          onClick={() => setShowDropdown(!showDropdown)}
          style={{
            width: '36px', height: '36px',
            backgroundColor: 'var(--primary-color, #387ac3)',
            borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#ffffff',
            fontWeight: 'bold',
            fontSize: '1rem',
            boxShadow: '0 4px 10px rgba(0,0,0,0.1)',
            cursor: 'pointer',
            overflow: 'hidden'
          }}
        >
          {userInfo?.avatar_url ? (
            <img 
              src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${userInfo.avatar_url}`} 
              alt="Avatar" 
              style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
            />
          ) : (
            getInitial()
          )}
        </div>

        {showDropdown && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '8px',
            backgroundColor: '#ffffff',
            borderRadius: '8px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
            border: '1px solid #e2e8f0',
            width: '200px',
            zIndex: 100,
            overflow: 'hidden'
          }}>
            <button
              onClick={() => { setShowDropdown(false); setIsProfileModalOpen(true); }}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 16px',
                backgroundColor: 'transparent',
                border: 'none',
                borderBottom: '1px solid #f1f5f9',
                cursor: 'pointer',
                fontSize: '0.9rem',
                color: '#334155',
                textAlign: 'left'
              }}
              onMouseOver={e => e.currentTarget.style.backgroundColor = '#f8fafc'}
              onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <User size={16} />
              Hồ sơ
            </button>
            <button
              onClick={handleLogout}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 16px',
                backgroundColor: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.9rem',
                color: '#ef4444',
                textAlign: 'left'
              }}
              onMouseOver={e => e.currentTarget.style.backgroundColor = '#fef2f2'}
              onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <LogOut size={16} />
              Đăng xuất
            </button>
          </div>
        )}
      </div>

      <DraggableStaffModal 
        isOpen={isProfileModalOpen} 
        onClose={() => setIsProfileModalOpen(false)} 
        staffData={userInfo} 
        onSuccess={handleProfileUpdated}
        showToast={showToast}
        isProfileMode={true}
      />
    </header>
  );
}
