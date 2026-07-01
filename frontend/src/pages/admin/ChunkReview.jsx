import React, { useState, useEffect } from 'react';
import { Card, Button, Typography, Space, Tag, message, Input, Checkbox, Spin, Row, Col } from 'antd';
import { SaveOutlined, DeleteOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import * as XLSX from 'xlsx';
import { DownloadOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
const { TextArea } = Input;

const ChunkReview = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    
    const [chunks, setChunks] = useState([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    
    const [selectedIds, setSelectedIds] = useState([]);
    const [selectAll, setSelectAll] = useState(false);

    const fetchChunks = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`http://localhost:8000/api/documents/${id}/chunks`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setChunks(data);
                setSelectedIds([]);
                setSelectAll(false);
            }
        } catch (error) {
            message.error('Lỗi khi tải dữ liệu chunk');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (id) {
            fetchChunks();
        }
    }, [id]);

    const handleContentChange = (chunkId, newContent) => {
        setChunks(prev => prev.map(c => c.id === chunkId ? { ...c, content: newContent } : c));
    };

    const handleSelect = (chunkId, checked) => {
        if (checked) {
            setSelectedIds(prev => [...prev, chunkId]);
        } else {
            setSelectedIds(prev => prev.filter(id => id !== chunkId));
            setSelectAll(false);
        }
    };

    const handleSelectAll = (e) => {
        const checked = e.target.checked;
        setSelectAll(checked);
        if (checked) {
            setSelectedIds(chunks.map(c => c.id));
        } else {
            setSelectedIds([]);
        }
    };

    const handleApprove = async () => {
        if (selectedIds.length === 0) {
            message.warning("Vui lòng chọn ít nhất 1 chunk để duyệt");
            return;
        }

        const payload = selectedIds.map(chunkId => {
            const chunk = chunks.find(c => c.id === chunkId);
            return {
                chunk_id: chunk.id,
                content: chunk.content
            };
        });

        setSaving(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`http://localhost:8000/api/documents/${id}/approve-chunks`, {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                message.success(`Đã xác nhận và lưu ${selectedIds.length} chunks lên Qdrant`);
                
                // Loại bỏ các chunk đã duyệt khỏi danh sách hiện tại
                const remaining = chunks.filter(c => !selectedIds.includes(c.id));
                setChunks(remaining);
                setSelectedIds([]);
                setSelectAll(false);

                // Nếu hết chunk, quay về trang danh sách
                if (remaining.length === 0) {
                    navigate('/admin/documents');
                }
            } else {
                message.error("Lỗi khi duyệt chunk");
            }
        } catch (error) {
            message.error("Lỗi kết nối");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (selectedIds.length === 0) {
            message.warning("Vui lòng chọn ít nhất 1 chunk để xóa");
            return;
        }

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`http://localhost:8000/api/documents/chunks/delete`, {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ chunk_ids: selectedIds })
            });

            if (res.ok) {
                message.success(`Đã xóa ${selectedIds.length} chunks`);
                const remaining = chunks.filter(c => !selectedIds.includes(c.id));
                setChunks(remaining);
                setSelectedIds([]);
                setSelectAll(false);
                
                if (remaining.length === 0) {
                    navigate('/admin/documents');
                }
            } else {
                message.error("Lỗi khi xóa chunk");
            }
        } catch (error) {
            message.error("Lỗi mạng");
        }
    };

    const handleExportExcel = () => {
        if (chunks.length === 0) {
            message.warning("Không có chunk nào để xuất");
            return;
        }

        const dataToExport = chunks.map((chunk, index) => ({
            "Số thứ tự": index + 1,
            "Chunk ID": chunk.id,
            "Năm": chunk.metadata_payload?.year || 'Tất cả',
            "Loại tài liệu": chunk.metadata_payload?.doc_type || 'N/A',
            "Nội dung": chunk.content
        }));

        const worksheet = XLSX.utils.json_to_sheet(dataToExport);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Chunks");
        XLSX.writeFile(workbook, `Chunks_Document_${id}.xlsx`);
    };

    return (
        <div style={{ padding: '24px' }}>
            <Button 
                icon={<ArrowLeftOutlined />} 
                onClick={() => navigate('/admin/documents')}
                style={{ marginBottom: '16px' }}
            >
                Quay lại Danh sách
            </Button>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
              <div>
                <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Duyệt nội dung tài liệu (Human-in-the-loop)</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
                  Admin kiểm tra, chỉnh sửa nội dung các chunk trước khi đưa vào RAG.
                </p>
              </div>
            </div>
            
            <Card style={{ marginTop: '16px', marginBottom: '24px' }}>
                <Row justify="space-between" align="middle">
                    <Col>
                        <Checkbox 
                            checked={selectAll} 
                            onChange={handleSelectAll}
                        >
                            Chọn tất cả ({selectedIds.length}/{chunks.length})
                        </Checkbox>
                    </Col>
                    <Col>
                        <Space>
                            <Button 
                                danger 
                                icon={<DeleteOutlined />} 
                                onClick={handleDelete}
                                disabled={selectedIds.length === 0}
                            >
                                Xóa đã chọn
                            </Button>
                            <Button 
                                icon={<DownloadOutlined />}
                                onClick={handleExportExcel}
                                disabled={chunks.length === 0}
                            >
                                Xuất Excel
                            </Button>
                            <Button 
                                type="primary" 
                                icon={<SaveOutlined />} 
                                loading={saving}
                                onClick={handleApprove}
                                disabled={selectedIds.length === 0}
                            >
                                Xác nhận & Lưu hệ thống
                            </Button>
                        </Space>
                    </Col>
                </Row>
            </Card>

            <Spin spinning={loading}>
                {chunks.map((chunk, index) => (
                    <Card 
                        key={chunk.id} 
                        style={{ marginBottom: '16px', borderColor: selectedIds.includes(chunk.id) ? '#1890ff' : '#f0f0f0' }}
                        headStyle={{ backgroundColor: '#fafafa' }}
                        title={
                            <Checkbox 
                                checked={selectedIds.includes(chunk.id)}
                                onChange={(e) => handleSelect(chunk.id, e.target.checked)}
                            >
                                <span style={{ fontWeight: 'bold' }}>Chunk #{index + 1}</span>
                            </Checkbox>
                        }
                        extra={
                            <Space>
                                {chunk.metadata_payload?.year && <Tag color="blue">Năm: {chunk.metadata_payload.year}</Tag>}
                                {chunk.metadata_payload?.doc_type && <Tag color="cyan">Loại: {chunk.metadata_payload.doc_type}</Tag>}
                                {Object.keys(chunk.metadata_payload || {}).map(key => {
                                    if (key.startsWith('Header')) {
                                        return <Tag color="purple" key={key}>{key}: {chunk.metadata_payload[key]}</Tag>
                                    }
                                    return null;
                                })}
                            </Space>
                        }
                    >
                        <TextArea 
                            rows={6}
                            value={chunk.content}
                            onChange={(e) => handleContentChange(chunk.id, e.target.value)}
                        />
                    </Card>
                ))}
                {chunks.length === 0 && !loading && (
                    <div style={{ textAlign: 'center', padding: '40px' }}>
                        <Text type="secondary">Không còn chunk nào chờ duyệt.</Text>
                    </div>
                )}
            </Spin>
        </div>
    );
};

export default ChunkReview;
