from collections import Counter
import json

from app.core.config import AI_ENABLE_CHATBOT
from app.schemas.chat import ChatInputMessage
from app.schemas.portfolio import Portfolio
from app.services.asset_universe_service import AssetUniverseService
from app.services.llm_prompts import EDUCATIONAL_CHATBOT_PROMPT
from app.services.llm_service import LLMService


class ChatService:
    def __init__(self):
        self.ai_enabled = AI_ENABLE_CHATBOT
        self.llm = LLMService()
        self.assets = AssetUniverseService()

    def answer(
        self,
        messages: list[ChatInputMessage],
        active_portfolio: Portfolio | None = None,
        consolidated_portfolios: list[Portfolio] | None = None,
    ) -> dict:
        latest_user_message = next((msg.content for msg in reversed(messages) if msg.role == "user"), "")
        portfolio_context = self._build_portfolio_context(active_portfolio, consolidated_portfolios or [])

        if self.ai_enabled:
            payload = {
                "pergunta_usuario": latest_user_message,
                "regras_produto": {
                    "sem_recomendacao_transacional": True,
                    "usar_apenas_contexto_fornecido": True,
                    "explicitar_baixa_confianca_sem_base": True,
                },
                "contexto_carteira": portfolio_context,
                "historico_recente": [msg.model_dump() for msg in messages[-6:]],
            }
            refined = self.llm.chat_completion(
                EDUCATIONAL_CHATBOT_PROMPT,
                user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
                temperature=0.2,
                max_tokens=220,
            )
            if refined:
                return {
                    "message": refined.strip(),
                    "mode": "llm",
                    "used_portfolio_context": portfolio_context["has_context"],
                }

        return {
            "message": self._fallback_answer(latest_user_message, portfolio_context),
            "mode": "fallback",
            "used_portfolio_context": portfolio_context["has_context"],
        }

    def _build_portfolio_context(self, active_portfolio: Portfolio | None, portfolios: list[Portfolio]) -> dict:
        target_portfolios = portfolios or ([active_portfolio] if active_portfolio else [])
        positions = [position for portfolio in target_portfolios for position in portfolio.positions]
        if not positions:
            return {
                "has_context": False,
                "summary": "Sem carteira suficiente para comentario contextual.",
                "top_assets": [],
                "class_distribution": {},
            }

        assets = {asset.ticker: asset for asset in self.assets.get_all()}
        top_positions = sorted(positions, key=lambda pos: pos.quantity, reverse=True)[:5]
        class_distribution = Counter(position.asset_class for position in positions)
        summary = ", ".join(
            f"{pos.ticker} ({assets.get(pos.ticker).name if assets.get(pos.ticker) else pos.ticker}, {pos.quantity:g} unidades)"
            for pos in top_positions
        )
        return {
            "has_context": True,
            "summary": summary,
            "top_assets": [pos.ticker for pos in top_positions],
            "class_distribution": dict(class_distribution),
        }

    def _fallback_answer(self, text: str, portfolio_context: dict) -> str:
        normalized = text.lower()
        if "carteira" in normalized or "como esta" in normalized:
            if portfolio_context["has_context"]:
                return (
                    "Consigo fazer um comentario educativo com a carteira atual sem recomendar acao direta. "
                    f"Os maiores destaques no contexto recebido sao: {portfolio_context['summary']}."
                )
            return "Ainda nao ha carteira suficiente para um comentario contextual. Posso explicar conceitos gerais enquanto isso."
        if "renda variavel" in normalized:
            return "Renda variavel inclui ativos cujo preco oscila com mercado, resultados, liquidez, juros e expectativa futura."
        if "inflacao" in normalized:
            return "Inflacao e a alta geral de precos. Quando sobe, ela pressiona juros, poder de compra e a leitura de varios ativos."
        if "liquidez" in normalized:
            return "Liquidez e a facilidade de comprar ou vender um ativo sem causar perda relevante de preco."
        if any(term in normalized for term in ["acao", "acoes", "fii", "bdr", "cripto"]):
            return "Para interpretar um ativo, vale observar funcao na carteira, liquidez, risco, setor, historico recente e noticias relevantes."
        return "Posso explicar conceitos de mercado e, quando houver contexto suficiente, comentar a carteira de forma educativa e sem recomendacao transacional."
