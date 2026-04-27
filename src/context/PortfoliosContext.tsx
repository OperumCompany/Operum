import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { Portfolio } from '../types';
import { getScopedStorageKey, readStorage, storageKeys, writeStorage } from '../utils/storage';
import { ALL_PORTFOLIOS_ID, getInitialPortfolios, normalizePortfolio, normalizePortfolios } from '../utils/portfolios';
import { useAuth } from './AuthContext';

type PortfoliosContextType = {
  portfolios: Portfolio[];
  activePortfolioId: string;
  activePortfolio: Portfolio | null;
  selectedPortfolios: Portfolio[];
  isAllPortfoliosSelected: boolean;
  setActivePortfolioId: (id: string) => void;
  createPortfolio: (input: { name: string; description: string }) => Portfolio;
  importPortfolio: (source: Portfolio['source']) => Portfolio;
  updatePortfolio: (id: string, updater: (current: Portfolio) => Portfolio) => void;
  deletePortfolio: (id: string) => void;
};

const PortfoliosContext = createContext<PortfoliosContextType | undefined>(undefined);

export function PortfoliosProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const userId = user?.id ?? null;
  const portfoliosStorageKey = getScopedStorageKey(storageKeys.portfolios, userId);
  const activePortfolioStorageKey = getScopedStorageKey(storageKeys.activePortfolio, userId);
  const [portfolios, setPortfolios] = useState<Portfolio[]>(() => getInitialPortfolios());
  const [activePortfolioId, setActivePortfolioIdState] = useState<string>(() => getInitialPortfolios()[0]?.id ?? '');

  useEffect(() => {
    if (!userId) {
      setPortfolios(getInitialPortfolios());
      setActivePortfolioIdState(getInitialPortfolios()[0]?.id ?? '');
      return;
    }

    const nextPortfolios = normalizePortfolios(readStorage<Portfolio[]>(portfoliosStorageKey, getInitialPortfolios()));
    const nextActivePortfolioId = readStorage(activePortfolioStorageKey, nextPortfolios[0]?.id ?? '');

    setPortfolios(nextPortfolios);
    setActivePortfolioIdState(nextActivePortfolioId);
  }, [activePortfolioStorageKey, portfoliosStorageKey, userId]);

  useEffect(() => {
    if (!userId) return;

    if (!portfolios.length) {
      setActivePortfolioIdState('');
      writeStorage(activePortfolioStorageKey, '');
      return;
    }

    if (activePortfolioId === ALL_PORTFOLIOS_ID) {
      writeStorage(activePortfolioStorageKey, ALL_PORTFOLIOS_ID);
      return;
    }

    const exists = portfolios.some((portfolio) => portfolio.id === activePortfolioId);
    if (!exists) {
      const fallbackId = portfolios[0].id;
      setActivePortfolioIdState(fallbackId);
      writeStorage(activePortfolioStorageKey, fallbackId);
    }
  }, [activePortfolioId, activePortfolioStorageKey, portfolios, userId]);

  useEffect(() => {
    if (!userId) return;
    writeStorage(portfoliosStorageKey, portfolios);
  }, [portfolios, portfoliosStorageKey, userId]);

  function setActivePortfolioId(id: string) {
    setActivePortfolioIdState(id);
    if (userId) {
      writeStorage(activePortfolioStorageKey, id);
    }
  }

  function createPortfolio(input: { name: string; description: string }) {
    const next = normalizePortfolio({
      id: crypto.randomUUID(),
      name: input.name.trim(),
      description: input.description.trim(),
      assets: [],
      createdAt: new Date().toISOString().slice(0, 10),
      source: 'manual',
    });

    setPortfolios((prev) => [next, ...prev]);
    setActivePortfolioId(next.id);
    return next;
  }

  function importPortfolio(source: Portfolio['source']) {
    const base = getInitialPortfolios()[0];
    const next = normalizePortfolio({
      ...base,
      id: crypto.randomUUID(),
      name: base.name,
      description: `Carteira criada a partir de um modelo ${source.toUpperCase()} para você começar mais rápido.`,
      source,
      createdAt: new Date().toISOString().slice(0, 10),
      assets: base.assets.map((asset) => ({ ...asset, id: crypto.randomUUID() })),
    });

    setPortfolios((prev) => [next, ...prev]);
    setActivePortfolioId(next.id);
    return next;
  }

  function updatePortfolio(id: string, updater: (current: Portfolio) => Portfolio) {
    setPortfolios((prev) => prev.map((portfolio) => (portfolio.id === id ? normalizePortfolio(updater(portfolio)) : portfolio)));
  }

  function deletePortfolio(id: string) {
    setPortfolios((prev) => prev.filter((portfolio) => portfolio.id !== id));
  }

  const value = useMemo<PortfoliosContextType>(() => {
    const isAllPortfoliosSelected = activePortfolioId === ALL_PORTFOLIOS_ID;
    const selectedPortfolios = isAllPortfoliosSelected ? portfolios : portfolios.filter((portfolio) => portfolio.id === activePortfolioId);
    const activePortfolio = portfolios.find((portfolio) => portfolio.id === activePortfolioId) ?? portfolios[0] ?? null;

    return {
      portfolios,
      activePortfolioId: isAllPortfoliosSelected ? ALL_PORTFOLIOS_ID : activePortfolio?.id ?? '',
      activePortfolio,
      selectedPortfolios,
      isAllPortfoliosSelected,
      setActivePortfolioId,
      createPortfolio,
      importPortfolio,
      updatePortfolio,
      deletePortfolio,
    };
  }, [activePortfolioId, portfolios]);

  return <PortfoliosContext.Provider value={value}>{children}</PortfoliosContext.Provider>;
}

export function usePortfolios() {
  const context = useContext(PortfoliosContext);
  if (!context) throw new Error('usePortfolios must be used within PortfoliosProvider');
  return context;
}
