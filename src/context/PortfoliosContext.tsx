import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { Portfolio } from '../types';
import { readStorage, storageKeys, writeStorage } from '../utils/storage';
import { ALL_PORTFOLIOS_ID, getInitialPortfolios, normalizePortfolio, normalizePortfolios } from '../utils/portfolios';

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
  const [portfolios, setPortfolios] = useState<Portfolio[]>(() =>
    normalizePortfolios(readStorage<Portfolio[]>(storageKeys.portfolios, getInitialPortfolios())),
  );
  const [activePortfolioId, setActivePortfolioIdState] = useState<string>(() =>
    readStorage(storageKeys.activePortfolio, portfolios[0]?.id ?? ''),
  );

  useEffect(() => {
    if (!portfolios.length) {
      setActivePortfolioIdState('');
      writeStorage(storageKeys.activePortfolio, '');
      return;
    }

    if (activePortfolioId === ALL_PORTFOLIOS_ID) {
      writeStorage(storageKeys.activePortfolio, ALL_PORTFOLIOS_ID);
      return;
    }

    const exists = portfolios.some((portfolio) => portfolio.id === activePortfolioId);
    if (!exists) {
      const fallbackId = portfolios[0].id;
      setActivePortfolioIdState(fallbackId);
      writeStorage(storageKeys.activePortfolio, fallbackId);
    }
  }, [activePortfolioId, portfolios]);

  useEffect(() => {
    writeStorage(storageKeys.portfolios, portfolios);
  }, [portfolios]);

  function setActivePortfolioId(id: string) {
    setActivePortfolioIdState(id);
    writeStorage(storageKeys.activePortfolio, id);
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
