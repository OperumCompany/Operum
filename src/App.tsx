import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppShell } from './layout/AppShell';

const ChatPage = lazy(() => import('./pages/ChatPage').then((module) => ({ default: module.ChatPage })));
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })));
const DashboardTechnicalPage = lazy(() => import('./pages/DashboardTechnicalPage').then((module) => ({ default: module.DashboardTechnicalPage })));
const LoginPage = lazy(() => import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })));
const NewsPage = lazy(() => import('./pages/NewsPage').then((module) => ({ default: module.NewsPage })));
const PortfolioDetailsPage = lazy(() => import('./pages/PortfolioDetailsPage').then((module) => ({ default: module.PortfolioDetailsPage })));
const PortfoliosPage = lazy(() => import('./pages/PortfoliosPage').then((module) => ({ default: module.PortfoliosPage })));
const RegisterPage = lazy(() => import('./pages/RegisterPage').then((module) => ({ default: module.RegisterPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })));

function PageLoader() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center rounded-[30px] border border-[var(--border-soft)] bg-[var(--bg-surface)] p-8 text-sm font-semibold text-[var(--text-muted)] shadow-[var(--shadow-card)]">
      Carregando...
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/registro" element={<RegisterPage />} />
        <Route
          path="/"
          element={(
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          )}
        >
          <Route index element={<DashboardPage />} />
          <Route path="dashboard-tecnico" element={<DashboardTechnicalPage />} />
          <Route path="noticias" element={<NewsPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="carteiras" element={<PortfoliosPage />} />
          <Route path="carteiras/:id" element={<PortfolioDetailsPage />} />
          <Route path="configuracoes" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
