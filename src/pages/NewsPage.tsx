import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, ExternalLink, Newspaper, RefreshCw, Search, X } from 'lucide-react';
import { Input } from '../components/UI';
import { NewsItem } from '../types';
import api from '../utils/api';

type NewsResponse = {
  items: NewsItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  search_mode_used: 'chronological' | 'hybrid' | 'keyword' | 'semantic';
  semantic_available: boolean;
};

const PAGE_SIZE = 20;
const QUICK_TOPICS = ['Mercado', 'Economia', 'Tecnologia'] as const;
const FALLBACK_TOPICS = ['Mercado de Capitais', 'Macroeconomia', 'Financeiro', 'Criptomoedas', 'Renda Fixa', 'Petróleo e Gás', 'Energia Elétrica'];

function formatPublishedAt(value: string): string {
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function getTopic(item: NewsItem): string {
  return item.mentioned_sectors[0] || 'Mercado';
}

export function NewsPage() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [selectedAsset, setSelectedAsset] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [modalNews, setModalNews] = useState<NewsItem | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [searchModeUsed, setSearchModeUsed] = useState<NewsResponse['search_mode_used']>('chronological');
  const [semanticAvailable, setSemanticAvailable] = useState(false);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [query]);

  useEffect(() => setPage(1), [selectedAsset, selectedTopic]);

  function fetchNews(targetPage = page) {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(targetPage) });
    if (debouncedQuery) {
      params.set('q', debouncedQuery);
      params.set('search_mode', 'hybrid');
    }
    if (selectedAsset) params.set('ticker', selectedAsset);
    if (selectedTopic) params.set('sector', selectedTopic);

    api.get<NewsResponse>(`/news?${params.toString()}`)
      .then((data) => {
        setNews(data.items);
        setTotal(data.total);
        setPage(data.page);
        setTotalPages(Math.max(1, data.total_pages || 1));
        setSearchModeUsed(data.search_mode_used || 'chronological');
        setSemanticAvailable(Boolean(data.semantic_available));
      })
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : 'Erro ao carregar notícias');
        setNews([]);
        setTotal(0);
        setTotalPages(1);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchNews(page);
  }, [page, debouncedQuery, selectedAsset, selectedTopic]);

  const availableAssets = useMemo(() => {
    const assets = new Set<string>();
    news.forEach((item) => item.mentioned_assets.forEach((asset) => assets.add(asset)));
    return Array.from(assets).sort();
  }, [news]);
  const additionalTopics = useMemo(() => {
    const topics = new Set(FALLBACK_TOPICS);
    news.forEach((item) => item.mentioned_sectors.forEach((topic) => topics.add(topic)));
    QUICK_TOPICS.forEach((topic) => topics.delete(topic));
    return Array.from(topics).sort((left, right) => left.localeCompare(right, 'pt-BR'));
  }, [news]);
  const pageNumbers = useMemo(() => {
    const numbers: number[] = [];
    for (let current = Math.max(1, page - 2); current <= Math.min(totalPages, page + 2); current += 1) numbers.push(current);
    return numbers;
  }, [page, totalPages]);
  const summaryParagraphs = modalNews
    ? (modalNews.summary || modalNews.content_preview).split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean)
    : [];
  const selectedAdditionalTopic = selectedTopic && !QUICK_TOPICS.includes(selectedTopic as typeof QUICK_TOPICS[number]) ? selectedTopic : '';

  return (
    <div className="space-y-5">
      <section className="rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(61,77,156,0.1)_0%,var(--bg-surface-strong)_52%,rgba(199,85,155,0.08)_100%)] p-5 shadow-[var(--shadow-card)] sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--brand)]"><Newspaper size={16} /> Notícias e contexto</div>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-[var(--text-main)] sm:text-4xl">Inteligência de mercado</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-muted)]">Acompanhe os fatos que ajudam a entender o mercado e os seus investimentos.</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-[var(--text-muted)]">{total} notícias</span>
            <button type="button" onClick={() => fetchNews(page)} className="rounded-full border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-2.5 text-[var(--text-muted)] transition hover:text-[var(--brand)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)]" title="Atualizar notícias" aria-label="Atualizar notícias"><RefreshCw size={16} className={loading ? 'animate-spin' : ''} /></button>
          </div>
        </div>

        <div className="mt-6 grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
          <div className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" size={17} />
            <Input placeholder="Buscar por assunto, ativo ou contexto" value={query} onChange={(event) => setQuery(event.target.value)} className="w-full !pl-11" aria-label="Buscar notícias" />
          </div>
          <div className="flex items-center gap-2 overflow-x-auto pb-1 [scrollbar-width:none] xl:justify-end">
            <TopicButton active={selectedTopic === null} onClick={() => setSelectedTopic(null)}>Todos</TopicButton>
            {QUICK_TOPICS.map((topic) => <TopicButton key={topic} active={selectedTopic === topic} onClick={() => setSelectedTopic(topic)}>{topic}</TopicButton>)}
          </div>
        </div>

        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
          <select value={selectedAsset ?? ''} onChange={(event) => setSelectedAsset(event.target.value || null)} className="min-h-11 rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 text-sm text-[var(--text-main)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)] sm:w-52" aria-label="Filtrar por ativo">
            <option value="">Todos os ativos</option>
            {availableAssets.map((asset) => <option key={asset} value={asset}>{asset}</option>)}
          </select>
          <select value={selectedAdditionalTopic} onChange={(event) => setSelectedTopic(event.target.value || null)} className="min-h-11 rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 text-sm text-[var(--text-main)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)] sm:w-56" aria-label="Filtrar por mais temas">
            <option value="">Mais temas</option>
            {additionalTopics.map((topic) => <option key={topic} value={topic}>{topic}</option>)}
          </select>
          {debouncedQuery && <span className="w-fit rounded-full bg-[var(--accent-soft)] px-3 py-2 text-xs font-semibold text-[var(--text-main)]">{searchModeUsed === 'hybrid' && semanticAvailable ? 'Busca inteligente' : 'Busca por palavras'}</span>}
        </div>
      </section>

      {loading && <NewsState>Carregando notícias...</NewsState>}
      {!loading && error && <NewsState className="text-[var(--danger-text)]">{error}</NewsState>}

      {!loading && !error && <>
        <div className="space-y-3">
          {news.map((item) => <button key={item.id} type="button" onClick={() => setModalNews(item)} className="group w-full rounded-[22px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4 text-left shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:border-[var(--brand)]/30 hover:shadow-[0_12px_24px_rgba(37,37,37,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)] sm:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                  <span className="rounded bg-[var(--accent-soft)] px-2 py-1 font-bold uppercase tracking-wide text-[var(--brand)]">{getTopic(item)}</span>
                  <span className="text-[var(--text-muted)]">{formatPublishedAt(item.published_at)}</span><span className="text-[var(--text-muted)]">•</span><span className="font-medium text-[var(--text-muted)]">{item.source_name}</span>
                </div>
                <h2 className="mt-3 text-base font-semibold leading-6 text-[var(--text-main)] transition group-hover:text-[var(--brand)] sm:text-lg">{item.title}</h2>
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--text-muted)]">{item.content_preview}</p>
                {item.mentioned_assets.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{item.mentioned_assets.slice(0, 4).map((asset) => <span key={asset} className="rounded-full bg-[var(--bg-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--text-main)]">{asset}</span>)}</div>}
              </div>
              <span className="hidden shrink-0 rounded-full p-2 text-[var(--text-muted)] transition group-hover:bg-[var(--accent-soft)] group-hover:text-[var(--brand)] sm:block" aria-hidden="true"><ChevronRight size={18} /></span>
            </div>
          </button>)}
        </div>
        {news.length === 0 && <NewsState>Nenhuma notícia encontrada com esses filtros.</NewsState>}
        {totalPages > 1 && <nav className="flex flex-wrap items-center justify-between gap-3 rounded-[22px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-4" aria-label="Paginação de notícias">
          <p className="text-sm text-[var(--text-muted)]">Página {page} de {totalPages}</p>
          <div className="flex items-center gap-2">
            <PaginationButton label="Página anterior" disabled={page === 1} onClick={() => setPage((current) => Math.max(1, current - 1))}><ChevronLeft size={16} /></PaginationButton>
            {pageNumbers.map((number) => <PaginationButton key={number} active={number === page} label={`Página ${number}`} onClick={() => setPage(number)}>{number}</PaginationButton>)}
            <PaginationButton label="Próxima página" disabled={page === totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}><ChevronRight size={16} /></PaginationButton>
          </div>
        </nav>}
      </>}

      {modalNews && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="presentation" onClick={() => setModalNews(null)}>
        <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-[32px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-6 shadow-2xl sm:p-8" role="dialog" aria-modal="true" aria-labelledby="news-modal-title" onClick={(event) => event.stopPropagation()}>
          <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold text-[var(--brand)]">{modalNews.source_name}</p><p className="mt-1 text-xs text-[var(--text-muted)]">{formatPublishedAt(modalNews.published_at)}</p></div><button type="button" onClick={() => setModalNews(null)} className="rounded-full p-2 text-[var(--text-muted)] hover:bg-[var(--bg-muted)] hover:text-[var(--text-main)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)]" aria-label="Fechar notícia"><X size={20} /></button></div>
          <h2 id="news-modal-title" className="mt-5 text-2xl font-bold leading-tight text-[var(--text-main)]">{modalNews.title}</h2>
          {modalNews.subtitle && <p className="mt-3 text-base text-[var(--text-muted)]">{modalNews.subtitle}</p>}
          <p className="mt-5 text-sm leading-7 text-[var(--text-main)]">{modalNews.content_preview}</p>
          <div className="mt-6"><h3 className="text-sm font-semibold text-[var(--text-muted)]">Resumo</h3><div className="mt-2 space-y-3">{summaryParagraphs.map((paragraph) => <p key={paragraph} className="text-sm leading-7 text-[var(--text-main)]">{paragraph}</p>)}</div></div>
          {modalNews.mentioned_assets.length > 0 && <div className="mt-5"><p className="text-sm font-semibold text-[var(--text-main)]">Ativos mencionados</p><div className="mt-2 flex flex-wrap gap-2">{modalNews.mentioned_assets.map((asset) => <span key={asset} className="rounded-full bg-[var(--accent-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--brand)]">{asset}</span>)}</div></div>}
          <div className="mt-7 flex flex-wrap gap-3"><a href={modalNews.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-2xl bg-[var(--brand)] px-5 py-2.5 text-sm font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)] focus-visible:ring-offset-2">Abrir original <ExternalLink size={14} /></a><button type="button" onClick={() => setModalNews(null)} className="rounded-2xl border border-[var(--border-soft)] px-5 py-2.5 text-sm font-semibold text-[var(--text-main)] hover:bg-[var(--bg-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)]">Fechar</button></div>
        </div>
      </div>}
    </div>
  );
}

function TopicButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} className={`shrink-0 rounded-full px-4 py-2 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)] ${active ? 'bg-[var(--brand)] text-white' : 'bg-[var(--bg-muted)] text-[var(--text-muted)] hover:text-[var(--text-main)]'}`}>{children}</button>;
}

function NewsState({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-[22px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-10 text-center text-sm text-[var(--text-muted)] ${className}`}>{children}</div>;
}

function PaginationButton({ active = false, disabled = false, label, onClick, children }: { active?: boolean; disabled?: boolean; label: string; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} disabled={disabled} aria-label={label} aria-current={active ? 'page' : undefined} className={`inline-flex min-h-9 min-w-9 items-center justify-center rounded-xl px-3 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)] disabled:cursor-not-allowed disabled:opacity-50 ${active ? 'bg-[var(--brand)] text-white' : 'border border-[var(--border-soft)] text-[var(--text-main)] hover:bg-[var(--bg-muted)]'}`}>{children}</button>;
}
