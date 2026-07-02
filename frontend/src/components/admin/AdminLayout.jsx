import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import AdminSidebar from './AdminSidebar';
import AdminNavbar from './AdminNavbar';

export default function AdminLayout() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [toast, setToast] = useState({ show: false, message: '', type: 'success' });

  const showToast = (message, type = 'success') => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast({ show: false, message: '', type: 'success' }), 4000);
  };

  return (
    <div className="admin-layout">
      {/* SIDEBAR */}
      <AdminSidebar 
        isMobileMenuOpen={isMobileMenuOpen} 
        setIsMobileMenuOpen={setIsMobileMenuOpen} 
      />

      {/* MAIN CONTAINER */}
      <div className="admin-main">
        {/* HEADER */}
        <AdminNavbar 
          isMobileMenuOpen={isMobileMenuOpen} 
          setIsMobileMenuOpen={setIsMobileMenuOpen} 
          showToast={showToast}
        />

        {/* PAGE CONTENT */}
        <div className="admin-content" style={{ overflowY: 'auto', flex: 1 }}>
          <Outlet context={{ showToast }} />
        </div>
      </div>

      {/* TOAST NOTIFICATION */}
      {toast.show && (
        <div style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          zIndex: 9999,
          padding: '16px 24px',
          backgroundColor: toast.type === 'success' ? '#14532d' : '#7f1d1d',
          color: toast.type === 'success' ? '#dcfce7' : '#fee2e2',
          border: `1.5px solid ${toast.type === 'success' ? '#22c55e' : '#ef4444'}`,
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          boxShadow: '8px 8px 0px rgba(0,0,0,0.3)',
          transition: 'all 0.3s ease'
        }}>
          {toast.type === 'success' ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
          <span style={{ fontWeight: 'bold', fontSize: '0.95rem' }}>{toast.message}</span>
        </div>
      )}
    </div>
  );
}
