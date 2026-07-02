import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import AdminLayout from "./components/admin/AdminLayout";
import DocumentUpload from "./pages/admin/DocumentUpload";
import ChunkReview from "./pages/admin/ChunkReview";
import ProvidersConfig from "./pages/admin/ProvidersConfig";
import SlotsConfig from "./pages/admin/SlotsConfig";
import SystemStatus from "./pages/admin/SystemStatus";
import AdminLogin from "./pages/admin/AdminLogin";
import GoogleCallback from "./pages/auth/GoogleCallback";
import AcademicStructure from "./pages/admin/AcademicStructure";
import AdmissionManagement from "./pages/admin/AdmissionManagement";
import StaffManagement from "./pages/admin/StaffManagement";
import CandidateManagement from "./pages/admin/CandidateManagement";
import AdmissionCodeManagement from "./pages/admin/AdmissionCodeManagement";
import QAApproval from "./pages/admin/QAApproval";
import OnlineSupport from "./pages/admin/OnlineSupport";

// Component để bảo vệ các route cần đăng nhập
const ProtectedRoute = () => {
  const token = localStorage.getItem("access_token");
  if (!token) {
    return <Navigate to="/admin/login" replace />;
  }

  // Giải mã JWT để kiểm tra role (cấu trúc token: header.payload.signature)
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function (c) {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));

    const payload = JSON.parse(jsonPayload);
    if (payload.role === 'CANDIDATE') {
      return <Navigate to="/" replace />;
    }
  } catch (e) {
    console.error("Lỗi parse token", e);
    // Nếu token không hợp lệ, chuyển ra ngoài
    return <Navigate to="/" replace />;
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
            <Route index element={<Navigate to="/admin/documents" replace />} />
            <Route path="documents" element={<DocumentUpload />} />
            <Route path="documents/:id/review" element={<ChunkReview />} />
            <Route path="providers" element={<ProvidersConfig />} />
            <Route path="slots" element={<SlotsConfig />} />
            <Route path="academic-structure" element={<AcademicStructure />} />
            <Route path="admission-plans" element={<AdmissionManagement />} />
            <Route path="admission-codes" element={<AdmissionCodeManagement />} />
            <Route path="staff" element={<StaffManagement />} />
            <Route path="candidates" element={<CandidateManagement />} />
            <Route path="qa-approval" element={<QAApproval />} />
            <Route path="support" element={<OnlineSupport />} />
            <Route path="status" element={<SystemStatus />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
