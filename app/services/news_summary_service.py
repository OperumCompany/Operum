import re


class NewsSummaryService:
    def _clean_noise(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = re.sub(r"The post .*? appeared first on .*?\.?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"Os sorteios ocorrem de segunda-feira a s[aá]bado\.?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"Leia tamb[eé]m:.*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"Assine.*$", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" -.")

    def _split_sentences(self, text: str) -> list[str]:
        if not text:
            return []
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) > 15]

    def _dedupe_sentences(self, sentences: list[str]) -> list[str]:
        seen = set()
        result = []
        for sentence in sentences:
            key = re.sub(r"[^a-z0-9]+", "", sentence.lower())
            if key in seen:
                continue
            seen.add(key)
            result.append(sentence)
        return result

    def _take_paragraph(self, sentences: list[str], min_chars: int, max_chars: int) -> str:
        chosen: list[str] = []
        total = 0
        for sentence in sentences:
            if total >= max_chars:
                break
            if chosen and total + len(sentence) + 1 > max_chars:
                break
            chosen.append(sentence)
            total += len(sentence) + 1
            if total >= min_chars:
                break
        paragraph = " ".join(chosen).strip()
        if paragraph and paragraph[-1] not in ".!?":
            paragraph += "."
        return paragraph

    def summarize(
        self,
        news_title: str,
        news_preview: str,
        mentioned_assets: list[str],
        mentioned_sectors: list[str] | None = None,
        full_text: str | None = None,
    ) -> str:
        title = self._clean_noise(news_title)
        preview = self._clean_noise(news_preview)
        body = self._clean_noise(full_text or "")

        pool = self._dedupe_sentences(
            self._split_sentences(". ".join(part for part in [preview, body] if part))
        )

        if not pool and title:
            pool = [title]

        first_paragraph = self._take_paragraph(pool, min_chars=120, max_chars=320)
        if not first_paragraph:
            first_paragraph = title
            if first_paragraph and first_paragraph[-1] not in ".!?":
                first_paragraph += "."

        remaining = [sentence for sentence in pool if sentence not in first_paragraph]
        assets_text = ""
        sectors_text = ""
        if mentioned_assets:
            assets_text = f"O texto menciona {', '.join(mentioned_assets[:3])}."
        if mentioned_sectors:
            sectors_text = f" O foco principal passa por {', '.join(mentioned_sectors[:2])}."

        second_paragraph = self._take_paragraph(remaining, min_chars=90, max_chars=260)
        if not second_paragraph:
            if assets_text or sectors_text:
                second_paragraph = f"{assets_text}{sectors_text}".strip()
            else:
                second_paragraph = "O impacto potencial depende da evolução do tema e da leitura do mercado sobre o fato."
        else:
            qualifier = ""
            if assets_text or sectors_text:
                qualifier = f" {assets_text}{sectors_text}".strip()
            if qualifier:
                second_paragraph = f"{second_paragraph} {qualifier}".strip()

        return f"{first_paragraph}\n\n{second_paragraph}".strip()
