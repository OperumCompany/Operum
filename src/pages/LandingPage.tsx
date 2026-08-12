import { ArrowRight, BarChart3, Bot, BriefcaseBusiness, Check, Newspaper, ShieldCheck, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Brand } from '../components/Brand';
import { ThemeToggle } from '../components/ThemeToggle';
import { useAuth } from '../context/AuthContext';

const features = [
  {
    icon: BriefcaseBusiness,
    title: 'Carteiras organizadas',
    description: 'Reúna posições, acompanhe composição e identifique concentrações em uma visão clara.',
  },
  {
    icon: BarChart3,
    title: 'Análise na sua medida',
    description: 'Comece pelo resumo essencial e avance para gráficos, cenários e indicadores quando precisar.',
  },
  {
    icon: Newspaper,
    title: 'Notícias com contexto',
    description: 'Filtre acontecimentos do mercado e entenda quais temas podem se relacionar com seus ativos.',
  },
  {
    icon: Bot,
    title: 'IA explicativa',
    description: 'Converse sobre finanças e use a carteira ativa como contexto, sempre com caráter educativo.',
  },
  {
    icon: Sparkles,
    title: 'Leituras por ativo',
    description: 'Consulte situação atual, histórico, perspectivas e as fontes usadas em cada análise.',
  },
  {
    icon: ShieldCheck,
    title: 'Controle e transparência',
    description: 'Dados, fontes e níveis de confiança permanecem visíveis para apoiar sua própria leitura.',
  },
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
          <nav className="landing-nav" aria-label="Navegação institucional">
            <a href="#produto">Produto</a>
            <a href="#como-funciona">Como funciona</a>
            <a href="#clareza">Clareza e IA</a>
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
            <span className="eyebrow">Inteligência financeira com clareza</span>
            <h1 className="landing-title">Seus investimentos, <span className="gradient-text">mais fáceis de entender.</span></h1>
            <p className="landing-lead">
              O Operum organiza sua carteira, conecta notícias ao seu contexto e transforma dados financeiros em leituras claras — sem esconder a profundidade quando você quiser ir além.
            </p>
            <div className="landing-cta-row">
              <Link to={appTarget} className={primaryLink}>{appLabel}<ArrowRight size={17} /></Link>
              <a href="#produto" className={ghostLink}>Conhecer o Operum</a>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm text-[var(--text-muted)]">
              {['Visão simples e técnica', 'Fontes rastreáveis', 'Conteúdo educativo'].map((item) => (
                <span key={item} className="inline-flex items-center gap-2"><Check size={15} className="text-[var(--accent)]" />{item}</span>
              ))}
            </div>
          </div>

          <div className="hero-visual" aria-label="Prévia visual do painel Operum">
            <div className="hero-orb" />
            <div className="hero-dashboard surface-card">
              <div className="hero-dashboard-header">
                <div><p className="eyebrow">Visão geral</p><h2 className="mt-1 text-lg font-semibold">Carteira em foco</h2></div>
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent)] shadow-[0_0_14px_var(--accent)]" />
              </div>
              <div className="hero-metrics">
                <div className="hero-metric"><p className="text-xs text-[var(--text-muted)]">Ativos</p><p className="mt-3 font-data text-2xl font-semibold">12</p></div>
                <div className="hero-metric"><p className="text-xs text-[var(--text-muted)]">Classes</p><p className="mt-3 font-data text-2xl font-semibold">04</p></div>
                <div className="hero-metric"><p className="text-xs text-[var(--text-muted)]">Leitura</p><p className="mt-3 text-sm font-semibold text-[var(--brand)]">Diversificada</p></div>
              </div>
              <div className="hero-chart" aria-hidden="true">
                {[38, 54, 43, 68, 61, 82, 74, 92].map((height, index) => <span key={index} style={{ height: `${height}%` }} />)}
              </div>
            </div>
            <div className="hero-insight ai-surface">
              <div className="flex items-center gap-2 text-[var(--accent)]"><Sparkles size={16} /><span className="eyebrow !text-[var(--accent)]">Insight Operum</span></div>
              <p className="mt-3 text-sm font-semibold">Uma leitura direta, com contexto e fontes acessíveis.</p>
            </div>
          </div>
        </section>

        <section id="produto" className="landing-section landing-section-muted scroll-mt-20">
          <div className="landing-container">
            <div className="section-heading">
              <span className="eyebrow">Uma plataforma, várias perspectivas</span>
              <h2>Do panorama da carteira aos detalhes que explicam cada movimento.</h2>
              <p>Ferramentas conectadas para organizar, acompanhar e aprofundar sua análise sem perder o fio da informação.</p>
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

        <section id="como-funciona" className="landing-container landing-section scroll-mt-20">
          <div className="story-grid">
            <div className="section-heading">
              <span className="eyebrow">Como funciona</span>
              <h2>Comece simples. Aprofunde no seu ritmo.</h2>
              <p>O produto mantém as ações importantes por perto e apresenta a complexidade financeira em camadas compreensíveis.</p>
            </div>
            <div className="story-list">
              {[
                ['01', 'Organize sua carteira', 'Crie carteiras e registre as posições que deseja acompanhar.'],
                ['02', 'Enxergue o essencial', 'Veja composição, concentração, notícias relacionadas e próximos passos.'],
                ['03', 'Investigue com contexto', 'Abra análises por ativo, cenários, indicadores técnicos e converse com o agente.'],
              ].map(([number, title, description]) => (
                <div key={number} className="story-item"><span className="story-number">{number}</span><div><h3 className="text-lg font-semibold">{title}</h3><p>{description}</p></div></div>
              ))}
            </div>
          </div>
        </section>

        <section id="clareza" className="landing-section landing-section-muted scroll-mt-20">
          <div className="landing-container">
            <div className="landing-final ai-surface">
              <Sparkles className="mx-auto text-[var(--accent)]" size={28} />
              <h2 className="mt-5">IA para explicar, não para decidir por você.</h2>
              <p>O Operum oferece conteúdo educativo, indica confiança e preserva as fontes da análise. A plataforma não recomenda compra ou venda de ativos.</p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link to={appTarget} className={primaryLink}>{appLabel}<ArrowRight size={17} /></Link>
                {!user && <Link to="/login" className={ghostLink}>Já tenho uma conta</Link>}
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <Brand />
          <p>Plataforma de apoio à análise e educação financeira.</p>
          <div className="flex items-center gap-4"><ThemeToggle /><span>© {new Date().getFullYear()} Operum</span></div>
        </div>
      </footer>
    </div>
  );
}
