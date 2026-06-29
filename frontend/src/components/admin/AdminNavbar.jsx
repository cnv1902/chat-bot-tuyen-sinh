import React from 'react';
import { Menu, X } from 'lucide-react';
import { useLocation } from 'react-router-dom';

export default function AdminNavbar({ isMobileMenuOpen, setIsMobileMenuOpen }) {
  const location = useLocation();

  const getPageTitle = () => {
    switch (location.pathname) {
      case '/admin/upload': return 'Nạp tài liệu tuyển sinh';
      case '/admin/manage': return 'Quản lý danh sách tài liệu';
      case '/admin/providers': return 'Cấu hình API Credentials';
      case '/admin/slots': return 'Phân chia nhiệm vụ Slots';
      case '/admin/status': return 'Trạng thái tích hợp';
      default: return 'Quản trị hệ thống';
    }
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
            {getPageTitle()}
          </h1>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{
          fontSize: '0.8rem',
          backgroundColor: '#e2e8f0',
          padding: '4px 10px',
          borderRadius: '12px',
          fontWeight: 'bold',
          color: '#475569'
        }}>
          v1.0.0
        </div>
        <div style={{
          width: '36px', height: '36px',
          backgroundColor: 'var(--primary-color)',
          borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#ffffff',
          fontWeight: 'bold',
          fontSize: '1rem',
          boxShadow: '0 4px 10px rgba(0,0,0,0.1)'
        }}>
          A
        </div>
      </div>
    </header>
  );
}
