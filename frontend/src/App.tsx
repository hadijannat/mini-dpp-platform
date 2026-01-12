import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';

// Layouts
import ViewerLayout from './app/layouts/ViewerLayout';
import PublisherLayout from './app/layouts/PublisherLayout';

// Viewer pages
import DPPViewerPage from './features/viewer/pages/DPPViewerPage';

// Publisher pages
import DashboardPage from './features/publisher/pages/DashboardPage';
import DPPListPage from './features/publisher/pages/DPPListPage';
import DPPEditorPage from './features/publisher/pages/DPPEditorPage';
import TemplatesPage from './features/publisher/pages/TemplatesPage';
import DataCarriersPage from './features/publisher/pages/DataCarriersPage';
import MastersPage from './features/publisher/pages/MastersPage';
import ConnectorsPage from './features/connectors/pages/ConnectorsPage';
import SubmodelEditorPage from './features/editor/pages/SubmodelEditorPage';
import GlobalIdSettingsPage from './features/admin/pages/GlobalIdSettingsPage';
import TenantsPage from './features/admin/pages/TenantsPage';

// Auth
import LoginPage from './auth/LoginPage';
import CallbackPage from './auth/CallbackPage';
import ProtectedRoute from './auth/ProtectedRoute';

function App() {
  const auth = useAuth();

  if (auth.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500"></div>
      </div>
    );
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/callback" element={<CallbackPage />} />

      {/* Viewer routes (auth required) */}
      <Route
        element={
          <ProtectedRoute>
            <ViewerLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/t/:tenantSlug/dpp/:dppId" element={<DPPViewerPage />} />
        <Route path="/t/:tenantSlug/p/:slug" element={<DPPViewerPage />} />
        <Route path="/dpp/:dppId" element={<DPPViewerPage />} />
        <Route path="/p/:slug" element={<DPPViewerPage />} />
      </Route>

      {/* Publisher routes (authenticated, publisher role) */}
      <Route
        path="/console"
        element={
          <ProtectedRoute requiredRole="publisher">
            <PublisherLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="dpps" element={<DPPListPage />} />
        <Route path="masters" element={<MastersPage />} />
        <Route path="dpps/:dppId" element={<DPPEditorPage />} />
        <Route path="dpps/:dppId/edit/:templateKey" element={<SubmodelEditorPage />} />
        <Route path="templates" element={<TemplatesPage />} />
        <Route path="carriers" element={<DataCarriersPage />} />
        <Route path="connectors" element={<ConnectorsPage />} />
        <Route
          path="settings"
          element={
            <ProtectedRoute requiredRole="admin">
              <GlobalIdSettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="tenants"
          element={
            <ProtectedRoute requiredRole="admin">
              <TenantsPage />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/console" replace />} />
      <Route path="*" element={<Navigate to="/console" replace />} />
    </Routes>
  );
}

export default App;
