import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import DecisionCenterPage from "./pages/DecisionCenterPage";
import AdvancedPage from "./pages/AdvancedPage";
import RunConference from "./pages/RunConference";
import ConferenceDetailPage from "./pages/ConferenceDetailPage";
import OrdersPage from "./pages/OrdersPage";
import PositionsPage from "./pages/PositionsPage";
import ProposalsPage from "./pages/ProposalsPage";
import AuditPage from "./pages/AuditPage";
import SetupWizardPage from "./pages/SetupWizardPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DecisionCenterPage />} />
        <Route path="/advanced" element={<AdvancedPage />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/proposals" element={<ProposalsPage />} />
        <Route path="/run" element={<RunConference />} />
        <Route path="/conference/:conferenceId" element={<ConferenceDetailPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/positions" element={<PositionsPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/setup" element={<SetupWizardPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
