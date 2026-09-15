import { mkdir, rm } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { chromium } from '@playwright/test';
import ffmpegPath from 'ffmpeg-static';

const frontendUrl = process.env.RECORD_FRONTEND_URL ?? 'http://localhost:5173';
const apiUrl = process.env.RECORD_API_URL ?? 'http://127.0.0.1:8001/api';
const outputDir = path.resolve('public/presentation/demos');
const videoDir = path.join(tmpdir(), 'operum-presentation-recordings');
const password = `Operum-${randomUUID()}!`;
const email = `pitch-${Date.now()}@operum.demo`;
let sessionCookie = '';
let examplePortfolioId = '';

const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function run(command, args) {
  return new Promise((resolve, reject) => {
    const process = spawn(command, args, { stdio: 'ignore' });
    process.on('error', reject);
    process.on('exit', (code) => code === 0 ? resolve() : reject(new Error(`${command} exited with ${code}`)));
  });
}

async function trimRecording(source, destination, startSeconds, durationSeconds) {
  if (!ffmpegPath) throw new Error('FFmpeg não está disponível para aparar a captura.');
  await rm(destination, { force: true });
  await run(ffmpegPath, [
    '-y', '-ss', String(startSeconds), '-i', source, '-t', String(durationSeconds), '-an',
    '-c:v', 'libvpx-vp9', '-crf', '34', '-b:v', '0', '-r', '24', destination,
  ]);
}

async function request(pathname, options = {}) {
  const response = await fetch(`${apiUrl}${pathname}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(sessionCookie ? { Cookie: sessionCookie } : {}), ...(options.headers ?? {}) },
  });
  if (!response.ok) throw new Error(`${pathname}: HTTP ${response.status} ${await response.text()}`);
  const setCookie = response.headers.get('set-cookie');
  if (setCookie?.includes('operum_session=')) {
    sessionCookie = setCookie.split(';', 1)[0];
  }
  return response.json();
}

async function createTemporaryAccount() {
  await request('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ name: 'Operum Pitch', email, password }),
  });
}

async function loadExamplePortfolio() {
  const portfolios = await request('/portfolios');
  const examplePortfolio = portfolios.find((portfolio) => portfolio.kind === 'example');
  if (!examplePortfolio) throw new Error('A conta temporária não recebeu a Carteira Exemplo.');
  examplePortfolioId = examplePortfolio.id;
}

async function prepareChatConversation() {
  const conversation = await request('/chat/conversations', {
    method: 'POST',
    body: JSON.stringify({ portfolio_id: examplePortfolioId, use_all_portfolios: false }),
  });
  await request(`/chat/conversations/${conversation.id}/messages`, {
    method: 'POST',
    body: JSON.stringify({
      content: 'Como está a composição da minha carteira ativa?',
      portfolio_id: examplePortfolioId,
      use_all_portfolios: false,
    }),
  });
}

async function removeTemporaryAccount() {
  if (!sessionCookie) return;
  await request('/auth/account', {
    method: 'DELETE',
    body: JSON.stringify({ current_password: password, confirmation: 'Excluir' }),
  }).catch(() => undefined);
}

async function waitForApplication(page) {
  await page.waitForLoadState('domcontentloaded');
  await page.locator('main').waitFor({ state: 'visible' });
  await pause(1_100);
}

async function record(browser, { file, route, title, action, settleMs = 8_500, clipStart = 0, clipSeconds = 10 }) {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
    colorScheme: 'light',
    recordVideo: { dir: videoDir, size: { width: 1280, height: 720 } },
  });
  const cookieUrl = new URL(apiUrl.replace(/\/api\/?$/, ''));
  const [, cookieValue = ''] = sessionCookie.split('=');
  if (cookieValue) {
    await context.addCookies([{
      name: 'operum_session',
      value: cookieValue,
      domain: cookieUrl.hostname,
      path: '/',
      httpOnly: true,
      secure: cookieUrl.protocol === 'https:',
      sameSite: 'Lax',
    }]);
  }
  const page = await context.newPage();
  page.setDefaultTimeout(5_000);
  await page.goto(`${frontendUrl}${route}`, { waitUntil: 'domcontentloaded' });
  await waitForApplication(page);
  try {
    await action(page);
  } catch (error) {
    console.warn(`Interação parcial em ${title}: ${error instanceof Error ? error.message : error}`);
  }
  await pause(settleMs);
  await page.screenshot({ path: path.join(outputDir, `${file}.png`) });
  const recording = page.video();
  await context.close();
  const destination = path.join(outputDir, `${file}.webm`);
  await trimRecording(await recording.path(), destination, clipStart, clipSeconds);
  console.log(`Capturado: ${title}`);
}

async function main() {
  await mkdir(outputDir, { recursive: true });
  await rm(videoDir, { recursive: true, force: true });
  await mkdir(videoDir, { recursive: true });
  await createTemporaryAccount();
  await loadExamplePortfolio();
  const browser = await chromium.launch({ headless: true });

  try {
    await record(browser, {
      file: 'visao-geral', route: '/app', title: 'Visão Geral', settleMs: 12_000,
      clipStart: 16, clipSeconds: 10,
      action: async (page) => {
        await page.getByText('Seu patrimônio em perspectiva.').waitFor({ timeout: 5_000 });
        await page.getByText('Valor atual').first().waitFor({ timeout: 12_000 });
      },
    });
    await record(browser, {
      file: 'carteiras', route: '/app/carteiras', title: 'Carteiras',
      clipStart: 8, clipSeconds: 10,
      action: async (page) => {
        await page.getByRole('button', { name: 'Abrir carteira' }).waitFor({ timeout: 5_000 });
        await pause(900);
        await page.getByRole('button', { name: 'Abrir carteira' }).click();
        await page.getByText('Ambiente demonstrativo').waitFor({ timeout: 5_000 });
      },
    });
    await record(browser, {
      file: 'analise-ativo', route: '/app/carteiras', title: 'Análise de ativo',
      clipStart: 14, clipSeconds: 11,
      action: async (page) => {
        const openPortfolio = page.getByRole('button', { name: 'Abrir carteira' });
        await openPortfolio.waitFor({ timeout: 5_000 });
        await openPortfolio.click();
        await page.getByText('Ambiente demonstrativo').waitFor({ timeout: 5_000 });
        const targetRow = page.locator('.portfolio-position-row').filter({ hasText: 'ITUB4' });
        await targetRow.locator('td[data-label="Análise"] button').click({ timeout: 5_000 });
        await page.getByText(/Situação atual/i).last().waitFor({ timeout: 12_000 });
        await page.getByText(/Situação atual/i).last().scrollIntoViewIfNeeded();
      },
    });
    await record(browser, {
      file: 'noticias', route: '/app/noticias', title: 'Notícias',
      clipStart: 5, clipSeconds: 10,
      action: async (page) => {
        await page.getByText('Inteligência de mercado').waitFor({ timeout: 5_000 });
        await pause(1_000);
        await page.getByRole('button', { name: 'Mercado', exact: true }).click();
      },
    });
    await prepareChatConversation();
    await record(browser, {
      file: 'chat', route: '/app/chat', title: 'Chat',
      clipStart: 14, clipSeconds: 10,
      action: async (page) => {
        await page.getByText('O que você quer entender?').waitFor({ timeout: 5_000 });
        await page.locator('.chat-message.is-assistant:not(.chat-thinking)').last().waitFor({ timeout: 12_000 });
        await page.locator('.chat-messages').evaluate((element) => element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' }));
      },
    });
  } finally {
    await browser.close();
    await removeTemporaryAccount();
    await rm(videoDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
