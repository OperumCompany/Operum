import { Portfolio } from '../types';

export const ALL_PORTFOLIOS_ID = '__all_portfolios__';

export function getPortfolioLabel(portfolio: Portfolio): string {
  return portfolio.name;
}

export function getActivePortfolioSelectionLabel(activePortfolio: Portfolio | null, isAllSelected: boolean): string {
  if (isAllSelected) return 'Todas as carteiras';
  return activePortfolio ? getPortfolioLabel(activePortfolio) : 'Nenhuma carteira';
}

export function mapAssetClassToLabel(assetClass: string): string {
  const map: Record<string, string> = {
    BR_STOCK: 'Ações Brasil',
    FII: 'Fundos Imobiliários',
    US_STOCK: 'Ações EUA',
    CRYPTO: 'Cripto',
  };
  return map[assetClass] ?? assetClass;
}
