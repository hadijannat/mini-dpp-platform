import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { LoadingSpinner } from './components/loading-spinner';

// Layouts (kept as static imports -- lightweight, always needed for route groups)
import ViewerLayout from './app/layouts/ViewerLayout';
import PublisherLayout from './app/layouts/PublisherLayout';

// Auth (kept static -- needed on initial navigation)
import CallbackPage from './auth/CallbackPage';
import ProtectedRoute from './auth/ProtectedRoute';

// Lazy-loaded pages
const LandingPage = lazy(() => import('./features/landing/LandingPage'));
const LoginPage = lazy(() => import('./auth/LoginPage'));
const DPPViewerPage = lazy(() => import('./features/viewer/pages/DPPViewerPage'));
const DashboardPage = lazy(() => import('./features/publisher/pages/DashboardPage'));
const DPPListPage = lazy(() => import('./features/publisher/pages/DPPListPage'));
const DPPEditorPage = lazy(() => import('./features/publisher/pages/DPPEditorPage'));
const TemplatesPage = lazy(() => import('./features/publisher/pages/TemplatesPage'));
const DataCarriersPage = lazy(() => import('./features/publisher/pages/DataCarriersPage'));
const MastersPage = lazy(() => import('./features/publisher/pages/MastersPage'));
const ConnectorsPage = lazy(() => import('./features/connectors/pages/ConnectorsPage'));
const CompliancePage = lazy(() => import('./features/compliance/pages/CompliancePage'));
const AuditPage = lazy(() => import('./features/audit/pages/AuditPage'));
const EPCISPage = lazy(() => import('./features/epcis/pages/EPCISPage'));
const SubmodelEditorPage = lazy(() => import('./features/editor/pages/SubmodelEditorPage'));
const BatchImportPage = lazy(() => import('./features/publisher/pages/BatchImportPage'));
const AdminDashboardPage = lazy(() => import('./features/admin/pages/AdminDashboardPage'));
const GlobalIdSettingsPage = lazy(() => import('./features/admin/pages/GlobalIdSettingsPage'));
const TenantsPage = lazy(() => import('./features/admin/pages/TenantsPage'));

function App() {
  const auth = useAuth();

  return (
    <Suspense fallback={<LoadingSpinner size="lg" />}>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/callback" element={<CallbackPage />} />

        {/* Viewer routes (public -- no auth required for published DPPs) */}
        <Route element={<ViewerLayout />}>
          <Route path="/t/:tenantSlug/dpp/:dppId" element={<DPPViewerPage />} />
          <Route path="/t/:tenantSlug/p/:slug" element={<DPPViewerPage />} />
          <Route path="/dpp/:dppId" element={<DPPViewerPage />} />
          <Route path="/p/:slug" element={<DPPViewerPage />} />
        </Route>

        {/* Publisher routes (authenticated, publisher role) */}
        {/* Show loading spinner while OIDC discovery is in progress for auth routes */}
        <Route
          path="/console"
          element={
            auth.isLoading ? (
              <div className="flex h-screen items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
              </div>
            ) : (
              <ProtectedRoute requiredRole="publisher">
                <PublisherLayout />
              </ProtectedRoute>
            )
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
          <Route path="compliance" element={<CompliancePage />} />
          <Route path="epcis" element={<EPCISPage />} />
          <Route path="batch-import" element={<BatchImportPage />} />
          <Route
            path="admin"
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="audit"
            element={
              <ProtectedRoute requiredRole="admin">
                <AuditPage />
              </ProtectedRoute>
            }
          />
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

        {/* Landing page */}
        <Route path="/" element={<LandingPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default App;
