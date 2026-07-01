import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PROVIDERS_LIST = [
  { id: 'gemini', label: 'Google Gemini', needsEndpoint: false },
  { id: 'openai', label: 'OpenAI GPT', needsEndpoint: false },
  { id: 'groq', label: 'Groq Cloud', needsEndpoint: false },
  { id: 'vllm', label: 'vLLM Server', needsEndpoint: true },
];

export default function SlotsConfig() {
  const { showToast } = useOutletContext();
  
  const [selectedProviders, setSelectedProviders] = useState({ ocr: 'gemini', chat: 'gemini' });
  const [selectedModels, setSelectedModels] = useState({ ocr: '', chat: '' });
  const [modelsList, setModelsList] = useState({ ocr: [], chat: [] });
  const [modelsLoading, setModelsLoading] = useState({ ocr: false, chat: false });
  const [slotsLoading, setSlotsLoading] = useState(false);

  const loadSlots = async () => {
    try {
      const slotsRes = await fetch(`${API_BASE}/admin/slots`);
      if (slotsRes.ok) {
        const data = await slotsRes.json();
        const ocrSlot = data.find(s => s.slot === 'ocr');
        const chatSlot = data.find(s => s.slot === 'chat');

        if (ocrSlot) {
          setSelectedProviders(prev => ({ ...prev, ocr: ocrSlot.provider }));
          setSelectedModels(prev => ({ ...prev, ocr: ocrSlot.model_name }));
        }
        if (chatSlot) {
          setSelectedProviders(prev => ({ ...prev, chat: chatSlot.provider }));
          setSelectedModels(prev => ({ ...prev, chat: chatSlot.model_name }));
        }
      }
    } catch (err) {
      showToast('Lỗi tải cấu hình Slots từ Backend.', 'error');
    }
  };

  useEffect(() => {
    loadSlots();
  }, []);

  const handleLoadModelsForSlot = async (slotType, forceProvider = null) => {
    const provider = forceProvider || selectedProviders[slotType];
    setModelsLoading(prev => ({ ...prev, [slotType]: true }));
    try {
      const res = await fetch(`${API_BASE}/admin/models/${provider}`);
      if (res.ok) {
        const data = await res.json();
        if (data.models && data.models.length > 0) {
          setModelsList(prev => ({ ...prev, [slotType]: data.models }));
          showToast(`Đã lấy thành công ${data.models.length} models của ${provider.toUpperCase()}.`);
        } else {
          setModelsList(prev => ({ ...prev, [slotType]: [] }));
          showToast(`Kết nối tới ${provider.toUpperCase()} thành công (vui lòng nhập tên model thủ công).`, 'success');
        }
      } else {
        const errData = await res.json();
        showToast(errData.detail || `Kết nối tới ${provider} thất bại.`, 'error');
      }
    } catch (err) {
      showToast(`Không kết nối được tới provider API.`, 'error');
    } finally {
      setModelsLoading(prev => ({ ...prev, [slotType]: false }));
    }
  };

  useEffect(() => {
    if (modelsList.ocr.length === 0 && selectedProviders.ocr) handleLoadModelsForSlot('ocr');
    if (modelsList.chat.length === 0 && selectedProviders.chat) handleLoadModelsForSlot('chat');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSaveSlot = async (slotType) => {
    const provider = selectedProviders[slotType];
    const model = selectedModels[slotType].trim();

    if (!model) {
      showToast('Vui lòng chọn hoặc nhập tên model.', 'error');
      return;
    }

    setSlotsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/slots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slot: slotType,
          provider,
          model_name: model
        })
      });

      if (res.ok) {
        showToast(`Đã lưu phân công slot "${slotType.toUpperCase()}" thành công.`);
      } else {
        const data = await res.json();
        showToast(data.detail || 'Lỗi cập nhật slot configuration.', 'error');
      }
    } catch (err) {
      showToast('Lỗi kết nối lưu slot.', 'error');
    } finally {
      setSlotsLoading(false);
    }
  };

  return (
    <div className="admin-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
        <div>
          <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Phân công nhiệm vụ LLM</h3>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
            Phân phối model AI cụ thể cho 2 công đoạn: OCR trích xuất PDF và Chat suy luận RAG.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }} className="slot-grid-layout">
        {/* SLOT OCR */}
        <div style={{ padding: '24px', border: '1.5px solid var(--border-color)', backgroundColor: '#f8fafc' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--primary-blue)', letterSpacing: '0.5px', marginBottom: '4px' }}>SLOT 1</div>
          <h4 style={{ fontSize: '1.1rem', marginBottom: '12px' }}>📄 OCR (Đọc & trích xuất PDF)</h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>CHỌN PROVIDER</label>
              <select
                value={selectedProviders.ocr}
                onChange={e => {
                  const val = e.target.value;
                  setSelectedProviders(prev => ({ ...prev, ocr: val }));
                  handleLoadModelsForSlot('ocr', val);
                }}
                style={{
                  border: '1.5px solid var(--border-color)',
                  padding: '10px 14px',
                  backgroundColor: '#ffffff',
                  fontSize: '0.9rem',
                  width: '100%',
                  marginTop: '4px'
                }}
              >
                {PROVIDERS_LIST.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>

            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>MODEL NAME</label>
              {selectedProviders.ocr === 'vllm' ? (
                <input
                  type="text"
                  placeholder="Ví dụ: Qwen/Qwen2.5-32B-Instruct"
                  value={selectedModels.ocr}
                  onChange={e => setSelectedModels(prev => ({ ...prev, ocr: e.target.value }))}
                  style={{
                    border: '1.5px solid var(--border-color)',
                    padding: '10px 14px',
                    backgroundColor: '#ffffff',
                    fontSize: '0.9rem',
                    width: '100%',
                    marginTop: '4px'
                  }}
                />
              ) : (
                <>
                  <select
                    value={selectedModels.ocr}
                    onChange={e => setSelectedModels(prev => ({ ...prev, ocr: e.target.value }))}
                    disabled={modelsLoading.ocr}
                    style={{
                      border: '1.5px solid var(--border-color)',
                      padding: '10px 14px',
                      backgroundColor: '#ffffff',
                      fontSize: '0.9rem',
                      width: '100%',
                      marginTop: '4px'
                    }}
                  >
                    <option value="">-- Chọn Model --</option>
                    {modelsList.ocr.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                    {selectedModels.ocr && !modelsList.ocr.includes(selectedModels.ocr) && (
                      <option value={selectedModels.ocr}>{selectedModels.ocr} (đang sử dụng)</option>
                    )}
                  </select>
                  {modelsLoading.ocr && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--primary-blue)', marginTop: '4px' }}>Đang tải danh sách model...</div>
                  )}
                </>
              )}
            </div>

            <button
              onClick={() => handleSaveSlot('ocr')}
              disabled={slotsLoading}
              style={{
                backgroundColor: 'var(--primary-blue)',
                color: '#ffffff',
                padding: '12px 24px',
                fontWeight: 'bold',
                fontSize: '0.9rem',
                marginTop: '8px',
                border: 'none',
                cursor: slotsLoading ? 'not-allowed' : 'pointer'
              }}
            >
              LƯU CẤU HÌNH OCR
            </button>
          </div>
        </div>

        {/* SLOT CHAT */}
        <div style={{ padding: '24px', border: '1.5px solid var(--border-color)', backgroundColor: '#f8fafc' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--primary-blue)', letterSpacing: '0.5px', marginBottom: '4px' }}>SLOT 2</div>
          <h4 style={{ fontSize: '1.1rem', marginBottom: '12px' }}>💬 Chat (Suy luận RAG)</h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>CHỌN PROVIDER</label>
              <select
                value={selectedProviders.chat}
                onChange={e => {
                  const val = e.target.value;
                  setSelectedProviders(prev => ({ ...prev, chat: val }));
                  handleLoadModelsForSlot('chat', val);
                }}
                style={{
                  border: '1.5px solid var(--border-color)',
                  padding: '10px 14px',
                  backgroundColor: '#ffffff',
                  fontSize: '0.9rem',
                  width: '100%',
                  marginTop: '4px'
                }}
              >
                {PROVIDERS_LIST.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>

            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>MODEL NAME</label>
              {selectedProviders.chat === 'vllm' ? (
                <input
                  type="text"
                  placeholder="Ví dụ: Qwen/Qwen2.5-32B-Instruct"
                  value={selectedModels.chat}
                  onChange={e => setSelectedModels(prev => ({ ...prev, chat: e.target.value }))}
                  style={{
                    border: '1.5px solid var(--border-color)',
                    padding: '10px 14px',
                    backgroundColor: '#ffffff',
                    fontSize: '0.9rem',
                    width: '100%',
                    marginTop: '4px'
                  }}
                />
              ) : (
                <>
                  <select
                    value={selectedModels.chat}
                    onChange={e => setSelectedModels(prev => ({ ...prev, chat: e.target.value }))}
                    disabled={modelsLoading.chat}
                    style={{
                      border: '1.5px solid var(--border-color)',
                      padding: '10px 14px',
                      backgroundColor: '#ffffff',
                      fontSize: '0.9rem',
                      width: '100%',
                      marginTop: '4px'
                    }}
                  >
                    <option value="">-- Chọn Model --</option>
                    {modelsList.chat.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                    {selectedModels.chat && !modelsList.chat.includes(selectedModels.chat) && (
                      <option value={selectedModels.chat}>{selectedModels.chat} (đang sử dụng)</option>
                    )}
                  </select>
                  {modelsLoading.chat && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--primary-blue)', marginTop: '4px' }}>Đang tải danh sách model...</div>
                  )}
                </>
              )}
            </div>

            <button
              onClick={() => handleSaveSlot('chat')}
              disabled={slotsLoading}
              style={{
                backgroundColor: 'var(--primary-blue)',
                color: '#ffffff',
                padding: '12px 24px',
                fontWeight: 'bold',
                fontSize: '0.9rem',
                marginTop: '8px',
                border: 'none',
                cursor: slotsLoading ? 'not-allowed' : 'pointer'
              }}
            >
              LƯU CẤU HÌNH CHAT
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .slot-grid-layout { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
