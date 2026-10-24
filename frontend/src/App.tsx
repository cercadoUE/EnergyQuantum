import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import MapPage from "./pages/MapPage";
import NetworkPage from "./pages/NetworkPage";
import SubnetsPage from "./pages/SubnetsPage";
import OptimizationPage from "./pages/OptimizationPage";
import FailuresPage from "./pages/FailuresPage";
import ComparePage from "./pages/ComparePage";
import SourcesPage from "./pages/SourcesPage";
import SyntheticPage from "./pages/SyntheticPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/mapa" replace />} />
        <Route path="/mapa" element={<MapPage />} />
        <Route path="/red" element={<NetworkPage />} />
        <Route path="/subredes" element={<SubnetsPage />} />
        <Route path="/optimizacion" element={<OptimizationPage />} />
        <Route path="/fallas" element={<FailuresPage />} />
        <Route path="/comparacion" element={<ComparePage />} />
        <Route path="/sintetico" element={<SyntheticPage />} />
        <Route path="/fuentes" element={<SourcesPage />} />
        <Route path="*" element={<Navigate to="/mapa" replace />} />
      </Route>
    </Routes>
  );
}
