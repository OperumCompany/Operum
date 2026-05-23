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

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
};

export type AssetClass = 'Renda fixa' | 'Ações Brasil' | 'Ações EUA' | 'Fundos' | 'Cripto';

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

// --- Backend-aligned types ---

export type Asset = {
  ticker: string;
  name: string;
  asset_class: string;
  country: string;
  currency: string;
  sector: string;
  sub_type: string;
  source: string;
};

export type Position = {
  asset_id: string;
  ticker: string;
  asset_class: string;
  quantity: number;
  avg_price: number | null;
  currency: string;
  manual_notes: string;
};

export type PortfolioSettings = {
  risk_profile: string;
  forecast_horizon_days: number;
};

export type Portfolio = {
  id: string;
  name: string;
  base_currency: string;
  created_at: string;
  updated_at: string;
  positions: Position[];
  settings: PortfolioSettings;
};

export type PortfolioAnalysis = {
  weights: Record<string, number>;
  class_weights: Record<string, number>;
  concentration: number;
  concentration_label: string;
  correlation_matrix: number[][] | null;
  volatility: number | null;
  portfolio_return: number | null;
  var_95: number | null;
  cvar_95: number | null;
  beta: number | null;
  num_assets: number;
  num_classes: number;
};

export type NewsItem = {
  id: string;
  title: string;
  subtitle: string | null;
  content_preview: string;
  full_text_if_available: string | null;
  source_name: string;
  source_url: string;
  published_at: string;
  language: string;
  tags: string[];
  mentioned_assets: string[];
  mentioned_countries: string[];
  mentioned_sectors: string[];
  sentiment_score: number;
  relevance_score: number;
  impact_score: number;
  summary: string;
  cluster_id: number | null;
  created_at: string;
};
