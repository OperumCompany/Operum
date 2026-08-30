import React, { lazy, Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import '@fontsource-variable/hanken-grotesk';
import '@fontsource-variable/manrope';
import '@fontsource-variable/geist';
import App from './App';
import { AuthProvider } from './context/AuthContext';
import { PortfoliosProvider } from './context/PortfoliosContext';
import { ThemeProvider } from './context/ThemeContext';
import './styles.css';

const PresentationPage = lazy(() => import('./presentation/PresentationPage').then((module) => ({ default: module.PresentationPage })));

function PresentationLoader() {
  return <div className="presentation-loader">Preparando apresentação…</div>;
}

function OperumApplication() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <PortfoliosProvider>
          <App />
        </PortfoliosProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

function Root() {
  return (
    <Routes>
      <Route path="/slides" element={<Suspense fallback={<PresentationLoader />}><PresentationPage /></Suspense>} />
      <Route path="*" element={<OperumApplication />} />
    </Routes>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Root />
    </BrowserRouter>
  </React.StrictMode>,
);
