
# UI Layout & Formatting Standards

## Admin Page Headers
When creating or editing Admin pages, you MUST adhere to the following UI layout for the page header to maintain consistency across the application. Do not use Ant Design's <Title> or <Text> components for the main page header. Use native HTML <h3> and <p> tags with inline styles instead.

Example format:
``javascript
<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1.5px solid var(--border-color)', paddingBottom: '16px', marginBottom: '24px' }}>
  <div>
    <h3 style={{ fontSize: '1.3rem', textTransform: 'uppercase', margin: 0 }}>TIÊU Ð? TRANG</h3>
    <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '6px', marginBottom: 0 }}>
      Mô t? ph? cho trang qu?n l?.
    </p>
  </div>
  {/* Các nút thao tác n?u có */}
</div>
``
