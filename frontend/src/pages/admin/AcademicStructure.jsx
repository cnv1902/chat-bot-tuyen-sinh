import React, { useState, useEffect } from 'react';
import { Upload, ChevronDown, ChevronRight, School, BookOpen } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';

export default function AcademicStructure() {
  const { showToast } = useOutletContext();
  const [treeData, setTreeData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadingInstitute, setUploadingInstitute] = useState(false);
  const [uploadingMajor, setUploadingMajor] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState(new Set());

  const fetchTree = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/academic/tree', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      if (!res.ok) throw new Error('Không thể tải dữ liệu');
      const data = await res.json();
      setTreeData(data);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTree();
  }, []);

  const handleFileUpload = async (event, endpoint, setUploadingState) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploadingState(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`http://localhost:8000/api/academic/${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: formData
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Có lỗi xảy ra khi tải file');

      showToast(data.message, 'success');
      fetchTree(); // Reload the tree data
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setUploadingState(false);
      event.target.value = ''; // Reset input
    }
  };

  const toggleNode = (code) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(code)) {
      newExpanded.delete(code);
    } else {
      newExpanded.add(code);
    }
    setExpandedNodes(newExpanded);
  };

  return (
    <div className="admin-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
        <div>
          <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Cơ cấu Đào tạo</h3>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
            Quản lý danh sách Trường/Viện và các Ngành đào tạo.
          </p>
        </div>
        
        <div style={{ display: 'flex', gap: '12px' }}>
          {/* Upload Institute Button */}
          <div style={{ position: 'relative' }}>
            <input
              type="file"
              accept=".xlsx"
              id="upload-institute"
              style={{ display: 'none' }}
              onChange={(e) => handleFileUpload(e, 'import-institutes', setUploadingInstitute)}
              disabled={uploadingInstitute}
            />
            <label
              htmlFor="upload-institute"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                backgroundColor: '#3b82f6',
                color: 'white',
                borderRadius: '6px',
                cursor: uploadingInstitute ? 'not-allowed' : 'pointer',
                fontWeight: '500',
                transition: 'background-color 0.2s',
                opacity: uploadingInstitute ? 0.7 : 1
              }}
            >
              <Upload size={18} />
              {uploadingInstitute ? 'Đang xử lý...' : 'Nhập Trường/Viện'}
            </label>
          </div>

          {/* Upload Major Button */}
          <div style={{ position: 'relative' }}>
            <input
              type="file"
              accept=".xlsx"
              id="upload-major"
              style={{ display: 'none' }}
              onChange={(e) => handleFileUpload(e, 'import-majors', setUploadingMajor)}
              disabled={uploadingMajor}
            />
            <label
              htmlFor="upload-major"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                backgroundColor: '#10b981',
                color: 'white',
                borderRadius: '6px',
                cursor: uploadingMajor ? 'not-allowed' : 'pointer',
                fontWeight: '500',
                transition: 'background-color 0.2s',
                opacity: uploadingMajor ? 0.7 : 1
              }}
            >
              <Upload size={18} />
              {uploadingMajor ? 'Đang xử lý...' : 'Nhập Ngành đào tạo'}
            </label>
          </div>
        </div>
      </div>

      {/* Tree View */}
      <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '20px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>Đang tải dữ liệu...</div>
        ) : treeData.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>
            Chưa có dữ liệu. Vui lòng tải file Excel lên.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {treeData.map((institute) => (
              <div key={institute.institute_code} style={{ border: '1px solid #e5e7eb', borderRadius: '6px', overflow: 'hidden' }}>
                {/* Institute Row */}
                <div 
                  onClick={() => toggleNode(institute.institute_code)}
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    padding: '12px 16px', 
                    backgroundColor: '#f9fafb', 
                    cursor: 'pointer',
                    userSelect: 'none'
                  }}
                >
                  <div style={{ marginRight: '12px', color: '#6b7280' }}>
                    {expandedNodes.has(institute.institute_code) ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                  </div>
                  <School size={20} style={{ marginRight: '12px', color: '#3b82f6' }} />
                  <div style={{ flex: 1 }}>
                    <span style={{ fontWeight: '600', color: '#1f2937' }}>{institute.institute_name}</span>
                    <span style={{ marginLeft: '8px', fontSize: '12px', color: '#6b7280', backgroundColor: '#e5e7eb', padding: '2px 6px', borderRadius: '4px' }}>
                      {institute.institute_code}
                    </span>
                  </div>
                  <div style={{ fontSize: '13px', color: '#6b7280', fontWeight: '500' }}>
                    {institute.majors?.length || 0} ngành
                  </div>
                </div>

                {/* Majors List */}
                {expandedNodes.has(institute.institute_code) && institute.majors && institute.majors.length > 0 && (
                  <div style={{ borderTop: '1px solid #e5e7eb' }}>
                    {institute.majors.map((major, index) => (
                      <div 
                        key={major.major_code} 
                        style={{ 
                          display: 'flex', 
                          padding: '12px 16px 12px 48px',
                          borderBottom: index < institute.majors.length - 1 ? '1px solid #f3f4f6' : 'none',
                          backgroundColor: 'white'
                        }}
                      >
                        <BookOpen size={18} style={{ marginRight: '12px', color: '#10b981', marginTop: '2px' }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                            <span style={{ fontWeight: '500', color: '#374151' }}>{major.major_name}</span>
                            <span style={{ marginLeft: '8px', fontSize: '12px', color: '#6b7280', backgroundColor: '#f3f4f6', padding: '2px 6px', borderRadius: '4px' }}>
                              {major.major_code}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
