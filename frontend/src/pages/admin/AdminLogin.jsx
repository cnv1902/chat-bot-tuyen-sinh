import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { GoogleOAuthProvider, useGoogleLogin } from '@react-oauth/google';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || 'your_google_client_id_here';

function AdminLoginForm() {
  const [loginState, setLoginState] = useState('LOGIN'); // 'LOGIN' or 'VERIFY'
  
  // LOGIN STATE
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  
  // VERIFY STATE
  const [otpCode, setOtpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [countdown, setCountdown] = useState(0);

  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);
  
  const navigate = useNavigate();

  useEffect(() => {
    let timer;
    if (countdown > 0) {
      timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [countdown]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (response.ok) {
        if (data.status === 'require_verification') {
          setLoginState('VERIFY');
          setSuccessMsg('Vui lòng tạo mật khẩu mới và xác thực OTP.');
        } else {
          localStorage.setItem('access_token', data.access_token);
          navigate('/admin');
        }
      } else {
        setErrorMsg(data.detail || 'Đăng nhập thất bại.');
      }
    } catch (error) {
      setErrorMsg('Không thể kết nối đến máy chủ.');
    } finally {
      setLoading(false);
    }
  };

  const handleSendOtp = async () => {
    if (countdown > 0) return;
    setErrorMsg('');
    setSuccessMsg('');
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/auth/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: username }),
      });
      const data = await response.json();
      if (response.ok) {
        setSuccessMsg(data.detail || 'Mã OTP đã được gửi đến email của bạn.');
        setCountdown(60);
      } else {
        setErrorMsg(data.detail || 'Lỗi gửi OTP.');
      }
    } catch (error) {
      setErrorMsg('Lỗi kết nối.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setErrorMsg('Mật khẩu xác nhận không khớp.');
      return;
    }
    if (!otpCode || otpCode.length !== 6) {
      setErrorMsg('Mã OTP phải gồm 6 chữ số.');
      return;
    }

    setErrorMsg('');
    setSuccessMsg('');
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/auth/verify-first-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email: username, 
          otp_code: otpCode, 
          new_password: newPassword 
        }),
      });

      const data = await response.json();

      if (response.ok) {
        localStorage.setItem('access_token', data.access_token);
        navigate('/admin');
      } else {
        setErrorMsg(data.detail || 'Xác thực thất bại.');
      }
    } catch (error) {
      setErrorMsg('Lỗi kết nối.');
    } finally {
      setLoading(false);
    }
  };

  const googleLogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      setLoading(true);
      setErrorMsg('');
      try {
        // Fetch user info from Google
        const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
          headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
        });
        const userInfo = await res.json();
        
        if (!userInfo.email) {
          setErrorMsg('Không lấy được Email từ tài khoản Google.');
          setLoading(false);
          return;
        }

        // Gửi email lên backend
        const authRes = await fetch(`${API_BASE}/api/auth/google-login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: userInfo.email, google_token: tokenResponse.access_token }),
        });
        
        const authData = await authRes.json();
        
        if (authRes.ok) {
          localStorage.setItem('access_token', authData.access_token);
          navigate('/admin');
        } else {
          // Lỗi 403 hoặc lỗi khác
          if (authRes.status === 403) {
            navigate('/chat');
          } else {
            setErrorMsg(authData.detail || 'Đăng nhập Google thất bại.');
          }
        }
      } catch (error) {
        setErrorMsg('Lỗi kết nối xác thực Google.');
      } finally {
        setLoading(false);
      }
    },
    onError: () => {
      setErrorMsg('Đăng nhập Google thất bại.');
    }
  });

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', backgroundColor: '#387ac3'
    }}>
      <div style={{
        width: '100%', maxWidth: '420px', padding: '32px',
        backgroundColor: 'var(--bg-main, #ffffff)', border: '1.5px solid var(--border-color, #e2e8f0)',
        boxShadow: '0 4px 6px rgba(0,0,0,0.05)', borderRadius: '8px'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <h2 style={{ margin: '0', color: 'var(--text-main, #1e293b)' }}>
            {loginState === 'LOGIN' ? 'ĐĂNG NHẬP' : 'XÁC THỰC LẦN ĐẦU'}
          </h2>
          <p style={{ margin: '8px 0 0', color: 'var(--text-muted, #64748b)', fontSize: '0.9rem' }}>
            Hệ thống quản trị Chatbot Tuyển sinh
          </p>
        </div>

        {errorMsg && (
          <div style={{ padding: '12px', marginBottom: '16px', backgroundColor: '#fef2f2', borderLeft: '4px solid #ef4444', color: '#991b1b', fontSize: '0.85rem' }}>
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div style={{ padding: '12px', marginBottom: '16px', backgroundColor: '#f0fdf4', borderLeft: '4px solid #16a34a', color: '#166534', fontSize: '0.85rem' }}>
            {successMsg}
          </div>
        )}

        {loginState === 'LOGIN' && (
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-main)' }}>Email đăng nhập</label>
              <input
                type="text" value={username} onChange={(e) => setUsername(e.target.value)} required
                style={{ padding: '10px 12px', border: '1.5px solid var(--border-color, #e2e8f0)', fontSize: '1rem', outline: 'none', borderRadius: '4px' }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-main)' }}>Mật khẩu</label>
              <input
                type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                style={{ padding: '10px 12px', border: '1.5px solid var(--border-color, #e2e8f0)', fontSize: '1rem', outline: 'none', borderRadius: '4px' }}
              />
            </div>

            <button
              type="submit" disabled={loading}
              style={{ marginTop: '8px', padding: '12px', backgroundColor: 'var(--primary-blue, #387ac3)', color: '#ffffff', fontWeight: 'bold', border: 'none', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1, borderRadius: '4px' }}
            >
              {loading ? 'Đang xử lý...' : 'Đăng nhập'}
            </button>
            
            <div style={{ display: 'flex', alignItems: 'center', margin: '12px 0' }}>
              <hr style={{ flex: 1, border: 'none', borderTop: '1px solid #e2e8f0' }} />
              <span style={{ margin: '0 10px', fontSize: '0.85rem', color: '#94a3b8' }}>HOẶC</span>
              <hr style={{ flex: 1, border: 'none', borderTop: '1px solid #e2e8f0' }} />
            </div>

            <button
              type="button"
              onClick={() => googleLogin()}
              disabled={loading}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', padding: '10px', backgroundColor: '#fff', color: '#334155', fontWeight: 'bold', border: '1px solid #cbd5e1', borderRadius: '4px', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1 }}
            >
              <img src="https://www.svgrepo.com/show/475656/google-color.svg" alt="Google" style={{ width: '20px' }} />
              Đăng nhập bằng Google
            </button>
          </form>
        )}

        {loginState === 'VERIFY' && (
          <form onSubmit={handleVerify} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-main)' }}>Mật khẩu mới</label>
              <input
                type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={6}
                style={{ padding: '10px 12px', border: '1.5px solid var(--border-color, #e2e8f0)', fontSize: '1rem', outline: 'none', borderRadius: '4px' }}
              />
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-main)' }}>Xác nhận mật khẩu mới</label>
              <input
                type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={6}
                style={{ padding: '10px 12px', border: '1.5px solid var(--border-color, #e2e8f0)', fontSize: '1rem', outline: 'none', borderRadius: '4px' }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-main)' }}>Mã OTP (gửi qua email)</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text" value={otpCode} onChange={(e) => setOtpCode(e.target.value)} required maxLength={6}
                  style={{ flex: 1, padding: '10px 12px', border: '1.5px solid var(--border-color, #e2e8f0)', fontSize: '1rem', outline: 'none', borderRadius: '4px', letterSpacing: '2px', textAlign: 'center' }}
                  placeholder="------"
                />
                <button
                  type="button" onClick={handleSendOtp} disabled={loading || countdown > 0}
                  style={{ padding: '0 16px', backgroundColor: '#e2e8f0', color: '#475569', fontWeight: 'bold', border: 'none', borderRadius: '4px', cursor: (loading || countdown > 0) ? 'not-allowed' : 'pointer' }}
                >
                  {countdown > 0 ? `Gửi lại (${countdown}s)` : 'Gửi mã'}
                </button>
              </div>
            </div>

            <button
              type="submit" disabled={loading}
              style={{ marginTop: '8px', padding: '12px', backgroundColor: '#10b981', color: '#ffffff', fontWeight: 'bold', border: 'none', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1, borderRadius: '4px' }}
            >
              {loading ? 'Đang xác thực...' : 'Xác thực & Đăng nhập'}
            </button>
            
            <button
              type="button" onClick={() => setLoginState('LOGIN')}
              style={{ padding: '8px', backgroundColor: 'transparent', color: '#64748b', border: 'none', cursor: 'pointer', fontSize: '0.85rem', textDecoration: 'underline' }}
            >
              Quay lại đăng nhập
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default function AdminLogin() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <AdminLoginForm />
    </GoogleOAuthProvider>
  );
}
