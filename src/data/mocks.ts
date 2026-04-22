import { Asset, ChatMessage, DashboardMetric, NewsItem, Portfolio, User, UserPreferences } from '../types';

export const defaultUser: User = {
  id: 'u-1',
  name: 'Camila Andrade',
  email: 'camila@operum.app',
  password: 'Operum123',
};

export const assetsCatalog: Asset[] = [
  { ticker: 'TESOURO-IPCA+', name: 'Tesouro IPCA+', class: 'Renda fixa', risk: 2 },
  { ticker: 'CDB-120', name: 'CDB 120% CDI', class: 'Renda fixa', risk: 2 },
  { ticker: 'PETR4', name: 'Petrobras PN', class: 'Ações Brasil', risk: 4 },
  { ticker: 'VALE3', name: 'Vale ON', class: 'Ações Brasil', risk: 4 },
  { ticker: 'AAPL34', name: 'Apple BDR', class: 'Ações EUA', risk: 3 },
  { ticker: 'IVVB11', name: 'ETF S&P 500', class: 'Ações EUA', risk: 3 },
  { ticker: 'HGLG11', name: 'FII Logístico', class: 'Fundos', risk: 3 },
  { ticker: 'BTC', name: 'Bitcoin', class: 'Cripto', risk: 5 },
];

export const initialPortfolios: Portfolio[] = [
  {
    id: 'p-1',
    name: 'Carteira Longo Prazo',
    description: 'Estratégia diversificada com foco em crescimento e proteção no longo prazo.',
    source: 'example',
    createdAt: '2026-02-12',
    assets: [
      { id: 'pa1', ticker: 'TESOURO-IPCA+', allocation: 25 },
      { id: 'pa2', ticker: 'PETR4', allocation: 15 },
      { id: 'pa3', ticker: 'IVVB11', allocation: 20 },
      { id: 'pa4', ticker: 'HGLG11', allocation: 20 },
      { id: 'pa5', ticker: 'BTC', allocation: 20 },
    ],
  },
];

export const newsData: NewsItem[] = [
  {
    id: 'n1',
    title: 'IPCA desacelera no fechamento do trimestre',
    summary: 'Leitura de inflação veio ligeiramente abaixo do consenso e alivia pressão de curto prazo.',
    category: 'Inflação',
    date: '2026-04-05',
    source: 'Boletim Macro BR',
    impact: 'Médio',
    featured: true,
  },
  {
    id: 'n2',
    title: 'Banco Central reforça comunicação sobre juros estáveis',
    summary: 'Ata sinaliza cautela e foco na convergência inflacionária.',
    category: 'Juros',
    date: '2026-04-05',
    source: 'Painel Monetário',
    impact: 'Alto',
    featured: true,
  },
  {
    id: 'n3',
    title: 'Big techs ampliam investimento em IA corporativa',
    summary: 'Empresas listadas registram nova rodada de capex com foco em produtividade.',
    category: 'Tecnologia',
    date: '2026-04-04',
    source: 'Tech Markets Daily',
    impact: 'Médio',
  },
  {
    id: 'n4',
    title: 'Bitcoin oscila com fluxo institucional menor',
    summary: 'Mercado cripto opera com volatilidade elevada e baixa liquidez no intraday.',
    category: 'Criptomoedas',
    date: '2026-04-04',
    source: 'Crypto Pulse',
    impact: 'Alto',
  },
  {
    id: 'n5',
    title: 'Ibovespa fecha em alta puxado por commodities',
    summary: 'Ações de mineração e energia sustentam ganho da sessão.',
    category: 'Ações',
    date: '2026-04-03',
    source: 'Mercado Agora',
    impact: 'Médio',
  },
  {
    id: 'n6',
    title: 'Bolsas globais monitoram dados de emprego nos EUA',
    summary: 'Indicadores de trabalho influenciam expectativa de política monetária.',
    category: 'Exterior',
    date: '2026-04-03',
    source: 'Global Desk',
    impact: 'Médio',
  },
  {
    id: 'n7',
    title: 'Discussão fiscal volta ao radar do mercado',
    summary: 'Propostas de ajuste fiscal geram leituras mistas para curva de juros.',
    category: 'Política econômica',
    date: '2026-04-02',
    source: 'Economia em Foco',
    impact: 'Alto',
  },
  {
    id: 'n8',
    title: 'Debêntures incentivadas atraem investidores',
    summary: 'Emissões com benefícios tributários seguem em destaque.',
    category: 'Renda fixa',
    date: '2026-04-02',
    source: 'Renda Fixa Hoje',
    impact: 'Baixo',
  },
];

export const initialChat: ChatMessage[] = [
  {
    id: 'c1',
    role: 'assistant',
    content: 'Olá. Sou o Operum e posso explicar seus investimentos com uma linguagem simples e direta.',
    createdAt: '09:00',
  },
];

export const metrics: DashboardMetric[] = [
  { label: 'Carteiras criadas', value: '4', variation: '+1 mês' },
  { label: 'Ativos monitorados', value: '28', variation: '+6%' },
  { label: 'Notícias relevantes', value: '12', variation: 'Hoje' },
  { label: 'Simulações', value: '47', variation: '+12%' },
  { label: 'Variação simulada', value: '+3,4%', variation: '30 dias' },
  { label: 'Tema em alta', value: 'Juros', variation: 'Sentimento neutro' },
];

export const preferencesDefault: UserPreferences = {
  topics: ['Inflação', 'Juros', 'Ações', 'Renda fixa'],
  compactMode: false,
  notifications: true,
};

export const lineSeries = [
  { month: 'Nov', value: 98 },
  { month: 'Dez', value: 101 },
  { month: 'Jan', value: 99 },
  { month: 'Fev', value: 106 },
  { month: 'Mar', value: 111 },
  { month: 'Abr', value: 114 },
];

export const barSeries = [
  { name: 'Renda fixa', value: 32 },
  { name: 'Ações BR', value: 22 },
  { name: 'Ações EUA', value: 18 },
  { name: 'Fundos', value: 15 },
  { name: 'Cripto', value: 13 },
];

export const pieSeries = [
  { name: 'Tesouro', value: 25 },
  { name: 'ETFs', value: 25 },
  { name: 'Ações', value: 20 },
  { name: 'Fundos', value: 15 },
  { name: 'Cripto', value: 15 },
];

export const areaSeries = [
  { week: 'W1', gain: 1.1 },
  { week: 'W2', gain: 0.8 },
  { week: 'W3', gain: 1.6 },
  { week: 'W4', gain: 1.2 },
  { week: 'W5', gain: 1.9 },
];

export const radarSeries = [
  { axis: 'Risco', carteira: 65, benchmark: 55 },
  { axis: 'Liquidez', carteira: 72, benchmark: 68 },
  { axis: 'Diversificação', carteira: 80, benchmark: 60 },
  { axis: 'Volatilidade', carteira: 58, benchmark: 70 },
  { axis: 'Exposição', carteira: 74, benchmark: 66 },
];

export const scenarioReturns = {
  conservador: 1.2,
  moderado: 2.8,
  agressivo: 4.9,
  'inflação alta': -0.7,
  'juros em queda': 3.4,
};
