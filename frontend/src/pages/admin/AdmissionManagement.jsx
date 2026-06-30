import React, { useState, useEffect } from 'react';
import { Table, Button, Typography, message, Tabs, Modal, Form, Input, Space, Popconfirm, Select } from 'antd';
import { Upload, RefreshCw, FileText, Layers, List, Plus, Edit, Trash2 } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';

const { Title, Text } = Typography;

export default function AdmissionManagement() {
  const { showToast } = useOutletContext();
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  const [activeTab, setActiveTab] = useState('plans');
  const [data, setData] = useState({ plans: [], quotas: [], methods: [], combinations: [] });
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState({ plans: false, quotas: false, methods: false, combinations: false });
  const [filterYear, setFilterYear] = useState('2026');

  // Modals for Methods and Combinations
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalType, setModalType] = useState('add');
  const [editingRecord, setEditingRecord] = useState(null);
  const [form] = Form.useForm();
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const resPlans = await fetch(`${API_URL}/api/admission/plans?year=${filterYear}`);
      const plansResponse = resPlans.ok ? await resPlans.json() : [];
      const plans = Array.isArray(plansResponse) ? plansResponse : (plansResponse.data || []);

      const resMethods = await fetch(`${API_URL}/api/admission/methods?year=${filterYear}`);
      const methods = resMethods.ok ? await resMethods.json() : [];

      const resCombos = await fetch(`${API_URL}/api/admission/combinations`);
      const combinations = resCombos.ok ? await resCombos.json() : [];

      const resQuotas = await fetch(`${API_URL}/api/admission/quotas`);
      const quotas = resQuotas.ok ? await resQuotas.json() : [];

      // Transform backend camelCase/snake_case to our standard for Antd
      // Assuming plans returns exactly what we need, or we map it:
      const mappedPlans = plans.map(p => ({
        id: p.id,
        programName: p.programName || p.program_name || '',
        majorName: p.majorName || p.major_name || '',
        maXetTuyen: p.maXetTuyen || p.ma_xet_tuyen,
        maNganh: p.maNganh || p.ma_nganh,
        nam: p.nam || p.year,
        maPhuongThuc: p.maPhuongThuc || p.ma_phuong_thuc,
        khoi: p.khoi,
        diemChuan: p.diemChuan || p.diem_chuan,
        hocBaTrungBinhChung3Nam: p.hocBaTrungBinhChung3Nam || p.hoc_ba_tbc_3_nam,
        diemTotNghiep: p.diemTotNghiep || p.diem_tot_nghiep,
        trungBinhChung3NamNgoaiNgu: p.trungBinhChung3NamNgoaiNgu || p.tbc_3_nam_ngoai_ngu,
        hocLuc12: p.hocLuc12 || p.hoc_luc_12,
        nangKhieu: p.nangKhieu || p.nang_khieu,
        monNhanHeSo: p.monNhanHeSo || p.mon_nhan_he_so,
        tiengAnh: p.tiengAnh || p.tieng_anh,
        ngoaiNgu: p.ngoaiNgu || p.ngoai_ngu,
        heSo: p.heSo || p.he_so,
        chiTieu: p.chiTieu || p.chi_tieu
      }));

      setData({ plans: mappedPlans, quotas, methods, combinations });
    } catch (error) {
      message.error('Lỗi khi tải dữ liệu');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [filterYear]);

  const handleFileUpload = async (event, type) => {
    const file = event.target.files[0];
    if (!file) return;

    const endpoints = {
      combinations: `${API_URL}/api/admission/import-combinations`,
      methods: `${API_URL}/api/admission/import-methods`,
      plans: `${API_URL}/api/admission/import-plans`,
      quotas: `${API_URL}/api/admission/import-quotas`
    };

    setUploading(prev => ({ ...prev, [type]: true }));
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(endpoints[type], {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
        body: formData,
      });

      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Có lỗi xảy ra khi import');

      message.success(result.message || 'Import thành công');
      fetchData(); 
    } catch (error) {
      message.error(error.message);
    } finally {
      setUploading(prev => ({ ...prev, [type]: false }));
      event.target.value = null;
    }
  };

  const handleDelete = async (record, tab) => {
    let url = '';
    if (tab === 'methods') url = `${API_URL}/api/admission_crud/methods/${record.id}`;
    if (tab === 'combinations') url = `${API_URL}/api/admission_crud/combinations/${record.combo_code}`;
    if (tab === 'plans') url = `${API_URL}/api/admission_crud/plans/${record.id}`;
    if (tab === 'quotas') url = `${API_URL}/api/admission_crud/quotas/${record.id}`;
    
    try {
      const res = await fetch(url, { method: 'DELETE' });
      if (!res.ok) throw new Error('Lỗi khi xóa');
      message.success('Xóa thành công');
      fetchData();
    } catch (err) {
      message.error(err.message);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedRowKeys.length === 0) return;
    
    let url = '';
    if (activeTab === 'methods') url = `${API_URL}/api/admission_crud/methods/bulk-delete`;
    if (activeTab === 'combinations') url = `${API_URL}/api/admission_crud/combinations/bulk-delete`;
    if (activeTab === 'plans') url = `${API_URL}/api/admission_crud/plans/bulk-delete`;
    if (activeTab === 'quotas') url = `${API_URL}/api/admission_crud/quotas/bulk-delete`;
    
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedRowKeys })
      });
      if (!res.ok) throw new Error('Lỗi khi xóa hàng loạt');
      message.success(`Đã xóa ${selectedRowKeys.length} mục`);
      setSelectedRowKeys([]);
      fetchData();
    } catch (err) {
      message.error(err.message);
    }
  };

  const openModal = (type, tab, record = null) => {
    setModalType(type);
    setEditingRecord(record);
    setIsModalOpen(true);
    if (record) {
      form.setFieldsValue(record);
    } else {
      form.resetFields();
      if (tab === 'methods') form.setFieldsValue({ year: filterYear });
    }
  };

  const handleModalSubmit = async (values) => {
    let url = '';
    let method = modalType === 'add' ? 'POST' : 'PUT';
    
    if (activeTab === 'methods') {
      url = modalType === 'add' ? `${API_URL}/api/admission_crud/methods` : `${API_URL}/api/admission_crud/methods/${editingRecord.id}`;
      values.year = parseInt(values.year);
    } else if (activeTab === 'combinations') {
      url = modalType === 'add' ? `${API_URL}/api/admission_crud/combinations` : `${API_URL}/api/admission_crud/combinations/${editingRecord.combo_code}`;
    } else if (activeTab === 'quotas') {
      url = modalType === 'add' ? `${API_URL}/api/admission_crud/quotas` : `${API_URL}/api/admission_crud/quotas/${editingRecord.id}`;
      values.nam = parseInt(values.nam);
      values.chi_tieu = parseInt(values.chi_tieu);
    } else if (activeTab === 'plans') {
      url = modalType === 'add' ? `${API_URL}/api/admission_crud/plans` : `${API_URL}/api/admission_crud/plans/${editingRecord.id}`;
      // convert keys from camelCase to snake_case for backend PlanCreate model
      const planPayload = {
        ma_xet_tuyen: values.maXetTuyen,
        ma_nganh: values.maNganh,
        nam: values.nam ? parseInt(values.nam) : null,
        ma_phuong_thuc: values.maPhuongThuc,
        khoi: values.khoi,
        diem_chuan: values.diemChuan,
        hoc_ba_tbc_3_nam: values.hocBaTrungBinhChung3Nam,
        diem_tot_nghiep: values.diemTotNghiep,
        tbc_3_nam_ngoai_ngu: values.trungBinhChung3NamNgoaiNgu,
        hoc_luc_12: values.hocLuc12,
        nang_khieu: values.nangKhieu,
        mon_nhan_he_so: values.monNhanHeSo,
        tieng_anh: values.tiengAnh,
        ngoai_ngu: values.ngoaiNgu,
        he_so: values.heSo
      };
      values = planPayload;
    }

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values)
      });
      if (!res.ok) throw new Error('Lỗi thao tác');
      message.success('Thành công');
      setIsModalOpen(false);
      fetchData();
    } catch (err) {
      message.error(err.message);
    }
  };

  const generateFilters = (dataIndex, tabData) => {
    const uniqueValues = new Set();
    tabData.forEach(item => {
      const val = item[dataIndex];
      if (val !== null && val !== undefined && val !== '') uniqueValues.add(val);
    });
    return Array.from(uniqueValues).sort().map(val => ({ text: String(val), value: val }));
  };
  const handleFilter = (value, record, dataIndex) => record[dataIndex] === value;

  // --- COLUMNS ---
  const planColumns = [
    { title: 'Tên Chương Trình', dataIndex: 'programName', key: 'programName', width: 200, fixed: 'left', filters: generateFilters('programName', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'programName') },
    { title: 'Tên Ngành', dataIndex: 'majorName', key: 'majorName', width: 200, filters: generateFilters('majorName', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'majorName') },
    { title: 'Mã xét tuyển', dataIndex: 'maXetTuyen', key: 'maXetTuyen', width: 130, filters: generateFilters('maXetTuyen', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'maXetTuyen') },
    { title: 'Mã ngành', dataIndex: 'maNganh', key: 'maNganh', width: 120, filters: generateFilters('maNganh', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'maNganh') },
    { title: 'Năm', dataIndex: 'nam', key: 'nam', width: 100, filters: generateFilters('nam', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'nam') },
    { title: 'Mã phương thức', dataIndex: 'maPhuongThuc', key: 'maPhuongThuc', width: 150, filters: generateFilters('maPhuongThuc', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'maPhuongThuc') },
    { title: 'Khối', dataIndex: 'khoi', key: 'khoi', width: 100, filters: generateFilters('khoi', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'khoi') },
    { title: 'Chỉ tiêu', dataIndex: 'chiTieu', key: 'chiTieu', width: 100, align: 'right', filters: generateFilters('chiTieu', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'chiTieu') },
    { title: 'Điểm chuẩn', dataIndex: 'diemChuan', key: 'diemChuan', width: 130, align: 'right', filters: generateFilters('diemChuan', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'diemChuan') },
    { title: 'Học bạ TBC 3 năm', dataIndex: 'hocBaTrungBinhChung3Nam', key: 'hocBaTrungBinhChung3Nam', width: 160, align: 'right', filters: generateFilters('hocBaTrungBinhChung3Nam', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'hocBaTrungBinhChung3Nam') },
    { title: 'Điểm tốt nghiệp', dataIndex: 'diemTotNghiep', key: 'diemTotNghiep', width: 150, align: 'right', filters: generateFilters('diemTotNghiep', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'diemTotNghiep') },
    { title: 'TBC 3 năm NN', dataIndex: 'trungBinhChung3NamNgoaiNgu', key: 'trungBinhChung3NamNgoaiNgu', width: 150, align: 'right', filters: generateFilters('trungBinhChung3NamNgoaiNgu', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'trungBinhChung3NamNgoaiNgu') },
    { title: 'Học lực 12', dataIndex: 'hocLuc12', key: 'hocLuc12', width: 120, filters: generateFilters('hocLuc12', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'hocLuc12') },
    { title: 'Năng khiếu', dataIndex: 'nangKhieu', key: 'nangKhieu', width: 120, filters: generateFilters('nangKhieu', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'nangKhieu') },
    { title: 'Môn nhân hệ số', dataIndex: 'monNhanHeSo', key: 'monNhanHeSo', width: 150, filters: generateFilters('monNhanHeSo', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'monNhanHeSo') },
    { title: 'Tiếng Anh', dataIndex: 'tiengAnh', key: 'tiengAnh', width: 120, align: 'right', filters: generateFilters('tiengAnh', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'tiengAnh') },
    { title: 'Ngoại ngữ', dataIndex: 'ngoaiNgu', key: 'ngoaiNgu', width: 120, align: 'right', filters: generateFilters('ngoaiNgu', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'ngoaiNgu') },
    { title: 'Hệ số', dataIndex: 'heSo', key: 'heSo', width: 100, align: 'right', filters: generateFilters('heSo', data.plans), filterSearch: true, onFilter: (value, record) => handleFilter(value, record, 'heSo') },
    { 
      title: 'Hành động', width: 100, fixed: 'right', align: 'center',
      render: (_, record) => (
        <Space>
          <Button icon={<Edit size={16} />} type="text" onClick={() => openModal('edit', 'plans', record)} />
          <Popconfirm title="Xóa đề án này?" onConfirm={() => handleDelete(record, 'plans')}>
            <Button icon={<Trash2 size={16} />} type="text" danger />
          </Popconfirm>
        </Space>
      )
    }
  ];

  const methodColumns = [
    { title: 'Năm', dataIndex: 'year', width: 100 },
    { title: 'Mã Phương thức', dataIndex: 'method_code', width: 150 },
    { title: 'Tên Phương thức', dataIndex: 'method_name' },
    { 
      title: 'Hành động', width: 150, align: 'right',
      render: (_, record) => (
        <Space>
          <Button icon={<Edit size={16} />} type="text" onClick={() => openModal('edit', 'methods', record)} />
          <Popconfirm title="Xóa phương thức này?" onConfirm={() => handleDelete(record, 'methods')}>
            <Button icon={<Trash2 size={16} />} type="text" danger />
          </Popconfirm>
        </Space>
      )
    }
  ];

  const quotaColumns = [
    { title: 'Năm', dataIndex: 'nam', width: 100, filters: generateFilters('nam', data.quotas), onFilter: (value, record) => handleFilter(value, record, 'nam') },
    { title: 'Mã xét tuyển', dataIndex: 'ma_xet_tuyen', width: 150, filters: generateFilters('ma_xet_tuyen', data.quotas), onFilter: (value, record) => handleFilter(value, record, 'ma_xet_tuyen') },
    { title: 'Chỉ tiêu', dataIndex: 'chi_tieu', width: 120, align: 'right' },
    { 
      title: 'Hành động', width: 150, align: 'right',
      render: (_, record) => (
        <Space>
          <Button icon={<Edit size={16} />} type="text" onClick={() => openModal('edit', 'quotas', record)} />
          <Popconfirm title="Xóa chỉ tiêu này?" onConfirm={() => handleDelete(record, 'quotas')}>
            <Button icon={<Trash2 size={16} />} type="text" danger />
          </Popconfirm>
        </Space>
      )
    }
  ];

  const comboColumns = [
    { title: 'Mã Tổ hợp', dataIndex: 'combo_code', width: 150 },
    { title: 'Môn học', dataIndex: 'subjects' },
    { 
      title: 'Hành động', width: 150, align: 'right',
      render: (_, record) => (
        <Space>
          <Button icon={<Edit size={16} />} type="text" onClick={() => openModal('edit', 'combinations', record)} />
          <Popconfirm title="Xóa tổ hợp này?" onConfirm={() => handleDelete(record, 'combinations')}>
            <Button icon={<Trash2 size={16} />} type="text" danger />
          </Popconfirm>
        </Space>
      )
    }
  ];

  const getModalTitle = () => {
    const action = modalType === 'add' ? 'Thêm mới' : 'Cập nhật';
    if (activeTab === 'methods') return `${action} Phương thức`;
    if (activeTab === 'combinations') return `${action} Tổ hợp`;
    if (activeTab === 'quotas') return `${action} Chỉ tiêu`;
    if (activeTab === 'plans') return `${action} Đề án tuyển sinh`;
    return action;
  };

  return (
    <div className="admin-card" style={{ padding: '0', backgroundColor: 'transparent', boxShadow: 'none' }}>
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '24px' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
          <div>
            <Title level={4} style={{ textTransform: 'uppercase', margin: 0 }}>Quản lý Đề Án Tuyển Sinh</Title>
            <Text type="secondary" style={{ marginTop: '6px', display: 'block' }}>
              Cấu hình thông tin xét tuyển, phương thức, và tổ hợp môn.
            </Text>
          </div>
          
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <Select value={filterYear} onChange={setFilterYear} style={{ width: 120 }}>
              <Select.Option value="2026">Năm 2026</Select.Option>
              <Select.Option value="2025">Năm 2025</Select.Option>
              <Select.Option value="2024">Năm 2024</Select.Option>
            </Select>

            <Button icon={<RefreshCw size={16} />} onClick={fetchData} loading={loading}>Làm mới</Button>

            {selectedRowKeys.length > 0 && (
              <Popconfirm title={`Xóa ${selectedRowKeys.length} mục đã chọn?`} onConfirm={handleBulkDelete}>
                <Button danger icon={<Trash2 size={16} />}>
                  Xóa ({selectedRowKeys.length})
                </Button>
              </Popconfirm>
            )}

            {activeTab !== 'plans' && activeTab !== 'quotas' && (
              <Button type="primary" icon={<Plus size={16} />} onClick={() => openModal('add', activeTab)}>
                Thêm mới
              </Button>
            )}

            <div style={{ position: 'relative' }}>
              <input
                type="file" accept=".csv, .xlsx, .xls" id="upload-excel" style={{ display: 'none' }}
                onChange={(e) => handleFileUpload(e, activeTab)} disabled={uploading[activeTab]}
              />
              <label htmlFor="upload-excel" style={{
                  display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 16px',
                  backgroundColor: '#10b981', color: 'white', borderRadius: '6px', cursor: uploading[activeTab] ? 'not-allowed' : 'pointer', fontWeight: '500'
                }}>
                <Upload size={16} /> {uploading[activeTab] ? 'Đang tải lên...' : 'Import Excel'}
              </label>
            </div>
          </div>
        </div>

        <Tabs 
          activeKey={activeTab} 
          onChange={(key) => { setActiveTab(key); setSelectedRowKeys([]); }} 
          items={[
            {
              key: 'plans',
              label: <span><FileText size={16} style={{marginRight: 6}}/>Đề án Tuyển sinh</span>,
              children: <Table columns={planColumns} dataSource={data.plans} rowKey="id" rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }} loading={loading} scroll={{ x: 2600, y: 'calc(100vh - 300px)' }} pagination={{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['20', '50', '100', '200'] }} bordered size="middle" />
            },
            {
              key: 'quotas',
              label: <span><List size={16} style={{marginRight: 6}}/>Chỉ tiêu</span>,
              children: <Table columns={quotaColumns} dataSource={data.quotas} rowKey="id" rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }} loading={loading} bordered size="middle" />
            },
            {
              key: 'methods',
              label: <span><Layers size={16} style={{marginRight: 6}}/>Phương thức</span>,
              children: <Table columns={methodColumns} dataSource={data.methods} rowKey="id" rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }} loading={loading} bordered size="middle" />
            },
            {
              key: 'combinations',
              label: <span><List size={16} style={{marginRight: 6}}/>Tổ hợp môn</span>,
              children: <Table columns={comboColumns} dataSource={data.combinations} rowKey="combo_code" rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }} loading={loading} bordered size="middle" />
            }
          ]} 
        />

      </div>

      <Modal
        title={getModalTitle()}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={null}
        destroyOnHidden
        width={activeTab === 'plans' ? 800 : 520}
      >
        <Form form={form} layout="vertical" onFinish={handleModalSubmit}>
          {activeTab === 'methods' ? (
            <>
              <Form.Item name="year" label="Năm" rules={[{ required: true }]}><Input type="number" /></Form.Item>
              <Form.Item name="method_code" label="Mã Phương thức" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="method_name" label="Tên Phương thức" rules={[{ required: true }]}><Input /></Form.Item>
            </>
          ) : activeTab === 'combinations' ? (
            <>
              <Form.Item name="combo_code" label="Mã Tổ hợp" rules={[{ required: true }]}><Input disabled={modalType === 'edit'} /></Form.Item>
              <Form.Item name="subjects" label="Các môn học (cách nhau bởi dấu phẩy)" rules={[{ required: true }]}><Input /></Form.Item>
            </>
          ) : activeTab === 'quotas' ? (
            <>
              <Form.Item name="nam" label="Năm" rules={[{ required: true }]}><Input type="number" /></Form.Item>
              <Form.Item name="ma_xet_tuyen" label="Mã xét tuyển" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="chi_tieu" label="Chỉ tiêu" rules={[{ required: true }]}><Input type="number" /></Form.Item>
            </>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
              <Form.Item name="maXetTuyen" label="Mã xét tuyển"><Input /></Form.Item>
              <Form.Item name="maNganh" label="Mã ngành"><Input /></Form.Item>
              <Form.Item name="nam" label="Năm"><Input type="number" /></Form.Item>
              <Form.Item name="maPhuongThuc" label="Mã phương thức"><Input /></Form.Item>
              <Form.Item name="khoi" label="Khối"><Input /></Form.Item>
              <Form.Item name="diemChuan" label="Điểm chuẩn"><Input /></Form.Item>
              <Form.Item name="hocBaTrungBinhChung3Nam" label="Học bạ TBC 3 năm"><Input /></Form.Item>
              <Form.Item name="diemTotNghiep" label="Điểm tốt nghiệp"><Input /></Form.Item>
              <Form.Item name="trungBinhChung3NamNgoaiNgu" label="TBC 3 năm Ngoại ngữ"><Input /></Form.Item>
              <Form.Item name="hocLuc12" label="Học lực 12"><Input /></Form.Item>
              <Form.Item name="nangKhieu" label="Năng khiếu"><Input /></Form.Item>
              <Form.Item name="monNhanHeSo" label="Môn nhân hệ số"><Input /></Form.Item>
              <Form.Item name="tiengAnh" label="Tiếng Anh"><Input /></Form.Item>
              <Form.Item name="ngoaiNgu" label="Ngoại ngữ"><Input /></Form.Item>
              <Form.Item name="heSo" label="Hệ số"><Input /></Form.Item>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: 16 }}>
            <Button onClick={() => setIsModalOpen(false)}>Hủy</Button>
            <Button type="primary" htmlType="submit">Lưu lại</Button>
          </div>
        </Form>
      </Modal>
    </div>
  );
}
