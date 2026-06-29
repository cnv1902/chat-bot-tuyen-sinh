import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PROVIDERS_LIST = [
  { id: 'gemini', label: 'Google Gemini', color: '#4285f4', needsEndpoint: false },
  { id: 'openai', label: 'OpenAI GPT', color: '#10a37f', needsEndpoint: false },
  { id: 'groq', label: 'Groq Cloud', color: '#f97316', needsEndpoint: false },
  { id: 'vllm', label: 'vLLM Server', color: '#8b5cf6', needsEndpoint: true },
];

export default function ProvidersConfig() {
  const { showToast } = useOutletContext();
  const [providersData, setProvidersData] = useState([]);
  const [providerKeys, setProviderKeys] = useState({
    gemini: '', openai: '', groq: '', vllm: ''
  });
  const [providerEndpoints, setProviderEndpoints] = useState({
    vllm: ''
  });
  const [provLoading, setProvLoading] = useState(false);

  const loadProviders = async () => {
    try {
      const provRes = await fetch(`${API_BASE}/admin/providers`);
      if (provRes.ok) {
        const data = await provRes.json();
        setProvidersData(data);
        const vllmProv = data.find(p => p.provider === 'vllm');
        if (vllmProv && vllmProv.endpoint) {
          setProviderEndpoints(prev => ({ ...prev, vllm: vllmProv.endpoint }));
        }
      }
    } catch (err) {
      showToast('Lỗi tải cấu hình API keys từ Backend.', 'error');
    }
  };

  useEffect(() => {
    loadProviders();
  }, []);

  const handleSaveProvider = async (providerId) => {
    const key = providerKeys[providerId].trim();
    const endpoint = PROVIDERS_LIST.find(p => p.id === providerId).needsEndpoint
      ? providerEndpoints[providerId].trim()
      : null;

    setProvLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/providers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: providerId,
          api_key: key || null,
          endpoint: endpoint || null,
          is_active: true
        })
      });

      if (res.ok) {
        showToast(`Đã cập nhật cấu hình cho ${providerId.toUpperCase()}.`);
        setProviderKeys(prev => ({ ...prev, [providerId]: '' }));
        await loadProviders();
      } else {
        const data = await res.json();
        showToast(data.detail || 'Lỗi cập nhật credentials.', 'error');
      }
    } catch (err) {
      showToast('Lỗi mạng, không lưu được credentials.', 'error');
    } finally {
      setProvLoading(false);
    }
  };

  return (
    <div className="admin-card">
      <div style={{ borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase' }}>Cấu hình API Keys</h3>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px' }}>
          Cung cấp API keys để kích hoạt các model AI. Khóa bảo mật được mã hóa lưu trữ.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
        {PROVIDERS_LIST.map((provider) => {
          const dbInfo = providersData.find(p => p.provider === provider.id) || {};
          return (
            <div
              key={provider.id}
              style={{
                padding: '24px',
                border: '1.5px solid var(--border-color)',
                backgroundColor: '#f8fafc',
                position: 'relative'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span style={{ fontWeight: 'bold', fontSize: '1.1rem', color: provider.color }}>
                  {provider.label}
                </span>
                <span style={{
                  fontSize: '0.75rem',
                  padding: '4px 10px',
                  fontWeight: 'bold',
                  backgroundColor: dbInfo.has_key ? '#dcfce7' : '#f1f5f9',
                  color: dbInfo.has_key ? '#166534' : 'var(--text-muted)',
                  border: `1px solid ${dbInfo.has_key ? '#22c55e' : 'var(--border-color)'}`
                }}>
                  {dbInfo.has_key ? 'ĐÃ ĐƯỢC THIẾT LẬP KEY' : 'CHƯA CÓ KEY'}
                </span>
              </div>

              {provider.needsEndpoint && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>VLLM SERVER URL ENDPOINT</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: http://10.0.0.5:8080"
                    value={providerEndpoints[provider.id] || ''}
                    onChange={e => setProviderEndpoints(prev => ({ ...prev, [provider.id]: e.target.value }))}
                    style={{
                      border: '1.5px solid var(--border-color)',
                      padding: '10px 14px',
                      backgroundColor: '#ffffff',
                      fontSize: '0.9rem',
                      width: '100%'
                    }}
                  />
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>
                  API KEY {dbInfo.has_key && '(Nhập mới nếu muốn thay đổi khóa cũ)'}
                </label>
                <input
                  type="password"
                  placeholder="••••••••••••••••"
                  value={providerKeys[provider.id]}
                  onChange={e => setProviderKeys(prev => ({ ...prev, [provider.id]: e.target.value }))}
                  style={{
                    border: '1.5px solid var(--border-color)',
                    padding: '10px 14px',
                    backgroundColor: '#ffffff',
                    fontSize: '0.9rem',
                    width: '100%'
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => handleSaveProvider(provider.id)}
                  disabled={provLoading}
                  style={{
                    backgroundColor: 'var(--primary-blue)',
                    color: '#ffffff',
                    padding: '10px 20px',
                    fontWeight: 'bold',
                    fontSize: '0.85rem',
                    cursor: provLoading ? 'not-allowed' : 'pointer',
                    border: 'none',
                    borderRadius: '4px'
                  }}
                >
                  LƯU CREDENTIALS
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
