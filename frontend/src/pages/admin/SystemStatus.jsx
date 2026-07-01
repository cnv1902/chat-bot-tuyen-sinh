import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function SystemStatus() {
  const { showToast } = useOutletContext();
  const [slotsData, setSlotsData] = useState([]);

  const loadSlots = async () => {
    try {
      const slotsRes = await fetch(`${API_BASE}/admin/slots`);
      if (slotsRes.ok) {
        setSlotsData(await slotsRes.json());
      }
    } catch (err) {
      showToast('Lỗi tải cấu hình Slots từ Backend.', 'error');
    }
  };

  useEffect(() => {
    loadSlots();
  }, []);

  return (
    <div className="admin-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
        <div>
          <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Cấu hình đang chạy trong DB</h3>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
            Phản ánh trạng thái thiết lập model hiện tại. Đọc trực tiếp từ PostgreSQL Database.
          </p>
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--border-color)' }}>
              <th style={{ textAlign: 'left', padding: '12px', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>SLOT NHIỆM VỤ</th>
              <th style={{ textAlign: 'left', padding: '12px', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>LLM PROVIDER</th>
              <th style={{ textAlign: 'left', padding: '12px', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>MODEL ĐANG DÙNG</th>
              <th style={{ textAlign: 'left', padding: '12px', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>THỜI GIAN CẬP NHẬT</th>
            </tr>
          </thead>
          <tbody>
            {slotsData.length === 0 ? (
              <tr>
                <td colSpan="4" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Chưa có cấu hình slots nào được thiết lập.
                </td>
              </tr>
            ) : (
              slotsData.map((slot) => (
                <tr key={slot.slot} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '12px', fontWeight: 'bold', textTransform: 'uppercase' }}>{slot.slot}</td>
                  <td style={{ padding: '12px' }}>
                    <span style={{
                      backgroundColor: 'var(--bg-main)',
                      padding: '4px 8px',
                      fontWeight: '500',
                      fontSize: '0.85rem'
                    }}>
                      {slot.provider.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '12px', fontFamily: 'monospace', fontWeight: '600', color: 'var(--primary-blue)' }}>
                    {slot.model_name}
                  </td>
                  <td style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    {slot.updated_at ? new Date(slot.updated_at).toLocaleString('vi-VN') : '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
