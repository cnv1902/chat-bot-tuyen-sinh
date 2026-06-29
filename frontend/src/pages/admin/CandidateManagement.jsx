import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Users, Search, Download, Shield } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function CandidateManagement() {
  const { showToast } = useOutletContext();
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [searchInput, setSearchInput] = useState(''); // Used for debouncing or button click

  const fetchCandidates = async (search = '') => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const url = search ? `${API_BASE}/api/candidates/list?search=${encodeURIComponent(search)}` : `${API_BASE}/api/candidates/list`;
      
      const res = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!res.ok) throw new Error('Không thể lấy danh sách thí sinh');
      const data = await res.json();
      setCandidates(data);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCandidates(searchText);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText]);

  const handleSearch = (e) => {
    e.preventDefault();
    setSearchText(searchInput);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`${API_BASE}/api/candidates/export`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!res.ok) throw new Error('Lỗi khi xuất danh sách');
      
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Danh_Sach_Thi_Sinh.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast('Xuất Excel thành công', 'success');
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="admin-card" style={{ padding: '24px', backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              Quản lý Thí sinh
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
              Tra cứu và xuất danh sách dữ liệu thí sinh đăng ký tư vấn tuyển sinh.
            </p>
          </div>
          
          <div style={{ display: 'flex', gap: '12px' }}>
            <form onSubmit={handleSearch} style={{ display: 'flex', position: 'relative' }}>
              <input 
                type="text" 
                placeholder="Tìm email hoặc họ tên..." 
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                style={{ 
                  padding: '10px 14px 10px 36px', 
                  borderRadius: '6px 0 0 6px', 
                  border: '1px solid #cbd5e1', 
                  outline: 'none', 
                  width: '250px',
                  borderRight: 'none'
                }}
              />
              <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
              <button 
                type="submit"
                style={{
                  backgroundColor: 'var(--primary-blue)', color: 'white', border: 'none', borderRadius: '0 6px 6px 0', padding: '0 16px', cursor: 'pointer', fontWeight: 600
                }}
              >
                Tìm
              </button>
            </form>

            <button
              onClick={handleExport}
              disabled={exporting}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                backgroundColor: '#10b981', color: '#fff', padding: '10px 16px', borderRadius: '6px', fontWeight: 'bold', fontSize: '0.9rem', border: 'none', cursor: exporting ? 'not-allowed' : 'pointer'
              }}
            >
              <Download size={18} />
              {exporting ? 'Đang xuất...' : 'Xuất Excel'}
            </button>
          </div>
        </div>

        {/* Data Table */}
        <div style={{ overflowX: 'auto' }}>
          {loading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Đang tải danh sách thí sinh...</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.95rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Họ Tên</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Email</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Số điện thoại</th>
                  <th style={{ padding: '14px 16px', textAlign: 'left', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Ngành quan tâm</th>
                  <th style={{ padding: '14px 16px', textAlign: 'center', color: '#475569', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {candidates.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ padding: '30px', textAlign: 'center', color: '#64748b' }}>
                      Không tìm thấy dữ liệu thí sinh.
                    </td>
                  </tr>
                ) : (
                  candidates.map((candidate, index) => (
                    <tr key={candidate.account_id} style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.2s' }} onMouseOver={e => e.currentTarget.style.backgroundColor = '#f8fafc'} onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}>
                      <td style={{ padding: '14px 16px', fontWeight: 600, color: '#0f172a' }}>
                        {candidate.full_name || '-'}
                      </td>
                      <td style={{ padding: '14px 16px', color: '#475569' }}>
                        {candidate.email}
                      </td>
                      <td style={{ padding: '14px 16px', color: '#475569' }}>
                        {candidate.phone_number || '-'}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        {candidate.interested_majors ? (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                            {candidate.interested_majors.split(',').map((major, i) => (
                              <span key={i} style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', backgroundColor: '#e0e7ff', color: '#3730a3', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 600 }}>
                                {major.trim()}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>-</span>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: candidate.is_active ? '#dcfce7' : '#fee2e2', color: candidate.is_active ? '#166534' : '#991b1b', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 600 }}>
                          {candidate.is_active ? 'HOẠT ĐỘNG' : 'BỊ KHÓA'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
