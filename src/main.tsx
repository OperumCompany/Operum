import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './context/AuthContext';
import { PortfoliosProvider } from './context/PortfoliosContext';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <PortfoliosProvider>
          <App />
        </PortfoliosProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
