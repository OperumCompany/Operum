import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  ArrowLeft, ArrowRight, BarChart3, BrainCircuit, BriefcaseBusiness, CalendarDays,
  ChevronRight, CircleHelp, Command, Database, Gauge, Layers3, LineChart,
  MessageCircle, Newspaper, Pause, Play, ShieldCheck, Sparkles, Target,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import './presentation.css';

const logoUrl = new URL('../img/logo.png', import.meta.url).href;

type SlideDefinition = {
  id: string;
  kicker: string;
  targetSeconds: number;
  note: string;
};

const slides: SlideDefinition[] = [
  {
    id: 'origem', kicker: '01 · Origem', targetSeconds: 30,
    note: 'O Operum não nasceu dentro de uma sala de aula. Ele nasceu de uma necessidade real. Em 2016, um dos integrantes do nosso grupo começou a aprender sobre investimentos com o primo e percebeu uma dificuldade que acompanha muitos investidores: existem muitos dados, muitas notícias, muitas opiniões, mas pouca clareza sobre o que fazer com tudo isso. A ideia começou simples, virou uma planilha em Excel, passou por diversas transformações e, em 2025, se tornou uma aplicação web, conquistando o terceiro lugar no NEXT. Hoje, depois de quase dez anos de evolução, apresentamos o Operum.',
  },
  {
    id: 'problema', kicker: '02 · Problema', targetSeconds: 30,
    note: 'Hoje, qualquer pessoa consegue abrir uma conta em uma corretora e comprar um ativo em poucos minutos. Mas conseguir investir não significa saber decidir bem. O investidor pula entre notícias, gráficos, relatórios e opiniões contraditórias. No final, continua com a mesma dúvida: compro, vendo, mantenho ou espero? O problema não é falta de informação. É excesso de informação sem organização, contexto e clareza. Quando dinheiro está envolvido, essa confusão gera insegurança, decisões emocionais e oportunidades perdidas. Essa é a dor que o Operum resolve.',
  },
  {
    id: 'solucao', kicker: '03 · Solução', targetSeconds: 30,
    note: 'O Operum centraliza a experiência do investidor. Em vez de depender de várias fontes separadas, ele acompanha carteira, ativos, notícias, cenários e análises em um só lugar. A plataforma ajuda o usuário a entender o contexto da carteira como um todo: o que aconteceu, o que está acontecendo agora e quais cenários podem surgir nos próximos meses. A proposta é transformar complexidade financeira em clareza para apoiar decisões melhores.',
  },
  {
    id: 'preditividade', kicker: '04 · O diferencial', targetSeconds: 40,
    note: 'Aqui está o principal diferencial do Operum: a camada de preditividade. Ao selecionar um ativo, o usuário visualiza análises para 1, 2 e 3 meses. O Operum combina histórico de preços, volatilidade, liquidez, indicadores financeiros, contexto econômico e notícias relevantes. A partir disso, apresenta possíveis cenários futuros, nível de confiança, riscos e fatores que influenciam o resultado. O mais importante é que a plataforma não mostra apenas um número. Ela explica por que aquele cenário faz sentido e como ele pode impactar a carteira.',
  },
  {
    id: 'ecossistema', kicker: '05 · Ecossistema', targetSeconds: 25,
    note: 'O Operum não termina na previsão. Ele cria um ecossistema para acompanhar a jornada do investidor. O usuário pode organizar carteiras, simular estratégias, acompanhar notícias relacionadas aos seus ativos e conversar com um chat inteligente para aprender e interpretar informações. Isso atende tanto investidores iniciantes, que precisam de apoio e educação, quanto investidores experientes, que querem organizar melhor suas análises. O objetivo é reduzir a distância entre informação e decisão.',
  },
  {
    id: 'fechamento', kicker: '06 · Próximos futuros', targetSeconds: 25,
    note: 'O mercado nunca será totalmente previsível, e o Operum não promete isso. A proposta é transformar incerteza em cenários compreensíveis. No B2C, o produto pode crescer por assinatura recorrente. No B2B, a inteligência analítica pode ser licenciada para fintechs, plataformas financeiras e empresas. O Operum começou como uma ideia, evoluiu para uma planilha, virou um projeto premiado e hoje se torna uma plataforma para ajudar pessoas a investir com mais informação, contexto e confiança. O Operum não tenta adivinhar o futuro. Ele prepara o investidor para os possíveis futuros.',
  },
];

const numberFormatter = new Intl.NumberFormat('pt-BR');

function formatTime(value: number) {
  const minutes = Math.floor(value / 60);
  return `${String(minutes).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
}

function Reveal({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduceMotion ? false : { opacity: 0, y: 18, filter: 'blur(5px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ duration: reduceMotion ? 0 : 0.52, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

function OperumMark({ inverse = false }: { inverse?: boolean }) {
  return <div className={`pitch-brand ${inverse ? 'is-inverse' : ''}`}><img src={logoUrl} alt="Operum" /><span>OPERUM</span></div>;
}

function SectionTitle({ kicker, title, description }: { kicker: string; title: React.ReactNode; description?: string }) {
  return <div className="pitch-heading"><Reveal><p className="pitch-kicker">{kicker}</p></Reveal><Reveal delay={0.08}><h1>{title}</h1></Reveal>{description && <Reveal delay={0.16}><p className="pitch-description">{description}</p></Reveal>}</div>;
}

function TrendChart({ prediction = false }: { prediction?: boolean }) {
  const reduceMotion = useReducedMotion();
  return (
    <svg className="pitch-line-chart" viewBox="0 0 660 250" aria-label={prediction ? 'Gráfico demonstrativo com projeção de cenários' : 'Gráfico demonstrativo de evolução de patrimônio'} role="img">
      <defs>
        <linearGradient id="line-fill" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#684CF2" stopOpacity=".32" /><stop offset="1" stopColor="#684CF2" stopOpacity="0" /></linearGradient>
        <linearGradient id="future-fill" x1="0" x2="1" y1="0" y2="0"><stop stopColor="#DF50F2" stopOpacity=".12" /><stop offset="1" stopColor="#DF50F2" stopOpacity=".42" /></linearGradient>
      </defs>
      {[46, 96, 146, 196].map((y) => <line key={y} x1="0" x2="660" y1={y} y2={y} className="pitch-grid-line" />)}
      <motion.path d="M0,199 C56,184 73,190 114,174 S181,154 218,164 S282,138 318,133 S388,105 430,113 L430,250 L0,250 Z" fill="url(#line-fill)" initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: .75 }} />
      <motion.path d="M0,199 C56,184 73,190 114,174 S181,154 218,164 S282,138 318,133 S388,105 430,113" className="pitch-chart-history" initial={reduceMotion ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: .9, ease: 'easeOut' }} />
      {prediction && <>
        <motion.path d="M430,113 C486,100 538,128 660,65 L660,182 C548,218 486,198 430,150 Z" fill="url(#future-fill)" initial={reduceMotion ? false : { opacity: 0, scaleX: 0 }} animate={{ opacity: 1, scaleX: 1 }} style={{ originX: 0 }} transition={{ duration: .7, delay: .55 }} />
        <motion.path d="M430,113 C486,100 538,128 660,65" className="pitch-chart-future" initial={reduceMotion ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: .7, delay: .62 }} />
        <motion.path d="M430,150 C486,142 548,161 660,122" className="pitch-chart-future-muted" initial={reduceMotion ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: .7, delay: .7 }} />
      </>}
      <line x1="430" x2="430" y1="28" y2="226" className="pitch-today-line" />
      <text x="412" y="28" className="pitch-chart-label">HOJE</text>
      {prediction && <text x="560" y="28" className="pitch-chart-label">CENÁRIOS</text>}
    </svg>
  );
}

function DashboardMock() {
  return <div className="product-screen dashboard-mock" aria-label="Réplica demonstrativa da Visão Geral do Operum">
    <div className="screen-topbar"><span className="screen-logo-dot"><Sparkles size={11} /></span><span>Visão geral</span><span className="screen-badge">Carteira Exemplo</span></div>
    <div className="screen-content">
      <div className="dashboard-metrics"><div><small>VALOR ATUAL</small><strong>R$ 128.490</strong><em>+12,4%</em></div><div><small>P&L NÃO REALIZADO</small><strong className="small-number">R$ 14.220</strong><em>em acompanhamento</em></div></div>
      <div className="dashboard-chart"><div className="screen-chart-header"><span>Evolução do patrimônio</span><small>6 meses</small></div><TrendChart /></div>
      <div className="dashboard-bottom"><div className="allocation-bars"><small>ALOCAÇÃO FINANCEIRA</small><i style={{ width: '86%' }} /><i style={{ width: '64%' }} /><i style={{ width: '42%' }} /></div><div className="insight-bubble"><Sparkles size={12} /><span>Contexto de IA atualizado</span></div></div>
    </div>
  </div>;
}

function PredictionMock() {
  return <div className="product-screen prediction-mock" aria-label="Réplica demonstrativa da análise preditiva de ITUB4">
    <div className="screen-topbar"><span className="screen-logo-dot"><BrainCircuit size={11} /></span><span>Análise do ativo</span><span className="screen-badge">Demonstração</span></div>
    <div className="screen-content prediction-content">
      <div className="analysis-position-row" aria-label="Resumo demonstrativo da posição ITUB4"><strong>ITUB4</strong><span>150</span><span>R$ 28,60</span><span>R$ 29,17</span><span>R$ 4.375,50</span><b>R$ 85,50 (2,0%)</b><em>Remover</em></div>
      <section className="analysis-context">
        <div className="analysis-context-title"><div><strong>ITUB4 (ITUB4)</strong><span>Confiança baixa | Cenário: demonstrativo</span><small>Janela histórica e fatores apresentados para ilustração.</small></div><span className="screen-badge">Dados simulados</span></div>
        <div className="analysis-context-grid">
          <article><b>Últimos 3 meses</b><div className="analysis-pills"><span>1 semana</span><span>1 mês</span><strong>3 meses</strong></div><p>ITUB4 apresentou oscilação demonstrativa.</p></article>
          <article><b>Situação atual</b><p>Preço, quantidade e participação são demonstrativos.</p></article>
          <article><b>Perspectiva</b><div className="analysis-pills"><span>1 semana</span><span>1 mês</span><strong>3 meses</strong></div><p>Variação moderada para o cenário-base.</p></article>
        </div>
      </section>
      <section className="analysis-price-card">
        <div className="analysis-price-header"><div className="analysis-price"><small>PREÇO</small><strong>R$ 29,17</strong><span>+9,0% <em>vs. 3 meses</em></span></div><div className="analysis-chart-tabs"><div><b>Últimos</b><span>1 sem.</span><span>1 mês</span><strong>3 meses</strong></div><div><b>Perspectiva</b><span>1 sem.</span><span>1 mês</span><strong>3 meses</strong></div></div></div>
        <div className="prediction-chart"><TrendChart prediction /></div>
        <div className="analysis-chart-footer"><span><i className="history-dot" /> Histórico</span><span><i className="future-dot" /> Perspectiva estimada</span><small>Projeção demonstrativa; não representa garantia de preço futuro.</small></div>
      </section>
    </div>
  </div>;
}

function MiniScreen({ type }: { type: 'news' | 'portfolio' | 'chat' }) {
  const content = type === 'news'
    ? <><div className="mini-heading">Inteligência de mercado</div><div className="mini-news"><b>Mercado</b><span>Banco Central sinaliza atenção aos juros</span></div><div className="mini-news"><b>Economia</b><span>Dados globais movimentam ativos</span></div></>
    : type === 'portfolio'
      ? <><div className="mini-heading">Carteiras</div><div className="mini-portfolio-value">R$ 128.490 <span>+12,4%</span></div><div className="mini-bars"><i /><i /><i /></div></>
      : <><div className="mini-heading">Operum IA</div><div className="mini-chat-user">Como está minha exposição?</div><div className="mini-chat-ai">Sua carteira tem concentração em ações brasileiras. Veja os cenários.</div></>;
  return <div className={`mini-screen ${type}`} aria-label={`Réplica demonstrativa de ${type}`}>{content}</div>;
}

function ClosingSignalCard({ type }: { type: 'data' | 'scenarios' | 'context' }) {
  const content = type === 'data'
    ? <><span className="closing-card-icon"><Database size={17} /></span><div><small>DADOS</small><strong>Uma visão clara da carteira</strong><p>Ativos, valores e exposição em um só lugar.</p></div><div className="closing-sparkline"><i /><i /><i /><i /><i /></div></>
    : type === 'scenarios'
      ? <><span className="closing-card-icon"><LineChart size={17} /></span><div><small>CENÁRIOS</small><strong>Possíveis próximos caminhos</strong><p>Histórico, perspectiva e confiança.</p></div><div className="closing-probability"><b>64%</b><span>alta</span></div></>
      : <><span className="closing-card-icon"><Sparkles size={17} /></span><div><small>CONTEXTO</small><strong>Entenda antes de decidir</strong><p>Fatores, notícias e IA para interpretar.</p></div><div className="closing-context-dot"><Newspaper size={13} /></div></>;
  return <article className={`closing-signal-card is-${type}`}>{content}</article>;
}

function SlideOne() {
  return <div className="pitch-slide hero-slide"><div className="hero-noise" /><div className="hero-orb pitch-orb-one" /><div className="hero-orb pitch-orb-two" /><div className="pitch-slide-inner hero-layout"><Reveal><OperumMark inverse /></Reveal><div className="hero-copy"><Reveal delay={0.1}><p className="pitch-kicker is-light">A evolução de uma ideia</p></Reveal><Reveal delay={0.18}><h1>Preditividade inteligente<br />para sua carteira.</h1></Reveal><Reveal delay={0.3}><p>Uma ideia que nasceu de uma dor real e evoluiu para uma plataforma inteligente de apoio ao investidor.</p></Reveal></div><Reveal delay={0.48} className="history-line"><span><b>2016</b><i />Ideia</span><span><b>Excel</b><i />Primeiro modelo</span><span><b>NEXT 2025</b><i />3º lugar</span><span><b>Operum</b><i />Hoje</span></Reveal><Reveal delay={0.65} className="hero-footnote"><Sparkles size={15} /> Dados, cenários e contexto para decisões mais conscientes.</Reveal></div></div>;
}

function SlideTwo() {
  const problems = [
    [Database, 'Informação demais', 'Notícias, gráficos, opiniões, indicadores e dados espalhados.'],
    [CircleHelp, 'Insegurança para decidir', 'Comprar? Vender? Manter? Esperar?'],
    [Command, 'Falta de contexto', 'O investidor vê o que aconteceu, mas não entende o que pode acontecer depois.'],
  ] as const;
  return <div className="pitch-slide light-slide"><div className="pitch-slide-inner problem-layout"><SectionTitle kicker="O problema" title={<>Informação demais.<br /><span>Entendimento de menos.</span></>} description="Quando falta contexto, decisões viram incerteza." /><div className="problem-grid">{problems.map(([Icon, title, copy], index) => <Reveal key={title} delay={.28 + index * .12}><article className="problem-card"><span><Icon size={24} /></span><h2>{title}</h2><p>{copy}</p><b>0{index + 1}</b></article></Reveal>)}</div></div></div>;
}

function SlideThree() {
  const highlights = [['Carteiras', BriefcaseBusiness], ['Dados financeiros', BarChart3], ['Notícias', Newspaper], ['Cenários', LineChart], ['Inteligência Artificial', Sparkles]] as const;
  return <div className="pitch-slide solution-slide"><div className="pitch-slide-inner solution-layout"><div><SectionTitle kicker="A solução" title="Uma única plataforma para entender sua carteira." description="O Operum transforma dados dispersos em uma visão clara, organizada e inteligente." /><div className="feature-tags">{highlights.map(([label, Icon], index) => <Reveal key={label} delay={.28 + index * .06}><span><Icon size={14} />{label}</span></Reveal>)}</div></div><Reveal delay={.24} className="dashboard-wrap"><DashboardMock /><div className="floating-callout top"><Target size={16} /><span>Visão de toda a carteira</span></div><div className="floating-callout side"><Sparkles size={16} /><span>Contexto em um só lugar</span></div></Reveal></div></div>;
}

function SlideFour() {
  const indicators = [['Probabilidade de alta', '64%'], ['Faixa provável', 'R$ 36–42'], ['Cenário esperado', 'Equilibrado'], ['Nível de confiança', 'Moderado']] as const;
  return <div className="pitch-slide prediction-slide"><div className="pitch-slide-inner prediction-layout"><div className="prediction-copy"><SectionTitle kicker="O coração do Operum" title={<>Não apenas o que aconteceu.<br /><span>O que pode acontecer depois.</span></>} description="Análises preditivas em horizontes de 1, 2 e 3 meses." /><div className="prediction-indicators">{indicators.map(([label, value], index) => <Reveal key={label} delay={.28 + index * .08}><div><small>{label}</small><strong>{value}</strong></div></Reveal>)}</div><Reveal delay={.68}><p className="demo-disclaimer"><ShieldCheck size={15} /> Cenários demonstrativos para apoio à decisão — não são recomendação de investimento.</p></Reveal></div><Reveal delay={.22} className="prediction-wrap"><PredictionMock /><div className="prediction-factors"><span><Newspaper size={15} /> Notícias e fatores relevantes</span><span><Gauge size={15} /> Volatilidade e liquidez</span></div></Reveal></div></div>;
}

function SlideFive() {
  const features = [
    [BrainCircuit, 'IA Preditiva', 'Cenários de 1, 2 e 3 meses.'],
    [Layers3, 'Carteiras e Simulações', 'Teste composições antes de decidir.'],
    [Newspaper, 'Notícias contextualizadas', 'Entenda o que impacta seus ativos.'],
    [MessageCircle, 'Chat inteligente', 'Aprenda e interprete informações.'],
  ] as const;
  return <div className="pitch-slide ecosystem-slide"><div className="pitch-slide-inner ecosystem-layout"><SectionTitle kicker="Ecossistema" title="Tudo que o investidor precisa para decidir com mais contexto." /><div className="ecosystem-content"><div className="ecosystem-grid">{features.map(([Icon, title, copy], index) => <Reveal key={title} delay={.2 + index * .08}><article className="ecosystem-card"><span><Icon size={23} /></span><h2>{title}</h2><p>{copy}</p></article></Reveal>)}</div><Reveal delay={.35} className="mini-screens"><MiniScreen type="news" /><MiniScreen type="portfolio" /><MiniScreen type="chat" /></Reveal></div></div></div>;
}

function SlideSix() {
  return <div className="pitch-slide close-slide"><div className="close-glow" /><div className="pitch-slide-inner close-layout"><div className="close-mosaic"><Reveal delay={.08}><ClosingSignalCard type="data" /></Reveal><Reveal delay={.18}><ClosingSignalCard type="scenarios" /></Reveal><Reveal delay={.28}><ClosingSignalCard type="context" /></Reveal></div><div className="close-copy"><Reveal><OperumMark inverse /></Reveal><Reveal delay={.1}><h1>O futuro é incerto.<br /><span>Sua decisão não precisa ser.</span></h1></Reveal><Reveal delay={.22}><p className="close-flow"><b>Dados</b><ChevronRight /><b>Cenários</b><ChevronRight /><b>Contexto</b><ChevronRight /><b>Decisão</b></p></Reveal><Reveal delay={.35}><div className="business-model"><span><small>B2C</small> Assinatura da plataforma</span><span><small>B2B</small> Licenciamento da inteligência analítica</span></div></Reveal><Reveal delay={.48}><p className="close-final">O Operum não tenta adivinhar o futuro. Ele prepara o investidor para os possíveis futuros.</p></Reveal></div></div></div>;
}

const slideComponents = [SlideOne, SlideTwo, SlideThree, SlideFour, SlideFive, SlideSix];

export function PresentationPage() {
  const [current, setCurrent] = useState(0);
  const [direction, setDirection] = useState(1);
  const [notesOpen, setNotesOpen] = useState(false);
  const [isRunning, setIsRunning] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const reduceMotion = useReducedMotion();
  const ActiveSlide = slideComponents[current];
  const totalTarget = useMemo(() => slides.reduce((sum, slide) => sum + slide.targetSeconds, 0), []);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = 'Operum — Pitch';
    return () => { document.title = previousTitle; };
  }, []);

  const goTo = useCallback((next: number) => {
    const normalized = Math.max(0, Math.min(slides.length - 1, next));
    setDirection(normalized >= current ? 1 : -1);
    setCurrent(normalized);
  }, [current]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === 'ArrowRight' || event.key === ' ' || event.key === 'PageDown') { event.preventDefault(); goTo(current + 1); }
      if (event.key === 'ArrowLeft' || event.key === 'PageUp') { event.preventDefault(); goTo(current - 1); }
      if (event.key === 'Home') { event.preventDefault(); goTo(0); }
      if (event.key === 'End') { event.preventDefault(); goTo(slides.length - 1); }
      if (event.key.toLowerCase() === 'n') setNotesOpen((open) => !open);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [current, goTo]);

  useEffect(() => {
    if (!isRunning) return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [isRunning]);

  const transition = reduceMotion ? { duration: 0 } : { duration: .48, ease: [0.22, 1, 0.36, 1] as const };
  return <main className="presentation-page" aria-label="Pitch Operum">
    <div className="presentation-stage">
      <AnimatePresence initial={false} mode="wait" custom={direction}>
        <motion.div key={slides[current].id} className="presentation-slide-host" custom={direction} initial={{ opacity: 0, x: reduceMotion ? 0 : direction * 46 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: reduceMotion ? 0 : direction * -46 }} transition={transition}>
          <ActiveSlide />
        </motion.div>
      </AnimatePresence>
    </div>

    <nav className="presentation-controls" aria-label="Controles da apresentação">
      <button type="button" onClick={() => goTo(current - 1)} disabled={current === 0} aria-label="Slide anterior"><ArrowLeft size={17} /></button>
      <div className="presentation-progress" aria-label={`Slide ${current + 1} de ${slides.length}`}>{slides.map((slide, index) => <button key={slide.id} type="button" className={index === current ? 'is-active' : ''} onClick={() => goTo(index)} aria-label={`Ir para slide ${index + 1}: ${slide.kicker}`}><span /></button>)}</div>
      <button type="button" onClick={() => goTo(current + 1)} disabled={current === slides.length - 1} aria-label="Próximo slide"><ArrowRight size={17} /></button>
      <button type="button" className="notes-trigger" onClick={() => setNotesOpen((open) => !open)} aria-pressed={notesOpen}>Notas <kbd>N</kbd></button>
    </nav>

    <div className={`presentation-meta ${current > 0 && current < slides.length - 1 ? 'is-light' : ''}`}><span>{slides[current].kicker}</span><span>{numberFormatter.format(current + 1).padStart(2, '0')} / {numberFormatter.format(slides.length).padStart(2, '0')}</span></div>
    <aside className={`presentation-notes ${notesOpen ? 'is-open' : ''}`} aria-label="Notas do apresentador" aria-hidden={!notesOpen}>
      <div className="notes-top"><div><p>Notas do apresentador</p><strong>{slides[current].kicker}</strong></div><button type="button" onClick={() => setNotesOpen(false)} aria-label="Fechar notas">×</button></div>
      <p className="notes-script">{slides[current].note}</p>
      <div className="notes-timer"><span><CalendarDays size={16} /> Meta: {formatTime(slides.slice(0, current + 1).reduce((sum, slide) => sum + slide.targetSeconds, 0))}</span><strong>{formatTime(elapsed)} <small>/ {formatTime(totalTarget)}</small></strong><button type="button" onClick={() => setIsRunning((running) => !running)} aria-label={isRunning ? 'Pausar cronômetro' : 'Iniciar cronômetro'}>{isRunning ? <Pause size={15} /> : <Play size={15} />}</button></div>
    </aside>
  </main>;
}
