import { initialPortfolios } from '../data/mocks';
import { Portfolio } from '../types';

export const ALL_PORTFOLIOS_ID = '__all_portfolios__';

export function normalizePortfolio(portfolio: Portfolio): Portfolio {
  return {
    ...portfolio,
    description: portfolio.description ?? 'Carteira sem descrição.',
  };
}

export function normalizePortfolios(portfolios: Portfolio[]): Portfolio[] {
  return portfolios.map(normalizePortfolio);
}

export function getPortfolioLabel(portfolio: Portfolio): string {
  if (portfolio.source === 'manual') return portfolio.name;
  const suffix = portfolio.source.toUpperCase();
  return portfolio.name.includes(`(${suffix})`) ? portfolio.name : `${portfolio.name} (${suffix})`;
}

export function getActivePortfolioSelectionLabel(activePortfolio: Portfolio | null, isAllSelected: boolean): string {
  if (isAllSelected) return 'Todas as carteiras';
  return activePortfolio ? getPortfolioLabel(activePortfolio) : 'Nenhuma carteira';
}

export function getInitialPortfolios(): Portfolio[] {
  return normalizePortfolios(initialPortfolios);
}
