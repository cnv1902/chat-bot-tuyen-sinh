import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function GoogleCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const [status, setStatus] = useState('Đang xử lý đăng nhập...');

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get('code');

    if (!code) {
      setStatus('Không tìm thấy mã xác thực từ Google.');
      setTimeout(() => navigate('/'), 3000);
      return;
    }

    const authenticateWithGoogle = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/auth/google`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ code })
        });

        if (response.ok) {
          const data = await response.json();
          // Lưu token vào localStorage (tương tự như Admin login)
          localStorage.setItem('access_token', data.access_token);
          // data không có trường user (do TokenResponse định nghĩa), ta chỉ cần check data.role
          setStatus('Đăng nhập thành công! Đang chuyển hướng...');
          
          if (['ADMIN', 'STAFF_TRUONG', 'STAFF_NGANH'].includes(data.role)) {
            setTimeout(() => navigate('/admin'), 1000);
          } else {
            setTimeout(() => navigate('/'), 1000);
          }
        } else {
          const errorData = await response.json();
          setStatus(`Đăng nhập thất bại: ${errorData.detail || 'Lỗi không xác định'}`);
          setTimeout(() => navigate('/'), 3000);
        }
      } catch (err) {
        setStatus('Lỗi kết nối đến máy chủ.');
        setTimeout(() => navigate('/'), 3000);
      }
    };

    authenticateWithGoogle();
  }, [location, navigate]);

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#f1f5f9',
      fontFamily: 'sans-serif'
    }}>
      <div style={{
        padding: '30px',
        backgroundColor: '#fff',
        borderRadius: '8px',
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
        textAlign: 'center'
      }}>
        <h2>Xác thực Google</h2>
        <p>{status}</p>
      </div>
    </div>
  );
}
