import { ArrowRight, Bot, BriefcaseBusiness, Check, Gauge, Layers3, Newspaper, ShieldCheck, Sparkles, TrendingUp } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Brand } from '../components/Brand';
import { ThemeToggle } from '../components/ThemeToggle';
import { useAuth } from '../context/AuthContext';

const features = [
  {
    icon: TrendingUp,
    title: 'Previsao por ativo',
    description: 'Transforme preco, historico e sinais recentes em perspectivas claras para acompanhar cada posicao.',
  },
  {
    icon: Newspaper,
    title: 'Noticias que importam',
    description: 'A IA conecta acontecimentos do mercado aos ativos da sua carteira e separa ruido de contexto relevante.',
  },
  {
    icon: Gauge,
    title: 'Status dos ativos',
    description: 'O Operum mede comportamento, volatilidade, sinais de mercado e qualidade do contexto antes de gerar a leitura.',
  },
  {
    icon: Bot,
    title: 'Analise pronta para ler',
    description: 'Uma camada de IA organiza os sinais e entrega uma analise objetiva, educativa e facil de comparar.',
  },
  {
    icon: BriefcaseBusiness,
    title: 'Carteiras para simular',
    description: 'Crie diferentes carteiras para testar cenarios, estrategias e exposicoes sem misturar suas hipoteses.',
  },
  {
    icon: ShieldCheck,
    title: 'Fontes e limites visiveis',
    description: 'Veja noticias usadas, confianca e avisos. O Operum apoia sua analise, nao decide por voce.',
  },
];

const engines = [
  ['01', 'IA de noticias', 'Coleta, interpreta e relaciona noticias ao ativo certo, no horizonte certo.'],
  ['02', 'IA de status', 'Mede preco, volatilidade, sinais recentes e papel do ativo dentro da carteira.'],
  ['03', 'IA de sintese', 'Formata tudo em uma analise final direta, comparavel e sem linguagem desnecessaria.'],
];

const primaryLink = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#684cf2] px-5 py-3 text-sm font-semibold text-white shadow-[0_10px_26px_rgba(104,76,242,.2)] transition hover:-translate-y-0.5 hover:bg-[#4f2cd9]';
const ghostLink = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[var(--border-soft)] bg-[var(--bg-surface)] px-5 py-3 text-sm font-semibold transition hover:-translate-y-0.5 hover:border-[var(--border-strong)]';

export function LandingPage() {
  const { user, loading } = useAuth();
  const appTarget = user ? '/app' : '/registro';
  const appLabel = user ? 'Acessar plataforma' : 'Criar conta';

  return (
    <div className="landing-page">
      <header className="landing-header">
        <div className="landing-container landing-header-inner">
          <Brand />
          <nav className="landing-nav" aria-label="Navegacao institucional">
            <a href="#produto">Produto</a>
            <a href="#motores">3 motores</a>
            <a href="#simulacoes">Simulacoes</a>
          </nav>
          <div className="landing-actions">
            <ThemeToggle />
            {!user && !loading && <Link to="/login" className={ghostLink}>Entrar</Link>}
            <Link to={appTarget} className={primaryLink}>{appLabel}<ArrowRight size={16} /></Link>
          </div>
        </div>
      </header>

      <main>
        <section className="landing-container landing-hero">
          <div>
            <span className="eyebrow">Previsao de ativos com IA</span>
            <h1 className="landing-title">Veja o que pode mover seus ativos <span className="gradient-text">antes do mercado virar manchete.</span></h1>
            <p className="landing-lead">
              O Operum combina noticias, leitura quantitativa e IA para transformar sua carteira em cenarios de analise. Compare ativos, entenda riscos e acompanhe previsoes com contexto.
            </p>
            <div className="landing-cta-row">
              <Link to={appTarget} className={primaryLink}>{appLabel}<ArrowRight size={17} /></Link>
              <a href="#produto" className={ghostLink}>Conhecer o Operum</a>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm text-[var(--text-muted)]">
              {['Previsoes por horizonte', 'Noticias conectadas aos ativos', 'Carteiras para simulacao'].map((item) => (
                <span key={item} className="inline-flex items-center gap-2"><Check size={15} className="text-[var(--accent)]" />{item}</span>
              ))}
            </div>
          </div>

          <div className="hero-visual" aria-label="Previa visual do painel Operum">
            <div className="hero-orb" />
            <div className="hero-dashboard surface-card">
              <div className="hero-dashboard-header">
                <div><p className="eyebrow">Previsao Operum</p><h2 className="mt-1 text-lg font-semibold">PETR4 em foco</h2></div>
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent)] shadow-[0_0_14px_var(--accent)]" />
              </div>
              <div className="hero-metrics">
                <div className="hero-metric"><p className="text-xs text-[var(--text-muted)]">Horizonte</p><p className="mt-3 font-data text-2xl font-semibold">3m</p></div>
                <div className="hero-metric"><p className="text-xs text-[var(--text-muted)]">Noticias</p><p className="mt-3 font-data text-2xl font-semibold">18</p></div>
                <div className="hero-metric"><p className="text-xs text-[var(--text-muted)]">Status</p><p className="mt-3 text-sm font-semibold text-[var(--brand)]">Cauteloso</p></div>
              </div>
              <div className="hero-chart" aria-hidden="true">
                {[38, 54, 43, 68, 61, 82, 74, 92].map((height, index) => <span key={index} style={{ height: `${height}%` }} />)}
              </div>
            </div>
            <div className="hero-insight ai-surface">
              <div className="flex items-center gap-2 text-[var(--accent)]"><Sparkles size={16} /><span className="eyebrow !text-[var(--accent)]">Insight Operum</span></div>
              <p className="mt-3 text-sm font-semibold">Analise com noticia, status e previsao em uma unica leitura.</p>
            </div>
          </div>
        </section>

        <section id="produto" className="landing-section landing-section-muted scroll-mt-20">
          <div className="landing-container">
            <div className="section-heading">
              <span className="eyebrow">Venda a incerteza antes dela cobrar caro</span>
              <h2>Uma plataforma para prever, comparar e acompanhar ativos com mais conviccao.</h2>
              <p>O Operum tira a analise do achismo: cada leitura nasce de noticias, dados de mercado, status do ativo e uma sintese pensada para decisao informada.</p>
            </div>
            <div className="feature-grid">
              {features.map(({ icon: Icon, title, description }) => (
                <article key={title} className="feature-card surface-card">
                  <span className="feature-icon"><Icon size={21} /></span>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="motores" className="landing-container landing-section scroll-mt-20">
          <div className="story-grid">
            <div className="section-heading">
              <span className="eyebrow">Os 3 motores do Operum</span>
              <h2>Noticias, status e sintese trabalhando juntos.</h2>
              <p>Cada analise combina sinais independentes para chegar em uma leitura final clara, rastreavel e pronta para comparar entre ativos.</p>
            </div>
            <div className="story-list">
              {engines.map(([number, title, description]) => (
                <div key={number} className="story-item"><span className="story-number">{number}</span><div><h3 className="text-lg font-semibold">{title}</h3><p>{description}</p></div></div>
              ))}
            </div>
          </div>
        </section>

        <section id="simulacoes" className="landing-section landing-section-muted scroll-mt-20">
          <div className="landing-container">
            <div className="landing-final ai-surface">
              <Layers3 className="mx-auto text-[var(--accent)]" size={28} />
              <h2 className="mt-5">Monte carteiras diferentes para testar teses diferentes.</h2>
              <p>Simule cenarios conservadores, agressivos, concentrados ou diversificados. Compare exposicoes e analises sem perder o historico de cada estrategia. O Operum apoia sua leitura e nao recomenda compra ou venda de ativos.</p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link to={appTarget} className={primaryLink}>{appLabel}<ArrowRight size={17} /></Link>
                {!user && <Link to="/login" className={ghostLink}>Ja tenho uma conta</Link>}
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <Brand />
          <p>Plataforma de apoio a previsao, analise e educacao financeira.</p>
          <div className="flex items-center gap-4"><ThemeToggle /><span>(c) {new Date().getFullYear()} Operum</span></div>
        </div>
      </footer>
    </div>
  );
}
