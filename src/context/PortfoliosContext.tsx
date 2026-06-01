import { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react';
import { Portfolio } from '../types';
import { getScopedStorageKey, readStorage, storageKeys, writeStorage } from '../utils/storage';
import { ALL_PORTFOLIOS_ID } from '../utils/portfolios';
import { useAuth } from './AuthContext';
import api from '../utils/api';

type PortfoliosContextType = {
  portfolios: Portfolio[];
  activePortfolioId: string;
  activePortfolio: Portfolio | null;
  selectedPortfolios: Portfolio[];
  isAllPortfoliosSelected: boolean;
  loading: boolean;
  error: string | null;
  setActivePortfolioId: (id: string) => void;
  createPortfolio: (input: { name: string; base_currency?: string }) => Promise<Portfolio>;
  updatePortfolio: (id: string, updates: Partial<Portfolio>) => Promise<void>;
  deletePortfolio: (id: string) => Promise<void>;
  deletePortfolios: (ids: string[]) => Promise<void>;
  addPosition: (portfolioId: string, data: { ticker: string; asset_class: string; quantity: number; avg_price?: number }) => Promise<void>;
  removePosition: (portfolioId: string, ticker: string) => Promise<void>;
  refreshPortfolios: () => Promise<void>;
};

const PortfoliosContext = createContext<PortfoliosContextType | undefined>(undefined);

export function PortfoliosProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const userId = user?.id ?? null;
  const activePortfolioStorageKey = getScopedStorageKey(storageKeys.activePortfolio, userId);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [activePortfolioId, setActivePortfolioIdState] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshPortfolios = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.get<Portfolio[]>('/portfolios');
      setPortfolios(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao carregar carteiras';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!userId) {
      setPortfolios([]);
      setActivePortfolioIdState('');
      setLoading(false);
      return;
    }
    refreshPortfolios();
  }, [userId, refreshPortfolios]);

  useEffect(() => {
    if (!userId || !portfolios.length) return;
    const stored = readStorage(activePortfolioStorageKey, '');
    const exists = stored && (stored === ALL_PORTFOLIOS_ID || portfolios.some((p) => p.id === stored));
    if (exists) {
      setActivePortfolioIdState(stored);
    } else {
      setActivePortfolioIdState(portfolios[0].id);
    }
  }, [portfolios, activePortfolioStorageKey, userId]);

  useEffect(() => {
    if (!userId) return;
    if (activePortfolioId) {
      writeStorage(activePortfolioStorageKey, activePortfolioId);
    }
  }, [activePortfolioId, activePortfolioStorageKey, userId]);

  function setActivePortfolioId(id: string) {
    setActivePortfolioIdState(id);
    if (userId) {
      writeStorage(activePortfolioStorageKey, id);
    }
  }

  async function createPortfolio(input: { name: string; base_currency?: string }) {
    const created = await api.post<Portfolio>('/portfolios', {
      name: input.name.trim(),
      base_currency: input.base_currency || 'BRL',
    });
    setPortfolios((prev) => [created, ...prev]);
    setActivePortfolioId(created.id);
    return created;
  }

  async function updatePortfolio(id: string, updates: Partial<Portfolio>) {
    const updated = await api.put<Portfolio>(`/portfolios/${id}`, updates);
    setPortfolios((prev) => prev.map((p) => (p.id === id ? updated : p)));
  }

  async function deletePortfolio(id: string) {
    await api.del(`/portfolios/${id}`);
    setPortfolios((prev) => {
      const nextPortfolios = prev.filter((p) => p.id !== id);
      if (activePortfolioId === id) {
        const next = nextPortfolios[0];
        setActivePortfolioId(next?.id ?? '');
      }
      return nextPortfolios;
    });
  }

  async function deletePortfolios(ids: string[]) {
    if (!ids.length) return;
    await api.post('/portfolios/bulk-delete', { portfolio_ids: ids });
    const selected = new Set(ids);
    setPortfolios((prev) => {
      const nextPortfolios = prev.filter((p) => !selected.has(p.id));
      if (selected.has(activePortfolioId)) {
        const next = nextPortfolios[0];
        setActivePortfolioId(next?.id ?? '');
      }
      return nextPortfolios;
    });
  }

  async function addPosition(portfolioId: string, data: { ticker: string; asset_class: string; quantity: number; avg_price?: number }) {
    const updated = await api.post<Portfolio>(`/portfolios/${portfolioId}/positions`, data);
    setPortfolios((prev) => prev.map((p) => (p.id === portfolioId ? updated : p)));
  }

  async function removePosition(portfolioId: string, ticker: string) {
    const updated = await api.del<Portfolio>(`/portfolios/${portfolioId}/positions/${ticker}`);
    setPortfolios((prev) => prev.map((p) => (p.id === portfolioId ? updated : p)));
  }

  const value = useMemo<PortfoliosContextType>(() => {
    const isAllPortfoliosSelected = activePortfolioId === ALL_PORTFOLIOS_ID;
    const selectedPortfolios = isAllPortfoliosSelected
      ? portfolios
      : portfolios.filter((p) => p.id === activePortfolioId);
    const activePortfolio = portfolios.find((p) => p.id === activePortfolioId) ?? portfolios[0] ?? null;

    return {
      portfolios,
      activePortfolioId: isAllPortfoliosSelected ? ALL_PORTFOLIOS_ID : activePortfolio?.id ?? '',
      activePortfolio,
      selectedPortfolios,
      isAllPortfoliosSelected,
      loading,
      error,
      setActivePortfolioId,
      createPortfolio,
      updatePortfolio,
      deletePortfolio,
      deletePortfolios,
      addPosition,
      removePosition,
      refreshPortfolios,
    };
  }, [activePortfolioId, portfolios, loading, error]);

  return <PortfoliosContext.Provider value={value}>{children}</PortfoliosContext.Provider>;
}

export function usePortfolios() {
  const context = useContext(PortfoliosContext);
  if (!context) throw new Error('usePortfolios must be used within PortfoliosProvider');
  return context;
}
