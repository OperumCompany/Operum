import { useEffect, useMemo, useState } from 'react';
import { Newspaper, ExternalLink, X, RefreshCw } from 'lucide-react';
import { Card, Input } from '../components/UI';
import { NewsItem } from '../types';
import api from '../utils/api';

function getImpactLabel(score: number): string {
  if (score >= 0.7) return 'Alto';
  if (score >= 0.4) return 'Medio';
  return 'Baixo';
}

function getImpactColor(score: number): string {
  if (score >= 0.7) return 'text-red-600 bg-red-50';
  if (score >= 0.4) return 'text-amber-600 bg-amber-50';
  return 'text-green-600 bg-green-50';
}

function getSentimentLabel(score: number): string {
  if (score > 0.2) return 'Positivo';
  if (score < -0.2) return 'Negativo';
  return 'Neutro';
}

function getSentimentColor(score: number): string {
  if (score > 0.2) return 'text-green-600 bg-green-50';
  if (score < -0.2) return 'text-red-600 bg-red-50';
  return 'text-gray-600 bg-gray-100';
}

type NewsResponse = {
  items: NewsItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

const PAGE_SIZE = 30;

export function NewsPage() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [selectedAsset, setSelectedAsset] = useState<string | null>(null);
  const [selectedSentiment, setSelectedSentiment] = useState<string | null>(null);
  const [selectedImpact, setSelectedImpact] = useState<string | null>(null);
  const [modalNews, setModalNews] = useState<NewsItem | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [query]);

  useEffect(() => {
    setPage(1);
  }, [selectedAsset, selectedSentiment, selectedImpact]);

  function fetchNews(targetPage = page) {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set('page_size', String(PAGE_SIZE));
    params.set('page', String(targetPage));
    if (debouncedQuery) params.set('q', debouncedQuery);
    if (selectedAsset) params.set('ticker', selectedAsset);
    if (selectedSentiment) params.set('sentiment', selectedSentiment);
    if (selectedImpact) params.set('impact', selectedImpact);

    api.get<NewsResponse>(`/news?${params.toString()}`)
      .then((data) => {
        setNews(data.items);
        setTotal(data.total);
        setPage(data.page);
        setTotalPages(Math.max(1, data.total_pages || 1));
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Erro ao carregar noticias');
        setNews([]);
        setTotal(0);
        setTotalPages(1);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchNews(page);
  }, [page, debouncedQuery, selectedAsset, selectedSentiment, selectedImpact]);

  const availableAssets = useMemo(() => {
    const assets = new Set<string>();
    news.forEach((n) => n.mentioned_assets.forEach((a) => assets.add(a)));
    return Array.from(assets).sort();
  }, [news]);

  const pageNumbers = useMemo(() => {
    const numbers: number[] = [];
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    for (let current = start; current <= end; current += 1) {
      numbers.push(current);
    }
    return numbers;
  }, [page, totalPages]);

  const summaryParagraphs = modalNews
    ? (modalNews.summary || modalNews.content_preview)
        .split(/\n\s*\n/)
        .map((part) => part.trim())
        .filter(Boolean)
    : [];

  return (
    <div className="space-y-4">
      <section className="rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(61,77,156,0.1)_0%,rgba(255,255,255,0.96)_52%,rgba(199,85,155,0.08)_100%)] p-6 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-[var(--text-main)]">
              <Newspaper size={16} />
              O que pode mexer com sua carteira
            </div>
            <h2 className="mt-4 text-3xl font-bold">Noticias de mercado com leitura mais clara</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Filtre por ativo, sentimento ou impacto. Clique em uma noticia para ver detalhes.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-[var(--text-muted)]">{total} noticias</span>
            <button
              onClick={() => fetchNews(page)}
              className="rounded-full p-2 text-[var(--text-muted)] hover:bg-gray-100"
              title="Atualizar noticias"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>
      </section>

      <Card title="Filtrar noticias">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <Input
            placeholder="Buscar palavra-chave"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="md:max-w-xs"
          />
          <select
            value={selectedAsset ?? ''}
            onChange={(e) => setSelectedAsset(e.target.value || null)}
            className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm"
          >
            <option value="">Todos os ativos</option>
            {availableAssets.map((asset) => (
              <option key={asset} value={asset}>{asset}</option>
            ))}
          </select>
          <select
            value={selectedSentiment ?? ''}
            onChange={(e) => setSelectedSentiment(e.target.value || null)}
            className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm"
          >
            <option value="">Todos sentimentos</option>
            <option value="positive">Positivo</option>
            <option value="negative">Negativo</option>
            <option value="neutral">Neutro</option>
          </select>
          <select
            value={selectedImpact ?? ''}
            onChange={(e) => setSelectedImpact(e.target.value || null)}
            className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm"
          >
            <option value="">Todos impactos</option>
            <option value="high">Alto</option>
            <option value="medium">Medio</option>
            <option value="low">Baixo</option>
          </select>
        </div>
      </Card>

      {loading && (
        <Card>
          <p className="py-8 text-center text-sm text-[var(--text-muted)]">Carregando noticias...</p>
        </Card>
      )}

      {!loading && error && (
        <Card>
          <p className="py-8 text-center text-sm text-[var(--danger-text)]">{error}</p>
        </Card>
      )}

      {!loading && !error && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {news.map((item) => (
              <article
                key={item.id}
                className="cursor-pointer rounded-[24px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4 transition hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(37,37,37,0.08)]"
                onClick={() => setModalNews(item)}
              >
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="font-semibold text-[var(--brand)]">{item.source_name}</span>
                  <span className="text-[var(--text-muted)]">•</span>
                  <span className="text-[var(--text-muted)]">
                    {new Date(item.published_at).toLocaleDateString('pt-BR')}
                  </span>
                </div>
                <h3 className="mt-2 text-base font-semibold text-[var(--text-main)]">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-[var(--text-muted)] line-clamp-3">{item.content_preview}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.mentioned_assets.slice(0, 3).map((asset) => (
                    <span key={asset} className="rounded-full bg-[var(--accent-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--accent)]">
                      {asset}
                    </span>
                  ))}
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${getImpactColor(item.impact_score)}`}>
                    Impacto {getImpactLabel(item.impact_score)}
                  </span>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${getSentimentColor(item.sentiment_score)}`}>
                    {getSentimentLabel(item.sentiment_score)}
                  </span>
                </div>
              </article>
            ))}
          </div>

          {news.length === 0 && (
            <Card>
              <p className="py-8 text-center text-sm text-[var(--text-muted)]">Nenhuma noticia encontrada com esses filtros.</p>
            </Card>
          )}

          {totalPages > 1 && (
            <Card>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-[var(--text-muted)]">Pagina {page} de {totalPages}</p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                    disabled={page === 1}
                    className="rounded-2xl border border-[var(--border-soft)] px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    ←
                  </button>
                  {pageNumbers.map((number) => (
                    <button
                      key={number}
                      type="button"
                      onClick={() => setPage(number)}
                      className={`rounded-2xl px-3 py-2 text-sm font-semibold ${number === page ? 'bg-[var(--brand)] text-white' : 'border border-[var(--border-soft)] text-[var(--text-main)]'}`}
                    >
                      {number}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                    disabled={page === totalPages}
                    className="rounded-2xl border border-[var(--border-soft)] px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    →
                  </button>
                </div>
              </div>
            </Card>
          )}
        </>
      )}

      {modalNews && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setModalNews(null)}>
          <div
            className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-[32px] bg-white p-6 shadow-2xl sm:p-8"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-semibold text-[var(--brand)]">{modalNews.source_name}</p>
                <p className="text-xs text-[var(--text-muted)]">
                  {new Date(modalNews.published_at).toLocaleString('pt-BR')}
                </p>
              </div>
              <button onClick={() => setModalNews(null)} className="rounded-full p-1 hover:bg-gray-100">
                <X size={20} />
              </button>
            </div>

            <h2 className="mt-4 text-2xl font-bold text-[var(--text-main)]">{modalNews.title}</h2>
            {modalNews.subtitle && (
              <p className="mt-2 text-base text-[var(--text-muted)]">{modalNews.subtitle}</p>
            )}

            <p className="mt-4 text-sm leading-7 text-[var(--text-main)]">{modalNews.content_preview}</p>

            <div className="mt-6">
              <h3 className="text-sm font-semibold text-[var(--text-muted)]">Resumo</h3>
              <div className="mt-2 space-y-3">
                {summaryParagraphs.map((paragraph) => (
                  <p key={paragraph} className="text-sm leading-7 text-[var(--text-main)]">
                    {paragraph}
                  </p>
                ))}
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${getImpactColor(modalNews.impact_score)}`}>
                Impacto: {getImpactLabel(modalNews.impact_score)} ({modalNews.impact_score.toFixed(2)})
              </span>
              <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${getSentimentColor(modalNews.sentiment_score)}`}>
                Sentimento: {getSentimentLabel(modalNews.sentiment_score)} ({modalNews.sentiment_score.toFixed(2)})
              </span>
              <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--accent)]">
                Relevancia: {(modalNews.relevance_score * 100).toFixed(0)}%
              </span>
            </div>

            {modalNews.mentioned_assets.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-semibold text-[var(--text-main)]">Ativos mencionados:</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {modalNews.mentioned_assets.map((asset) => (
                    <span key={asset} className="rounded-full bg-[var(--accent-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--accent)]">
                      {asset}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-6 flex gap-3">
              <a
                href={modalNews.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-2xl bg-[var(--brand)] px-5 py-2.5 text-sm font-semibold text-white"
              >
                Abrir original
                <ExternalLink size={14} />
              </a>
              <button
                onClick={() => setModalNews(null)}
                className="rounded-2xl border border-[var(--border-soft)] px-5 py-2.5 text-sm font-semibold text-[var(--text-main)]"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
