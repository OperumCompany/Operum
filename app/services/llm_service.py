import json
import logging
import re
from typing import Any

import httpx

from app.core.config import AI_API_KEY, AI_BASE_URL, AI_ENABLED, AI_MODEL, AI_PROVIDER, AI_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.enabled = AI_ENABLED
        self.provider = AI_PROVIDER
        self.base_url = AI_BASE_URL
        self.api_key = AI_API_KEY
        self.model = AI_MODEL
        self.timeout_seconds = AI_TIMEOUT_SECONDS

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "reachable": self.is_reachable(),
        }

    def is_reachable(self) -> bool:
        if not self.enabled:
            return False
        try:
            with httpx.Client(timeout=min(self.timeout_seconds, 5.0)) as client:
                response = client.get(f"{self.base_url.removesuffix('/v1')}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 900,
    ) -> str | None:
        if not self.enabled:
            return None

        if self.provider == "ollama":
            return self._ollama_chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content")
        except Exception as exc:
            logger.warning("Falha na chamada ao provedor de IA local: %s", exc)
            return None

    def chat_answer(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 700,
    ) -> str | None:
        """Return a user-facing answer without exposing Qwen's reasoning stream."""
        if not self.enabled:
            return None
        if self.provider != "ollama":
            return self.chat_completion(system_prompt, user_prompt, temperature, max_tokens)
        schema = {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "Resposta final em Markdown natural, direta e adaptada à pergunta.",
                },
            },
            "required": ["answer"],
            "additionalProperties": False,
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{system_prompt.rstrip()}\n"
                        "Preencha answer com a resposta final em português brasileiro. Comece respondendo diretamente "
                        "à pergunta e use Markdown somente quando melhorar a leitura. Não imponha seções fixas, não copie "
                        "a pergunta e não exponha raciocínio ou descrições do schema."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            "format": schema,
            "stream": False,
            "think": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url.removesuffix('/v1')}/api/chat", json=payload)
                response.raise_for_status()
                content = response.json().get("message", {}).get("content", "")
                parsed = json.loads(content)
                answer = str(parsed.get("answer", "")).strip()
                return answer if answer and self._is_user_facing_answer(answer) else None
        except Exception as exc:
            logger.warning("Falha na resposta estruturada do Ollama: %s", exc)
            return None

    def _ollama_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str | None:
        system_message, user_message = self._prepare_ollama_messages(system_prompt, user_prompt)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url.removesuffix('/v1')}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                message = data.get("message", {}) if isinstance(data, dict) else {}
                content = (message.get("content") or "").strip()
                if content:
                    normalized = self._normalize_possible_reasoning(content)
                    if normalized:
                        if self._looks_like_reasoning_or_meta(normalized):
                            cleaned = self._cleanup_ollama_output(normalized)
                            if cleaned and self._is_user_facing_answer(cleaned):
                                return cleaned
                        if self._is_user_facing_answer(normalized):
                            return normalized

                reasoning = (
                    message.get("thinking")
                    or message.get("reasoning")
                    or data.get("thinking")
                    or data.get("reasoning")
                    or ""
                )
                extracted = self._extract_useful_answer(reasoning)
                if extracted:
                    logger.info("Resposta final extraida do reasoning do modelo %s", self.model)
                    if self._looks_like_reasoning_or_meta(extracted):
                        cleaned = self._cleanup_ollama_output(extracted)
                        if cleaned and self._is_user_facing_answer(cleaned):
                            return cleaned
                    if self._is_user_facing_answer(extracted):
                        return extracted
                return None
        except Exception as exc:
            logger.warning("Falha na chamada ao Ollama local: %s", exc)
            return None

    def chat_json(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 900,
    ) -> dict[str, Any] | None:
        prompt = json.dumps(user_payload, ensure_ascii=False, indent=2)
        raw = self.chat_completion(system_prompt, prompt, temperature=temperature, max_tokens=max_tokens)
        if not raw:
            return None
        try:
            return self._extract_json(raw)
        except Exception as exc:
            logger.warning("Retorno JSON invalido da IA local: %s", exc)
            return None

    def _extract_json(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("JSON nao encontrado")
        return json.loads(text[start : end + 1])

    def _extract_useful_answer(self, reasoning: str) -> str | None:
        if not reasoning:
            return None

        text = reasoning.strip()

        tagged = re.search(r"<final>(.*?)</final>", text, flags=re.IGNORECASE | re.DOTALL)
        if tagged:
            candidate = tagged.group(1).strip()
            if candidate:
                return candidate

        try:
            parsed = self._extract_json(text)
            return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            pass

        quote_patterns = [
            r'(?:answer should be|the answer is|final answer|resposta deve ser|a resposta deve ser)\s*:\s*"([^"]+)"',
            r"(?:answer should be|the answer is|final answer|resposta deve ser|a resposta deve ser)\s*:\s*'([^']+)'",
            r'(?:something like|algo como|it should be something like)\s*:\s*"([^"]+)"',
            r"(?:something like|algo como|it should be something like)\s*:\s*'([^']+)'",
        ]
        for pattern in quote_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                if candidate:
                    return candidate

        line_patterns = [
            r"(?:answer should be|the answer is|final answer|resposta deve ser|a resposta deve ser)\s*:\s*(.+)",
        ]
        for pattern in line_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1).strip().strip('"').strip("'")
                candidate = candidate.split("\n", 1)[0].strip()
                if candidate:
                    return candidate

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        answer_like = [
            line
            for line in lines
            if len(line) >= 20
            and not line.lower().startswith(("okay", "wait", "first", "so,", "hmm", "let me", "but ", "the user"))
            and not line.endswith("?")
        ]
        for candidate in reversed(answer_like):
            if any(token in candidate for token in ["{", "}", "[", "]"]):
                continue
            return candidate.strip('"').strip("'")

        return None

    def _normalize_possible_reasoning(self, content: str) -> str | None:
        text = content.strip()
        if not text:
            return None

        quoted_candidates = re.findall(r'["“](.{20,}?)["”]', text, flags=re.DOTALL)
        if quoted_candidates:
            best = max((candidate.strip() for candidate in quoted_candidates if candidate.strip()), key=len, default="")
            if best:
                return best

        lowered = text.lower()
        reasoning_markers = [
            "let me think",
            "the user wants me",
            "first,",
            "wait,",
            "it should be something like",
            "a resposta deve ser",
            "algo como",
            "alternatively,",
        ]
        if any(marker in lowered for marker in reasoning_markers):
            extracted = self._extract_useful_answer(text)
            if extracted:
                return extracted
        return text

    def _prepare_ollama_messages(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        if "qwen" in self.model.lower():
            system_message = (
                f"{system_prompt.rstrip()} /no_think "
                "Responda apenas com a resposta final. "
                "Nao exponha raciocinio, etapas intermediarias ou preambulos."
            )
            user_message = f"/no_think {user_prompt.lstrip()}"
            return system_message, user_message
        return system_prompt, user_prompt

    def _looks_like_reasoning_or_meta(self, text: str) -> bool:
        lowered = text.lower()
        markers = [
            "let me think",
            "the user wants",
            "i need to avoid",
            "first,",
            "wait,",
            "alternatively,",
            "it should be",
            "so,",
            "so the answer should be",
            "without any reasoning",
        ]
        return any(marker in lowered for marker in markers)

    def _cleanup_ollama_output(self, text: str) -> str | None:
        cleanup_system, cleanup_user = self._prepare_ollama_messages(
            "Extraia somente a resposta final ao usuario em PT-BR. Remova raciocinio, frases em ingles e preambulos. Nao invente informacoes.",
            f"Texto bruto do modelo:\n{text}\n\nDevolva apenas a resposta final limpa em PT-BR.",
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": cleanup_system},
                {"role": "user", "content": cleanup_user},
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0,
                "num_predict": 180,
            },
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url.removesuffix('/v1')}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                message = data.get("message", {}) if isinstance(data, dict) else {}
                content = (message.get("content") or "").strip()
                if content and not self._looks_like_reasoning_or_meta(content):
                    normalized = self._normalize_possible_reasoning(content)
                    if normalized and self._is_user_facing_answer(normalized):
                        return normalized

                reasoning = (
                    message.get("thinking")
                    or message.get("reasoning")
                    or data.get("thinking")
                    or data.get("reasoning")
                    or ""
                )
                extracted = self._extract_useful_answer(reasoning or content)
                if extracted and not self._looks_like_reasoning_or_meta(extracted) and self._is_user_facing_answer(extracted):
                    return extracted
        except Exception as exc:
            logger.warning("Falha no segundo passe de limpeza do Ollama: %s", exc)
        return None

    def _is_user_facing_answer(self, text: str) -> bool:
        candidate = text.strip()
        if not candidate:
            return False
        if self._looks_like_reasoning_or_meta(candidate):
            return False
        blocked_prefixes = (
            "okay,",
            "first,",
            "wait,",
            "alternatively,",
            "the correct definition",
            "i need to",
            "the user wants",
        )
        lowered = candidate.lower()
        if lowered.startswith(blocked_prefixes):
            return False
        return True
