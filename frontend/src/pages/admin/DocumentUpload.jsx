import React, { useState, useEffect } from 'react';
import { Card, Form, InputNumber, Select, Upload, Button, Typography, Alert, Table, Space, Tag, message } from 'antd';
import { InboxOutlined, FileTextOutlined, ArrowRightOutlined, DeleteOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;
const { Option } = Select;

const DocumentUpload = () => {
    const [form] = Form.useForm();
    const navigate = useNavigate();
    const [uploading, setUploading] = useState(false);
    const [documents, setDocuments] = useState([]);
    const [polling, setPolling] = useState(false);

    const fetchDocuments = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch('http://localhost:8000/api/documents', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setDocuments(data);
                
                // Kiểm tra xem có file nào đang processing không
                const hasProcessing = data.some(doc => doc.status === 'processing');
                if (hasProcessing && !polling) {
                    setPolling(true);
                } else if (!hasProcessing && polling) {
                    setPolling(false);
                }
            }
        } catch (error) {
            console.error('Failed to fetch documents:', error);
        }
    };

    useEffect(() => {
        fetchDocuments();
    }, []);

    useEffect(() => {
        let interval;
        if (polling) {
            interval = setInterval(() => {
                fetchDocuments();
            }, 3000);
        }
        return () => {
            if (interval) clearInterval(interval);
        };
    }, [polling]);

    const onFinish = async (values) => {
        if (!values.file || values.file.length === 0) {
            message.error("Vui lòng chọn file");
            return;
        }

        const formData = new FormData();
        formData.append("file", values.file[0].originFileObj);
        if (values.year) {
            formData.append("year", values.year);
        }
        formData.append("doc_type", values.doc_type);

        setUploading(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch('http://localhost:8000/api/documents/upload', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });

            if (res.ok) {
                message.success("Upload thành công, hệ thống đang xử lý!");
                form.resetFields();
                fetchDocuments(); // Sẽ trigger polling
            } else {
                message.error("Upload thất bại");
            }
        } catch (error) {
            message.error("Lỗi kết nối tới server");
        } finally {
            setUploading(false);
        }
    };

    const handleDelete = async (id) => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`http://localhost:8000/api/documents/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                message.success("Đã xóa tài liệu");
                fetchDocuments();
            } else {
                message.error("Lỗi khi xóa tài liệu");
            }
        } catch (error) {
            message.error("Lỗi mạng");
        }
    };

    const columns = [
        { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
        { title: 'Tên file', dataIndex: 'filename', key: 'filename' },
        { title: 'Năm', dataIndex: 'year', key: 'year', width: 100, render: (year) => year || 'Tất cả' },
        { title: 'Loại', dataIndex: 'doc_type', key: 'doc_type', width: 120 },
        { 
            title: 'Trạng thái', 
            dataIndex: 'status', 
            key: 'status',
            render: (status, record) => {
                if (status === 'processing') return <Tag color="processing">Đang xử lý</Tag>;
                if (status === 'pending_review') return <Tag color="warning">Chờ duyệt chunks</Tag>;
                if (status === 'success') return <Tag color="success">Hoàn thành</Tag>;
                if (status === 'failed') return <Tag color="error">Lỗi xử lý</Tag>;
                return <Tag>{status}</Tag>;
            }
        },
        {
            title: 'Thao tác',
            key: 'action',
            render: (_, record) => (
                <Space size="middle">
                    {record.status === 'pending_review' && (
                        <Button 
                            type="primary" 
                            size="small" 
                            icon={<ArrowRightOutlined />}
                            onClick={() => navigate(`/admin/documents/${record.id}/review`)}
                        >
                            Duyệt Chunks
                        </Button>
                    )}
                    <Button 
                        danger 
                        size="small" 
                        icon={<DeleteOutlined />}
                        onClick={() => handleDelete(record.id)}
                    >
                        Xóa
                    </Button>
                </Space>
            )
        }
    ];

    return (
        <div className="admin-card" style={{ padding: '0', backgroundColor: 'transparent', boxShadow: 'none' }}>
            <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
                    <div>
                        <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>Quản lý & Upload Tài Liệu RAG</h3>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
                            Upload file văn bản để AI học và trả lời câu hỏi của thí sinh.
                        </p>
                    </div>
                </div>
            
                <div style={{ marginBottom: '32px' }}>
                    <Form
                        form={form}
                        layout="vertical"
                        onFinish={onFinish}
                        initialValues={{ doc_type: 'khac' }}
                    >
                        <Form.Item
                            name="file"
                            valuePropName="fileList"
                            getValueFromEvent={e => Array.isArray(e) ? e : e?.fileList}
                            rules={[{ required: true, message: 'Vui lòng chọn hoặc kéo thả file' }]}
                        >
                            <Upload.Dragger name="file" beforeUpload={() => false} maxCount={1} style={{ padding: '20px 0' }}>
                                <p className="ant-upload-drag-icon">
                                    <InboxOutlined style={{ color: '#1890ff', fontSize: '48px' }} />
                                </p>
                                <p className="ant-upload-text" style={{ fontSize: '1.1rem', fontWeight: 500 }}>
                                    Kéo thả file tài liệu vào đây hoặc click để duyệt
                                </p>
                                <p className="ant-upload-hint" style={{ color: 'var(--text-muted)' }}>
                                    Hỗ trợ file định dạng DOCX, PDF chứa văn bản, TXT.
                                </p>
                            </Upload.Dragger>
                        </Form.Item>

                        <Space size="large" style={{ marginTop: '8px' }}>
                            <Form.Item name="year" label="Năm áp dụng (Trống = Tất cả)">
                                <InputNumber min={2020} max={2030} style={{ width: 180 }} placeholder="Tất cả các năm" />
                            </Form.Item>

                            <Form.Item name="doc_type" label="Loại tài liệu">
                                <Select style={{ width: 250 }}>
                                    <Select.OptGroup label="📚 NGHIỆP VỤ TUYỂN SINH">
                                        <Option value="de_an">Đề án tuyển sinh</Option>
                                        <Option value="quy_che">Quy chế tuyển sinh</Option>
                                        <Option value="diem_chuan">Điểm chuẩn</Option>
                                        <Option value="huong_dan">Hướng dẫn</Option>
                                        <Option value="hoc_phi">Học phí</Option>
                                    </Select.OptGroup>
                                    <Select.OptGroup label="🌟 TRUYỀN THÔNG & TIẾP THỊ">
                                        <Option value="lich_su">Lịch sử truyền thống</Option>
                                        <Option value="gioi_thieu">Giới thiệu chung</Option>
                                        <Option value="co_so_vat_chat">Cơ sở vật chất & KTX</Option>
                                        <Option value="thanh_tich">Thành tích & Việc làm</Option>
                                        <Option value="doi_song">Đời sống sinh viên</Option>
                                    </Select.OptGroup>
                                    <Select.OptGroup label="KHÁC">
                                        <Option value="khac">Khác</Option>
                                    </Select.OptGroup>
                                </Select>
                            </Form.Item>

                            <Form.Item label=" ">
                                <Button type="primary" htmlType="submit" loading={uploading} icon={<FileTextOutlined />}>
                                    Upload và Xử lý
                                </Button>
                            </Form.Item>
                        </Space>
                    </Form>
                </div>

                {documents.some(d => d.status === 'failed') && (
                    <Alert 
                        message="Cảnh báo: Có tài liệu bị lỗi" 
                        description={documents.find(d => d.status === 'failed')?.error_message || "Đã xảy ra lỗi khi xử lý."} 
                        type="error" 
                        showIcon 
                        style={{ marginBottom: '24px' }}
                    />
                )}

                <Table 
                    columns={columns} 
                    dataSource={documents} 
                    rowKey="id" 
                    pagination={{ pageSize: 10 }}
                    bordered
                    size="middle"
                />
            </div>
        </div>
    );
};

export default DocumentUpload;
