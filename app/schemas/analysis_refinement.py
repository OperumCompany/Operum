"""Internal text-only contracts for analysis refinement."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


class Refinement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AssetRefinement(Refinement):
    historico: Text
    situacaoAtual: Text
    perspectiva: Text


class BlockRefinement(Refinement):
    title: Text
    assessment: Text
    highlights: Text


class PortfolioRefinement(Refinement):
    headline: Text
    composition_summary: Text
    final_diagnosis: Text
    conclusion: Text
    strengths: list[Text]
    overlaps: list[Text]
    block_reviews: list[BlockRefinement]
