import { Navigate, Route, Routes } from "react-router-dom";
import UploadPage from "./pages/Upload";
import AnalyzingPage from "./pages/Analyzing";
import ReportPage from "./pages/Report";
import VideoPage from "./pages/Video";

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/analyzing" element={<AnalyzingPage />} />
        <Route path="/report" element={<ReportPage />} />
        <Route path="/video" element={<VideoPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
