import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './context/AuthContext';
import { PortfoliosProvider } from './context/PortfoliosContext';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <PortfoliosProvider>
          <App />
        </PortfoliosProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
