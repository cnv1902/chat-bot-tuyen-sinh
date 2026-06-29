import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import AdminLayout from "./components/admin/AdminLayout";
import UploadDocument from "./pages/admin/UploadDocument";
import ManageDocuments from "./pages/admin/ManageDocuments";
import ProvidersConfig from "./pages/admin/ProvidersConfig";
import SlotsConfig from "./pages/admin/SlotsConfig";
import SystemStatus from "./pages/admin/SystemStatus";
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        
        {/* Admin Nested Routes */}
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Navigate to="/admin/upload" replace />} />
          <Route path="upload" element={<UploadDocument />} />
          <Route path="manage" element={<ManageDocuments />} />
          <Route path="providers" element={<ProvidersConfig />} />
          <Route path="slots" element={<SlotsConfig />} />
          <Route path="status" element={<SystemStatus />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
