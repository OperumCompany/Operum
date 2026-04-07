export type User = {
  id: string;
  name: string;
  email: string;
  password: string;
};

export type NewsCategory =
  | 'Inflação'
  | 'Juros'
  | 'Tecnologia'
  | 'Criptomoedas'
  | 'Ações'
  | 'Exterior'
  | 'Política econômica'
  | 'Renda fixa';

export type Impact = 'Alto' | 'Médio' | 'Baixo';

export type NewsItem = {
  id: string;
  title: string;
  summary: string;
  category: NewsCategory;
  date: string;
  source: string;
  impact: Impact;
  featured?: boolean;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
};

export type AssetClass = 'Renda fixa' | 'Ações Brasil' | 'Ações EUA' | 'Fundos' | 'Cripto';

export type Asset = {
  ticker: string;
  name: string;
  class: AssetClass;
  risk: number;
};

export type PortfolioAsset = {
  id: string;
  ticker: string;
  allocation: number;
};

export type Portfolio = {
  id: string;
  name: string;
  description: string;
  assets: PortfolioAsset[];
  createdAt: string;
  source: 'manual' | 'csv' | 'sheet' | 'example';
};

export type DashboardMetric = {
  label: string;
  value: string;
  variation: string;
};

export type UserPreferences = {
  topics: NewsCategory[];
  compactMode: boolean;
  notifications: boolean;
};
