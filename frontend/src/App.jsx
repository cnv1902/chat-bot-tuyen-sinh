import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import AdminLayout from "./components/admin/AdminLayout";
import UploadDocument from "./pages/admin/UploadDocument";
import ManageDocuments from "./pages/admin/ManageDocuments";
import ProvidersConfig from "./pages/admin/ProvidersConfig";
import SlotsConfig from "./pages/admin/SlotsConfig";
import SystemStatus from "./pages/admin/SystemStatus";
import AdminLogin from "./pages/admin/AdminLogin";
import GoogleCallback from "./pages/auth/GoogleCallback";
import AcademicStructure from "./pages/admin/AcademicStructure";
import AdmissionManagement from "./pages/admin/AdmissionManagement";
import StaffManagement from "./pages/admin/StaffManagement";
import CandidateManagement from "./pages/admin/CandidateManagement";

// Component để bảo vệ các route cần đăng nhập
const ProtectedRoute = () => {
  const token = localStorage.getItem("access_token");
  if (!token) {
    return <Navigate to="/admin/login" replace />;
  }
  return <Outlet />;
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        
        {/* Public Admin Routes */}
        <Route path="/admin/login" element={<AdminLogin />} />
        
        {/* Public OAuth Routes */}
        <Route path="/auth/google/callback" element={<GoogleCallback />} />

        {/* Protected Admin Nested Routes */}
        <Route path="/admin" element={<ProtectedRoute />}>
          <Route element={<AdminLayout />}>
            <Route index element={<Navigate to="/admin/upload" replace />} />
            <Route path="upload" element={<UploadDocument />} />
            <Route path="manage" element={<ManageDocuments />} />
            <Route path="providers" element={<ProvidersConfig />} />
            <Route path="slots" element={<SlotsConfig />} />
            <Route path="academic-structure" element={<AcademicStructure />} />
            <Route path="admission-plans" element={<AdmissionManagement />} />
            <Route path="staff" element={<StaffManagement />} />
            <Route path="candidates" element={<CandidateManagement />} />
            <Route path="status" element={<SystemStatus />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
