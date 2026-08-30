import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildCurrencySummaries,
  consolidateHistoriesByCurrency,
} from '../src/utils/dashboardOverview.ts';

const portfolios = [
  { id: 'br-1', base_currency: 'BRL' },
  { id: 'br-2', base_currency: 'BRL' },
  { id: 'us-1', base_currency: 'USD' },
];

test('separates financial totals by base currency and reports partial data', () => {
  const summaries = buildCurrencySummaries(portfolios, new Map([
    ['br-1', {
      positions: [
        { ticker: 'PETR4', asset_class: 'BR_STOCK', quantity: 2, avg_price: 40, total_value: 100, unrealized_pnl: 20, unrealized_pnl_pct: 25, weight_pct: 100 },
        { ticker: 'ABEV3', asset_class: 'BR_STOCK', quantity: 1, avg_price: 10, total_value: null, unrealized_pnl: null, unrealized_pnl_pct: null, weight_pct: null },
      ],
    }],
    ['br-2', {
      positions: [
        { ticker: 'HGLG11', asset_class: 'FII', quantity: 1, avg_price: 40, total_value: 50, unrealized_pnl: 10, unrealized_pnl_pct: 25, weight_pct: 100 },
      ],
    }],
    ['us-1', {
      positions: [
        { ticker: 'AAPL', asset_class: 'US_STOCK', quantity: 1, avg_price: null, total_value: 200, unrealized_pnl: null, unrealized_pnl_pct: null, weight_pct: 100 },
      ],
    }],
  ]));

  assert.deepEqual(summaries.map((summary) => summary.currency), ['BRL', 'USD']);
  assert.deepEqual(summaries[0], {
    currency: 'BRL',
    portfolioIds: ['br-1', 'br-2'],
    currentValue: 150,
    investedValue: 130,
    unrealizedPnl: 30,
    unrealizedPnlPct: 25,
    positionCount: 3,
    classCount: 2,
    missingQuotes: 1,
    missingCosts: 0,
    allocation: [
      { assetClass: 'BR_STOCK', value: 100, percent: 66.66666666666666 },
      { assetClass: 'FII', value: 50, percent: 33.33333333333333 },
    ],
    ranking: [
      { ticker: 'HGLG11', assetClass: 'FII', value: 50, pnl: 10, pnlPct: 25, percent: 33.33333333333333 },
      { ticker: 'PETR4', assetClass: 'BR_STOCK', value: 100, pnl: 20, pnlPct: 25, percent: 66.66666666666666 },
    ],
  });
  assert.equal(summaries[1].currentValue, 200);
  assert.equal(summaries[1].investedValue, null);
  assert.equal(summaries[1].unrealizedPnlPct, null);
  assert.equal(summaries[1].missingCosts, 1);
});

test('consolidates histories by currency using the last known value on union dates', () => {
  const histories = new Map([
    ['br-1', { points: [
      { date: '2026-01-01', market_value: 100, invested_value: 80 },
      { date: '2026-01-03', market_value: 120, invested_value: 80 },
    ] }],
    ['br-2', { points: [
      { date: '2026-01-02', market_value: 50, invested_value: 40 },
      { date: '2026-01-03', market_value: 55, invested_value: 40 },
    ] }],
    ['us-1', { points: [
      { date: '2026-01-01', market_value: 200, invested_value: 190 },
    ] }],
  ]);

  const groups = consolidateHistoriesByCurrency(portfolios, histories);

  assert.deepEqual(groups, [
    {
      currency: 'BRL',
      points: [
        { date: '2026-01-01', marketValue: 100, investedValue: 80 },
        { date: '2026-01-02', marketValue: 150, investedValue: 120 },
        { date: '2026-01-03', marketValue: 175, investedValue: 120 },
      ],
    },
    {
      currency: 'USD',
      points: [
        { date: '2026-01-01', marketValue: 200, investedValue: 190 },
      ],
    },
  ]);
});

test('counts and ranks the same ticker only once in a consolidated currency group', () => {
  const summaries = buildCurrencySummaries(portfolios.slice(0, 2), new Map([
    ['br-1', { positions: [
      { ticker: 'PETR4', asset_class: 'BR_STOCK', quantity: 1, avg_price: 40, total_value: 50, unrealized_pnl: 10, unrealized_pnl_pct: 25, weight_pct: 100 },
    ] }],
    ['br-2', { positions: [
      { ticker: 'PETR4', asset_class: 'BR_STOCK', quantity: 2, avg_price: 40, total_value: 100, unrealized_pnl: 20, unrealized_pnl_pct: 25, weight_pct: 100 },
    ] }],
  ]));

  assert.equal(summaries[0].positionCount, 1);
  assert.deepEqual(summaries[0].ranking, [
    { ticker: 'PETR4', assetClass: 'BR_STOCK', value: 150, pnl: 30, pnlPct: 25, percent: 100 },
  ]);
});

test('keeps BDR allocation separate from direct US stocks', () => {
  const summaries = buildCurrencySummaries([{ id: 'br-1', base_currency: 'BRL' }], new Map([
    ['br-1', { positions: [
      { ticker: 'AAPL34', asset_class: 'US_STOCK', quantity: 1, avg_price: 50, total_value: 60, unrealized_pnl: 10, unrealized_pnl_pct: 20, weight_pct: 60 },
      { ticker: 'AAPL', asset_class: 'US_STOCK', quantity: 1, avg_price: 30, total_value: 40, unrealized_pnl: 10, unrealized_pnl_pct: 33.33, weight_pct: 40 },
    ] }],
  ]));

  assert.deepEqual(summaries[0].allocation, [
    { assetClass: 'BDR', value: 60, percent: 60 },
    { assetClass: 'US_STOCK', value: 40, percent: 40 },
  ]);
});

test('carries the last non-null market and invested values across partial history points', () => {
  const groups = consolidateHistoriesByCurrency(portfolios.slice(0, 2), new Map([
    ['br-1', { points: [
      { date: '2026-01-01', market_value: 100, invested_value: 80 },
      { date: '2026-01-02', market_value: null, invested_value: null },
   ] }],
    ['br-2', { points: [
      { date: '2026-01-03', market_value: 50, invested_value: 40 },
   ] }],
  ]));

  assert.deepEqual(groups[0].points.at(-1), {
    date: '2026-01-03',
    marketValue: 150,
    investedValue: 120,
  });
});

test('separates positions by their effective currency even inside one portfolio', () => {
  const summaries = buildCurrencySummaries([{ id: 'mixed', base_currency: 'BRL' }], new Map([
    ['mixed', { positions: [
      { ticker: 'PETR4', asset_class: 'BR_STOCK', currency: 'BRL', quantity: 1, avg_price: 40, total_value: 50, unrealized_pnl: 10, unrealized_pnl_pct: 25, weight_pct: 50 },
      { ticker: 'AAPL', asset_class: 'US_STOCK', currency: 'USD', quantity: 1, avg_price: 180, total_value: 200, unrealized_pnl: 20, unrealized_pnl_pct: 11.11, weight_pct: 50 },
    ] }],
  ]));

  assert.deepEqual(summaries.map((summary) => [summary.currency, summary.currentValue]), [
    ['BRL', 50],
    ['USD', 200],
  ]);
});

test('uses null instead of zero when no current value or acquisition cost is known', () => {
  const summaries = buildCurrencySummaries([{ id: 'unknown', base_currency: 'BRL' }], new Map([
    ['unknown', { positions: [
      { ticker: 'UNKNOWN', asset_class: 'BR_STOCK', currency: 'BRL', quantity: 1, avg_price: null, total_value: null, unrealized_pnl: null, unrealized_pnl_pct: null, weight_pct: null },
    ] }],
  ]));

  assert.equal(summaries[0].currentValue, null);
  assert.equal(summaries[0].investedValue, null);
  assert.equal(summaries[0].unrealizedPnl, null);
  assert.equal(summaries[0].unrealizedPnlPct, null);
});

test('groups history by the currency declared by each history response', () => {
  const groups = consolidateHistoriesByCurrency(portfolios.slice(0, 2), new Map([
    ['br-1', { currency: 'USD', points: [{ date: '2026-01-01', market_value: 100, invested_value: 90 }] }],
    ['br-2', { currency: 'BRL', points: [{ date: '2026-01-01', market_value: 200, invested_value: 180 }] }],
  ]));

  assert.deepEqual(groups.map((group) => [group.currency, group.points[0].marketValue]), [
    ['USD', 100],
    ['BRL', 200],
  ]);
});
