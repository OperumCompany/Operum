from __future__ import annotations

from collections import Counter
import json
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from app.core.config import AI_ENABLE_CHATBOT
from app.schemas.chat import ChatInputMessage
from app.schemas.portfolio import Portfolio
from app.services.asset_universe_service import AssetUniverseService
from app.services.knowledge_service import KnowledgeService, normalize_text
from app.services.llm_prompts import EDUCATIONAL_CHATBOT_PROMPT
from app.services.llm_service import LLMService
from app.services.news_ingestion_service import NewsIngestionService
from app.services.news_semantic_service import NewsSemanticService


TEMPORAL_TERMS = {
    "hoje", "agora", "atual", "atuais", "recente", "recentes", "esta semana",
    "este mes", "últimas notícias", "ultimas noticias", "notícia", "noticia",
    "mercado", "resultado trimestral", "copom", "cotação", "cotacao",
}
PORTFOLIO_TERMS = {"carteira", "posição", "posicao", "patrimônio", "patrimonio", "meus ativos", "concentração", "concentracao"}
FINANCE_TERMS = {
    "ação", "acao", "ações", "acoes", "ativo", "investimento", "fii", "etf", "bdr",
    "renda", "juros", "selic", "cdi", "ipca", "inflação", "inflacao", "dividendo",
    "lucro", "bolsa", "mercado", "cripto", "risco", "retorno", "liquidez", "fundo",
    "tesouro", "cdb", "lci", "lca", "empresa", "preço", "preco", "dólar", "dolar",
    "reserva", "poupança", "poupanca",
}
ORIENTATION_TERMS = {
    "cite", "exemplo", "exemplos", "qual escolher", "quais escolher", "como escolher",
    "mais seguro", "mais seguros", "melhor investimento", "melhores investimentos",
    "ativos seguros", "investimentos seguros", "opcoes seguras", "opções seguras",
    "onde investir", "recomenda", "recomendacao", "indique", "indicacao",
}
TRANSACTIONAL_PATTERN = re.compile(
    r"\b(compre|venda|mantenha|aumente (?:a )?posi[cç][aã]o|reduza (?:a )?posi[cç][aã]o|"
    r"deve comprar|deve vender|hora de comprar|hora de vender)\b",
    flags=re.IGNORECASE,
)
UNSAFE_GUARANTEE_PATTERN = re.compile(
    r"\b(?:e|sao) (?:totalmente |100% )?segur[oa]s?\b|\bgarante? (?:lucro|retorno|rentabilidade)\b|"
    r"\bretorno garantido\b",
    flags=re.IGNORECASE,
)


class ChatService:
    def __init__(self, knowledge: KnowledgeService | None = None):
        self.ai_enabled = AI_ENABLE_CHATBOT
        self.llm = LLMService()
        self.assets = AssetUniverseService()
        self.news = NewsIngestionService()
        self.semantic_news = NewsSemanticService()
        self.knowledge = knowledge or KnowledgeService()

    def answer(
        self,
        messages: list[ChatInputMessage],
        active_portfolio: Portfolio | None = None,
        consolidated_portfolios: list[Portfolio] | None = None,
        conversation_summary: str = "",
    ) -> dict:
        question = next((msg.content for msg in reversed(messages) if msg.role == "user"), "").strip()
        portfolio_context = self._build_portfolio_context(active_portfolio, consolidated_portfolios or [])
        intent = self._classify_intent(question, messages, portfolio_context)
        if self._is_safe_orientation(question, intent):
            by_id = {item["id"]: item for item in self.knowledge.load_documents()}
            knowledge_context = [
                {**by_id[item_id], "similarity": None, "exact_match": False, "direct_match": False}
                for item_id in ("risco-retorno", "tesouro-selic", "cdb", "fgc")
                if item_id in by_id
            ]
        else:
            knowledge_context = self.knowledge.search(question, limit=4)
        if intent in {"ativo", "temporal"}:
            anchors = {"preco-empresa", "noticias-preco", "fonte-oficial"}
            by_id = {item["id"]: item for item in self.knowledge.load_documents()}
            anchored = [
                {**by_id[item_id], "similarity": None, "exact_match": False, "direct_match": False}
                for item_id in ("preco-empresa", "noticias-preco", "fonte-oficial")
                if item_id in by_id
            ]
            knowledge_context = anchored + [item for item in knowledge_context if item["id"] not in anchors]
            knowledge_context = knowledge_context[:4]
        should_use_portfolio = intent == "carteira"
        if not should_use_portfolio:
            portfolio_context = {**portfolio_context, "has_context": False, "summary": "Contexto de carteira não solicitado."}
        news_context = self._news_context(question, portfolio_context) if intent in {"temporal", "ativo"} else []
        sources = self.knowledge.source_payload(knowledge_context)[:4] + self._news_sources(news_context)
        retrieval = {
            "intent": intent,
            "knowledge_count": len(knowledge_context),
            "news_count": len(news_context),
            "used_portfolio_context": portfolio_context["has_context"],
        }

        if self._is_safe_orientation(question, intent):
            return {
                "message": self._fallback_answer(question, intent, knowledge_context, news_context, portfolio_context),
                "mode": "knowledge_direct",
                "used_portfolio_context": False,
                "sources": sources,
                "retrieval": retrieval,
            }

        if self._is_direct_question(question, intent, knowledge_context):
            direct_sources = self.knowledge.source_payload(knowledge_context[:1])[:2]
            return {
                "message": self.knowledge.render_direct_answer(knowledge_context[0]),
                "mode": "knowledge_direct",
                "used_portfolio_context": False,
                "sources": direct_sources,
                "retrieval": retrieval,
            }

        if self.ai_enabled and intent != "fora_do_escopo":
            payload = {
                "intencao": intent,
                "pergunta_usuario": question,
                "base_conhecimento": [
                    {"titulo": item["title"], "resposta": item["short_answer"]}
                    for item in knowledge_context
                ],
                "noticias_recentes": [
                    {"titulo": item["title"], "resumo": item["summary"][:500], "fonte": item["source_name"]}
                    for item in news_context
                ],
                "contexto_carteira": portfolio_context,
                "resumo_conversa": conversation_summary,
                "historico_recente": [msg.model_dump() for msg in messages[-8:]],
                "politica_de_conhecimento": (
                    "Use conhecimento financeiro geral apenas para conceitos estaveis. "
                    "Para fatos atuais, numeros, tributacao ou regulacao, use somente o contexto fornecido "
                    "e declare quando nao houver base para confirmar."
                ),
            }
            complex_question = len(question.split()) > 12 or intent in {"orientacao", "carteira", "ativo", "temporal", "continuacao"}
            user_prompt = (
                "Use os dados abaixo como contexto, sem repetir o JSON.\n\n"
                f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
                f"TAREFA FINAL: responda diretamente à pergunta ‘{question}’. "
                + (
                    "Desenvolva a resposta na profundidade necessaria, usando paragrafos, subtitulos ou listas somente quando ajudarem."
                    if complex_question
                    else "Responda de forma natural e objetiva. Inclua exemplo apenas se ele realmente ajudar."
                )
            )
            refined = self.llm.chat_answer(
                EDUCATIONAL_CHATBOT_PROMPT,
                user_prompt=user_prompt,
                temperature=0.15,
                max_tokens=700 if complex_question else 420,
            )
            minimum_length = 180 if complex_question else 100
            is_echo = bool(refined and normalize_text(refined).strip("?.!") == normalize_text(question).strip("?.!"))
            placeholders = (
                "resumo da resposta", "explicacao detalhada", "riscos identificados",
                "limitacoes da analise", "fatos a serem acompanhados",
            )
            is_placeholder = bool(refined and any(item in normalize_text(refined) for item in placeholders))
            if (
                refined and len(refined) >= minimum_length and not is_echo and not is_placeholder
                and not TRANSACTIONAL_PATTERN.search(refined)
                and not UNSAFE_GUARANTEE_PATTERN.search(refined)
            ):
                return {
                    "message": refined.strip(),
                    "mode": "llm",
                    "used_portfolio_context": portfolio_context["has_context"],
                    "sources": sources,
                    "retrieval": retrieval,
                }

        return {
            "message": self._fallback_answer(question, intent, knowledge_context, news_context, portfolio_context),
            "mode": "fallback",
            "used_portfolio_context": portfolio_context["has_context"],
            "sources": sources,
            "retrieval": retrieval,
        }

    def _classify_intent(self, question: str, messages: list[ChatInputMessage], portfolio: dict) -> str:
        normalized = normalize_text(question)
        if any(term in normalized for term in PORTFOLIO_TERMS):
            return "carteira"
        tickers = {asset.ticker.lower() for asset in self.assets.get_all()}
        words = set(re.findall(r"[a-z0-9]+", normalized))
        if tickers.intersection(words) or re.search(r"\b[A-Z]{4}\d{1,2}\b", question):
            return "ativo"
        if any(term in normalized for term in TEMPORAL_TERMS):
            return "temporal"
        if len(messages) > 1 and any(normalized.startswith(term) for term in ("e ", "mas ", "por que", "entao", "isso", "nesse caso")):
            return "continuacao"
        is_financial = any(term in normalized for term in FINANCE_TERMS)
        if is_financial and any(term in normalized for term in ORIENTATION_TERMS):
            return "orientacao"
        if is_financial:
            return "conceitual"
        return "fora_do_escopo"

    @staticmethod
    def _is_direct_question(question: str, intent: str, knowledge: list[dict]) -> bool:
        return bool(
            intent == "conceitual" and knowledge and knowledge[0]["exact_match"]
            and len(question.split()) <= 14
        )

    @staticmethod
    def _is_safe_orientation(question: str, intent: str) -> bool:
        normalized = normalize_text(question)
        return intent == "orientacao" and any(
            term in normalized for term in ("seguro", "segura", "seguranca")
        )

    @staticmethod
    def _canonical_url(url: str) -> str:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))

    def _news_context(self, question: str, portfolio_context: dict) -> list[dict]:
        all_news = self.news.get_all_raw()
        if not question or not all_news:
            return []
        query = " ".join([question, " ".join(portfolio_context.get("top_assets", []))]).strip()
        ranked, _, _ = self.semantic_news.hybrid_search(all_news, query, search_mode="hybrid")
        selected = []
        seen_urls = set()
        seen_titles = set()
        for news in ranked:
            canonical = self._canonical_url(news.source_url)
            title_key = normalize_text(news.title)
            if not canonical or canonical in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(canonical)
            seen_titles.add(title_key)
            selected.append({
                "id": news.id, "title": news.title, "summary": news.summary,
                "source_name": news.source_name, "source_url": news.source_url,
                "published_at": news.published_at.isoformat(), "similarity": None,
            })
            if len(selected) == 3:
                break
        return selected

    @staticmethod
    def _news_sources(news_context: list[dict]) -> list[dict]:
        return [
            {
                "id": item["id"], "type": "news", "title": item["title"],
                "source_name": item["source_name"], "source_url": item["source_url"],
                "published_at": item["published_at"], "similarity": item.get("similarity"),
            }
            for item in news_context
        ]

    def _build_portfolio_context(self, active_portfolio: Portfolio | None, portfolios: list[Portfolio]) -> dict:
        target = portfolios or ([active_portfolio] if active_portfolio else [])
        positions = [position for portfolio in target for position in portfolio.positions]
        if not positions:
            return {"has_context": False, "summary": "Sem carteira suficiente para comentário contextual.", "top_assets": [], "class_distribution": {}}
        assets = {asset.ticker: asset for asset in self.assets.get_all()}
        top = sorted(positions, key=lambda pos: pos.quantity, reverse=True)[:5]
        classes = Counter(position.asset_class for position in positions)
        summary = ", ".join(
            f"{pos.ticker} ({assets.get(pos.ticker).name if assets.get(pos.ticker) else pos.ticker}, {pos.quantity:g} unidades)"
            for pos in top
        )
        return {"has_context": True, "summary": summary, "top_assets": [pos.ticker for pos in top], "class_distribution": dict(classes)}

    def _fallback_answer(self, question: str, intent: str, knowledge: list[dict], news: list[dict], portfolio: dict) -> str:
        if self._is_safe_orientation(question, intent):
            return (
                "Não existe investimento totalmente seguro: todo produto envolve ao menos risco de crédito, "
                "liquidez, mercado ou perda de poder de compra. Como referências educacionais de menor risco, "
                "dois exemplos comuns são:\n\n"
                "- **Tesouro Selic:** título público federal cuja rentabilidade acompanha a taxa Selic. Costuma "
                "ser usado quando liquidez e baixa oscilação são prioridades, embora a venda antecipada ocorra "
                "pelo preço de mercado.\n"
                "- **CDB elegível à cobertura do FGC:** título emitido por banco. O risco depende da instituição, "
                "do prazo e das regras e limites vigentes do FGC; também é preciso verificar se há liquidez antes "
                "do vencimento.\n\n"
                "A comparação adequada depende do prazo do objetivo, da necessidade de resgate, da tributação e "
                "do risco do emissor. Esses exemplos não representam uma indicação personalizada de investimento."
            )
        if intent in {"ativo", "temporal"} and news:
            news_lines = []
            for item in news:
                detail = (item.get("summary") or "").strip()
                if detail:
                    detail = detail.split(". ", 1)[0].rstrip(".") + "."
                else:
                    detail = "A manchete foi recuperada como contexto, mas o resumo disponível é insuficiente."
                news_lines.append(f"- **{item['title']}**: {detail}")
            concepts = "\n".join(
                f"- **{item['title']}**: {item['short_answer']}" for item in knowledge[:3]
            )
            interpretation = (
                "\n\n## Como interpretar\n" + concepts
                if concepts else ""
            )
            return (
                "## Resumo\n"
                "A leitura recente depende de separar o desempenho da empresa, a expectativa já incorporada no preço "
                "e os eventos divulgados. As fontes abaixo ajudam a identificar temas relevantes, mas não provam "
                "isoladamente a causa de um movimento da ação.\n\n"
                "## Fatores recentes encontrados\n" + "\n".join(news_lines) + interpretation + "\n\n"
                "## Riscos e limitações\n"
                "- Notícias podem mencionar o ativo apenas como comparação ou repetir o mesmo evento sob ângulos diferentes.\n"
                "- Preço, resultados da empresa e impacto da posição na carteira devem ser avaliados separadamente.\n"
                "- O contexto pode mudar com novos resultados, decisões de juros, dados de crédito ou comunicados oficiais.\n\n"
                "## O que acompanhar\n"
                "Confirme os fatos nas fontes primárias, observe se os eventos alteram lucro, risco, crédito ou expectativas "
                "e compare a reação do ativo com seu setor e com o mercado no mesmo período."
            )
        if knowledge:
            sections = [self.knowledge.render_direct_answer(knowledge[0])]
            if portfolio["has_context"]:
                sections.append(f"## Relação com a carteira\nNo contexto disponível, as principais posições são {portfolio['summary']}. Essa composição deve ser lida junto com concentração, classes e objetivo, sem transformar o diagnóstico em ordem de transação.")
            if news:
                sections.append("## Contexto recente\nAs notícias relacionadas podem atualizar o cenário, mas não substituem a análise dos dados e das fontes primárias.")
            return "\n\n".join(sections)
        if intent == "carteira":
            return portfolio["summary"] if portfolio["has_context"] else "Ainda não há uma carteira disponível para contextualizar a pergunta. Posso explicar conceitos financeiros gerais enquanto isso."
        if intent == "fora_do_escopo":
            return "Posso ajudar com investimentos, economia, riscos, análise de ativos e interpretação da carteira. Reformule a pergunta dentro desses temas para eu usar a base financeira do Operum."
        return "Não encontrei base suficiente para responder com segurança. Tente incluir o conceito, ativo, período ou contexto que deseja analisar."

    def summarize_conversation(self, messages: list[ChatInputMessage]) -> str | None:
        if not self.ai_enabled or len(messages) < 12:
            return None
        payload = json.dumps([msg.model_dump() for msg in messages[-12:]], ensure_ascii=False)
        return self.llm.chat_answer(
            "Resuma a conversa financeira em um único parágrafo factual de até 120 palavras. Preserve dúvidas abertas e não crie informações. /no_think",
            payload, temperature=0, max_tokens=180,
        )
