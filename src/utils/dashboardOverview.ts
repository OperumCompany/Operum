export type DashboardPortfolioRef = {
  id: string;
  base_currency: string;
};

export type DashboardPricePosition = {
  ticker: string;
  asset_class: string;
  currency?: string;
  quantity: number;
  avg_price: number | null;
  total_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  weight_pct: number | null;
};

export type DashboardPrices = {
  positions: DashboardPricePosition[];
};

export type DashboardRankingItem = {
  ticker: string;
  assetClass: string;
  value: number;
  pnl: number;
  pnlPct: number;
  percent: number;
};

export type DashboardCurrencySummary = {
  currency: string;
  portfolioIds: string[];
  currentValue: number | null;
  investedValue: number | null;
  unrealizedPnl: number | null;
  unrealizedPnlPct: number | null;
  positionCount: number;
  classCount: number;
  missingQuotes: number;
  missingCosts: number;
  allocation: Array<{ assetClass: string; value: number; percent: number }>;
  ranking: DashboardRankingItem[];
};

export type DashboardHistoryPoint = {
  date: string;
  market_value: number | null;
  invested_value: number | null;
};

export type DashboardHistory = {
  currency?: string;
  points: DashboardHistoryPoint[];
};

export type ConsolidatedHistoryGroup = {
  currency: string;
  points: Array<{ date: string; marketValue: number | null; investedValue: number | null }>;
};

function displayAssetClass(position: Pick<DashboardPricePosition, 'asset_class' | 'ticker'>) {
  return position.asset_class === 'US_STOCK' && /\d{2}$/.test(position.ticker) ? 'BDR' : position.asset_class;
}

export function buildCurrencySummaries(
  portfolios: DashboardPortfolioRef[],
  pricesByPortfolio: ReadonlyMap<string, DashboardPrices>,
): DashboardCurrencySummary[] {
  const buckets = new Map<string, { portfolioIds: Set<string>; positions: DashboardPricePosition[] }>();
  for (const portfolio of portfolios) {
    for (const position of pricesByPortfolio.get(portfolio.id)?.positions ?? []) {
      const currency = position.currency || portfolio.base_currency || 'BRL';
      const bucket = buckets.get(currency) ?? { portfolioIds: new Set<string>(), positions: [] };
      bucket.portfolioIds.add(portfolio.id);
      bucket.positions.push(position);
      buckets.set(currency, bucket);
    }
  }

  return Array.from(buckets.entries()).map(([currency, bucket]) => {
    const positions = bucket.positions;
    const knownValues = positions.filter((position) => position.total_value != null);
    const knownCosts = positions.filter((position) => position.avg_price != null);
    const currentValue = knownValues.length
      ? knownValues.reduce((sum, position) => sum + (position.total_value ?? 0), 0)
      : null;
    const investedValue = knownCosts.length
      ? knownCosts.reduce((sum, position) => sum + (position.avg_price ?? 0) * position.quantity, 0)
      : null;
    const positionsWithPnl = positions.filter((position) => position.unrealized_pnl != null);
    const unrealizedPnl = positionsWithPnl.length
      ? positionsWithPnl.reduce((sum, position) => sum + (position.unrealized_pnl ?? 0), 0)
      : null;
    const pnlCostBasis = positionsWithPnl.reduce(
      (sum, position) => sum + (position.avg_price == null ? 0 : position.avg_price * position.quantity),
      0,
    );

    const allocationTotals = new Map<string, number>();
    const rankingTotals = new Map<string, { ticker: string; assetClass: string; value: number; pnl: number; cost: number }>();
    for (const position of positions) {
      const assetClass = displayAssetClass(position);
      if (position.total_value != null) {
        allocationTotals.set(assetClass, (allocationTotals.get(assetClass) ?? 0) + position.total_value);
      }
      if (position.total_value == null || position.unrealized_pnl == null || position.avg_price == null) continue;
      const key = `${assetClass}:${position.ticker}`;
      const current = rankingTotals.get(key) ?? {
        ticker: position.ticker,
        assetClass,
        value: 0,
        pnl: 0,
        cost: 0,
      };
      current.value += position.total_value;
      current.pnl += position.unrealized_pnl;
      current.cost += position.avg_price * position.quantity;
      rankingTotals.set(key, current);
    }

    const allocation = Array.from(allocationTotals.entries())
      .map(([assetClass, value]) => ({ assetClass, value, percent: currentValue ? value / currentValue * 100 : 0 }))
      .sort((a, b) => b.value - a.value || a.assetClass.localeCompare(b.assetClass));
    const ranking = Array.from(rankingTotals.values())
      .map((item) => ({
        ticker: item.ticker,
        assetClass: item.assetClass,
        value: item.value,
        pnl: item.pnl,
        pnlPct: item.cost ? item.pnl / item.cost * 100 : 0,
        percent: currentValue ? item.value / currentValue * 100 : 0,
      }))
      .sort((a, b) => b.pnlPct - a.pnlPct || a.ticker.localeCompare(b.ticker));

    return {
      currency,
      portfolioIds: Array.from(bucket.portfolioIds),
      currentValue,
      investedValue,
      unrealizedPnl,
      unrealizedPnlPct: unrealizedPnl != null && pnlCostBasis > 0 ? unrealizedPnl / pnlCostBasis * 100 : null,
      positionCount: new Set(positions.map((position) => `${displayAssetClass(position)}:${position.ticker}`)).size,
      classCount: new Set(positions.map(displayAssetClass)).size,
      missingQuotes: positions.filter((position) => position.total_value == null).length,
      missingCosts: positions.filter((position) => position.avg_price == null).length,
      allocation,
      ranking,
    };
  });
}

export function consolidateHistoriesByCurrency(
  portfolios: DashboardPortfolioRef[],
  historiesByPortfolio: ReadonlyMap<string, DashboardHistory>,
): ConsolidatedHistoryGroup[] {
  const groups = new Map<string, DashboardHistoryPoint[][]>();
  for (const portfolio of portfolios) {
    const history = historiesByPortfolio.get(portfolio.id);
    if (!history?.points.length) continue;
    const currency = history.currency || portfolio.base_currency || 'BRL';
    groups.set(currency, [...(groups.get(currency) ?? []), history.points]);
  }

  return Array.from(groups.entries()).map(([currency, groupHistories]) => {
    const histories = groupHistories.map((points) => [...points].sort((a, b) => a.date.localeCompare(b.date)));
    const dates = Array.from(new Set(histories.flatMap((points) => points.map((point) => point.date)))).sort();

    const points = dates.map((date) => {
      let marketValue = 0;
      let investedValue = 0;
      let hasMarketValue = false;
      let hasInvestedValue = false;
      for (const history of histories) {
        let latestMarketValue: number | null = null;
        let latestInvestedValue: number | null = null;
        for (let index = history.length - 1; index >= 0; index -= 1) {
          const point = history[index];
          if (point.date > date) continue;
          if (latestMarketValue == null && point.market_value != null) latestMarketValue = point.market_value;
          if (latestInvestedValue == null && point.invested_value != null) latestInvestedValue = point.invested_value;
          if (latestMarketValue != null && latestInvestedValue != null) break;
        }
        if (latestMarketValue != null) {
          marketValue += latestMarketValue;
          hasMarketValue = true;
        }
        if (latestInvestedValue != null) {
          investedValue += latestInvestedValue;
          hasInvestedValue = true;
        }
      }
      return {
        date,
        marketValue: hasMarketValue ? marketValue : null,
        investedValue: hasInvestedValue ? investedValue : null,
      };
    });

    return { currency, points };
  });
}
