import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function AdminLogin() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (response.ok) {
        // Lưu token vào localStorage
        localStorage.setItem('access_token', data.access_token);
        // Chuyển hướng người dùng vào trang dashboard (mặc định là /admin)
        navigate('/admin');
      } else {
        setErrorMsg(data.detail || 'Đăng nhập thất bại.');
      }
    } catch (error) {
      setErrorMsg('Không thể kết nối đến máy chủ.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      backgroundColor: '#387ac3'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '400px',
        padding: '32px',
        backgroundColor: 'var(--bg-main, #ffffff)',
        border: '1.5px solid var(--border-color, #e2e8f0)',
        boxShadow: '0 4px 6px rgba(0,0,0,0.05)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <h2 style={{ margin: '0', color: 'var(--text-main, #1e293b)' }}>ĐĂNG NHẬP</h2>
          <p style={{ margin: '8px 0 0', color: 'var(--text-muted, #64748b)', fontSize: '0.9rem' }}>
            Hệ thống quản trị Chatbot Tuyển sinh
          </p>
        </div>

        {errorMsg && (
          <div style={{
            padding: '12px',
            marginBottom: '16px',
            backgroundColor: '#fef2f2',
            borderLeft: '4px solid #ef4444',
            color: '#991b1b',
            fontSize: '0.85rem'
          }}>
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-main)' }}>
              Tên đăng nhập
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              style={{
                padding: '10px 12px',
                border: '1.5px solid var(--border-color, #e2e8f0)',
                fontSize: '1rem',
                outline: 'none'
              }}
              onFocus={(e) => e.target.style.borderColor = 'var(--primary-blue, #387ac3)'}
              onBlur={(e) => e.target.style.borderColor = 'var(--border-color, #e2e8f0)'}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-main)' }}>
              Mật khẩu
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{
                padding: '10px 12px',
                border: '1.5px solid var(--border-color, #e2e8f0)',
                fontSize: '1rem',
                outline: 'none'
              }}
              onFocus={(e) => e.target.style.borderColor = 'var(--primary-blue, #387ac3)'}
              onBlur={(e) => e.target.style.borderColor = 'var(--border-color, #e2e8f0)'}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: '8px',
              padding: '12px',
              backgroundColor: 'var(--primary-blue, #387ac3)',
              color: '#ffffff',
              fontWeight: 'bold',
              border: 'none',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              transition: 'opacity 0.2s'
            }}
          >
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>
      </div>
    </div>
  );
}
