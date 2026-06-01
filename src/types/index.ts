export type User = {
  id: string;
  name: string;
  email: string;
  password?: string;
  created_at?: string;
  updated_at?: string;
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

export type AuthResponse = {
  token: string;
  user: User;
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
  volatility_window_days: number;
  portfolio_return: number | null;
  var_95: number | null;
  cvar_95: number | null;
  beta: number | null;
  benchmark: {
    ticker: string | null;
    label: string;
    return_21d_pct: number | null;
    return_42d_pct: number | null;
    return_63d_pct: number | null;
    return_252d_pct: number | null;
  };
  num_assets: number;
  num_classes: number;
};

export type NewsItem = {
  id: string;
  title: string;
  subtitle: string | null;
  content_preview: string;
  full_text_if_available: string | null;
  source_id?: string;
  source_name: string;
  source_type?: string;
  is_official?: boolean;
  source_category?: string | null;
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

export type PortfolioOpinion = {
  score: number;
  components: {
    diversification: number;
    correlation_risk: number;
    news_impact: number;
    macro_sensitivity: number;
    forecast_risk: number;
  };
  opinion: string;
  headline: string;
  composition_grade: string;
  composition_summary: string;
  strengths: string[];
  overlaps: string[];
  block_reviews: Array<{
    title: string;
    assessment: string;
    highlights: string;
  }>;
  final_diagnosis: string;
  conclusion: string;
  sources: Array<{
    id: string;
    title: string;
    source_name: string;
    source_url: string;
    published_at: string;
    summary: string;
    sentiment_score: number;
    impact_score: number;
    relevance_score: number;
    match_score: number;
    rank_score?: number;
    source_category?: string | null;
    is_official?: boolean;
    context_role?: string;
    source_confidence_weight?: number;
  }>;
  source_groups: Array<{
    source_name: string;
    count: number;
    items: Array<PortfolioOpinion['sources'][number] & { role?: string }>;
  }>;
  selected_analysis_horizon?: '1m' | '2m' | '3m';
  portfolio_id: string;
  generated_at: string;
};

export type HorizonSeriesPoint = {
  date: string;
  value: number;
};

export type PositionOpinion = {
  portfolio_id: string;
  ticker: string;
  asset_name: string;
  asset_class: string;
  generated_at: string;
  recomputed_at: string;
  confidence: string;
  status: string;
  selected_history_horizon: '1m' | '2m' | '3m';
  selected_outlook_horizon: '1w' | '1m' | '2m' | '3m';
  current_snapshot: {
    current_price: number | null;
    currency: string;
    weight_pct: number | null;
    sector: string;
    country: string;
  };
  historical_window: {
    start_date: string;
    end_date: string;
    news_count: number;
    has_price_history: boolean;
  };
  historical_series: HorizonSeriesPoint[];
  forecast_series: HorizonSeriesPoint[];
  forecast_anchor_points: Array<{
    date: string;
    horizon_days: number;
    predicted_price: number;
    predicted_return: number;
    confidence: number;
  }>;
  recent_performance: {
    change_selected_pct: number | null;
    change_1m_pct: number | null;
    change_2m_pct: number | null;
    change_3m_pct: number | null;
    change_12m_pct: number | null;
    volatility_selected_pct: number | null;
    drawdown_selected_pct?: number | null;
    beta_selected?: number | null;
    correlation_selected?: number | null;
    benchmark_ticker?: string | null;
    forecast_return_selected_pct?: number | null;
    forecast_price_selected?: number | null;
    forecast_confidence_selected?: number | null;
  };
  outlook_3m: {
    scenario: string;
    dominant_topics: string[];
  };
  analysis_sections: {
    current: string;
    recent: string;
    outlook: string;
    recent_by_horizon: Record<string, string>;
    outlook_by_horizon: Record<string, string>;
  };
  used_news_count: number;
  sources: PortfolioOpinion['sources'];
  source_groups: Array<{
    source_name: string;
    count: number;
    items: Array<PortfolioOpinion['sources'][number] & { role?: string }>;
  }>;
};
