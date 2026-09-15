import test from 'node:test';
import assert from 'node:assert/strict';
import { chromium, expect } from '@playwright/test';
import { createServer } from 'vite';

// A real browser renders the component; API responses are controlled and no account is created.
test('analysis loads only selected horizons, ignores stale responses and refreshes provisional results', async () => {
  const server = await createServer({
    server: { host: '127.0.0.1', port: 0, open: false },
    plugins: [{ name: 'analysis-test-harness', configureServer(server) {
      server.middlewares.use('/__analysis_test', async (_req, res) => {
        const html = await server.transformIndexHtml('/__analysis_test', `
          <div id="root"></div><script type="module">
          import React from 'react';
          import ReactDOM from 'react-dom/client';
          import { PortfolioAnalysisAI } from '/src/components/PortfolioAnalysisAI.tsx';
          function Harness() {
            const ref = React.useRef();
            const [id, setId] = React.useState('p1');
            return React.createElement(React.Fragment, null,
              React.createElement('button', {onClick: () => ref.current.generate()}, 'Refresh'),
              React.createElement('button', {onClick: () => setId('p2')}, 'Switch portfolio'),
              React.createElement(PortfolioAnalysisAI, {ref, portfolioId: id}));
          }
          ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(Harness));
          </script>`);
        res.setHeader('Content-Type', 'text/html');
        res.end(html);
      });
    } }],
  });
  let browser;
  try {
    await server.listen();
    const address = server.httpServer.address();
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    const requests = [];
    const pending = [];
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('**/api/models/opinion/**', async (route) => {
      requests.push(route.request().url());
      pending.push(route);
    });
    const respond = async (route, headline, provisional = false) => route.fulfill({ json: {
      score: 0.7, headline, composition_grade: '7 / 10', composition_summary: headline,
      conclusion: 'Conclusão', final_diagnosis: 'Diagnóstico', overlaps: [], source_groups: [],
      forecast_availability: { status: provisional ? 'partial' : 'ready', items: provisional
        ? [{ ticker: 'PETR4', missing_horizons: [21], preparation: 'pending' }] : [] },
    } });
    const nextRequest = async () => {
      await expect.poll(() => pending.length).toBeGreaterThan(0);
      return pending.shift();
    };
    await page.goto(`http://127.0.0.1:${address.port}/__analysis_test`);
    try {
      await expect(page.getByRole('button', { name: 'Refresh', exact: true })).toBeVisible({ timeout: 10000 });
    } catch (error) {
      throw new Error(`Harness failed: ${errors.join('; ') || error.message}`);
    }
    await page.getByRole('button', { name: 'Refresh', exact: true }).click();
    const first = await nextRequest();
    await page.getByRole('button', { name: 'Refresh', exact: true }).click();
    await respond(first, 'Resultado inicial', true);
    await expect(page.getByText('Resultado inicial', { exact: true }).first()).toBeVisible();
    await expect(page.getByRole('status')).toContainText('Cobertura de previsões incompleta');
    // Allow effects to run and prove there are no unsolicited horizon requests.
    await page.waitForTimeout(200);
    assert.equal(requests.length, 1);

    await page.getByRole('button', { name: '1 mês', exact: true }).click();
    const slow = await nextRequest();
    await page.getByRole('button', { name: '2 meses', exact: true }).click();
    const fast = await nextRequest();
    await respond(fast, 'Resultado dois meses');
    await respond(slow, 'Resposta atrasada');
    await expect(page.getByText('Resultado dois meses', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Resposta atrasada', { exact: true })).toHaveCount(0);

    await page.getByRole('button', { name: 'Refresh', exact: true }).click();
    await respond(await nextRequest(), 'Resultado atualizado');
    await expect(page.getByText('Resultado atualizado', { exact: true }).first()).toBeVisible();
    await expect(page.getByRole('status')).toHaveCount(0);
    assert.equal(requests.length, 4);

    await page.getByRole('button', { name: 'Refresh', exact: true }).click();
    const previousPortfolio = await nextRequest();
    await page.getByRole('button', { name: 'Switch portfolio', exact: true }).click();
    await page.getByRole('button', { name: 'Refresh', exact: true }).click();
    const currentPortfolio = await nextRequest();
    assert.match(currentPortfolio.request().url(), /opinion\/p2/);
    await respond(currentPortfolio, 'Carteira atual');
    await respond(previousPortfolio, 'Carteira anterior');
    await expect(page.getByText('Carteira atual', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Carteira anterior', { exact: true })).toHaveCount(0);
    assert.deepEqual(errors, []);
  } finally {
    await browser?.close();
    await server.close();
  }
});
