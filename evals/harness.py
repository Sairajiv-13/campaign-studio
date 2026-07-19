"""Evaluation runner: score each labeled pair and compare to human preference."""

from __future__ import annotations

from typing import Any

from app.config import LlmMode, Settings
from app.domain.enums import Channel, Tone
from app.domain.models import BrandVoice, Variant
from app.llm.base import LlmPort
from app.llm.openai_compatible import OpenAICompatibleLlm
from app.llm.sandbox import SandboxLlm
from app.scoring.scorer import score_variant

from evals.dataset import PAIRS, EvalPair
from evals.metrics import EvalReport, PairResult


def build_llm(settings: Settings) -> LlmPort:
    if settings.llm_mode is LlmMode.REAL:
        return OpenAICompatibleLlm(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return SandboxLlm()


def _variant(slot: str, pair: EvalPair) -> Variant:
    channel = Channel(pair.channel)
    subject = getattr(pair, f"{slot}_subject") if channel is Channel.EMAIL else ""
    return Variant(
        id=f"{pair.id}-{slot}",
        segment_id=pair.id,
        channel=channel,
        subject=subject,
        body=getattr(pair, f"{slot}_body"),
    )


def _tone(value: str) -> Tone:
    try:
        return Tone(value)
    except ValueError:
        return Tone.FRIENDLY


async def evaluate(llm: LlmPort, pairs: list[EvalPair]) -> list[PairResult]:
    results: list[PairResult] = []
    for pair in pairs:
        brand_voice = BrandVoice(tone=_tone(pair.tone), banned_phrases=pair.banned)
        score_a = await score_variant(llm, _variant("a", pair), brand_voice, pair.traits)
        score_b = await score_variant(llm, _variant("b", pair), brand_voice, pair.traits)

        predicted = "a" if score_a.composite >= score_b.composite else "b"
        preferred_score = score_a if pair.preferred == "a" else score_b
        other_score = score_b if pair.preferred == "a" else score_a
        results.append(
            PairResult(
                id=pair.id,
                dimension=pair.dimension,
                predicted=predicted,
                preferred=pair.preferred,
                composite_preferred=preferred_score.composite,
                composite_other=other_score.composite,
            )
        )
    return results


def default_pairs() -> list[EvalPair]:
    return PAIRS


def format_report(report: EvalReport, results: list[PairResult]) -> str:
    lines = [
        "Scorer evaluation (pairwise ranking vs human preference)",
        "========================================================",
        f"pairs:            {report.n}",
        f"ranking accuracy: {report.accuracy:.1%}",
        f"mean margin:      {report.mean_margin:.3f}",
        "",
        "accuracy by lever:",
    ]
    for dim, acc in report.by_dimension.items():
        lines.append(f"  {dim:<16} {acc:.0%}")
    misses = [r for r in results if not r.correct]
    if misses:
        lines.append("")
        lines.append("misses: " + ", ".join(f"{r.id}({r.dimension})" for r in misses))
    return "\n".join(lines)


def to_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "pairs": report.n,
        "ranking_accuracy": round(report.accuracy, 4),
        "mean_margin": round(report.mean_margin, 4),
        "by_dimension": {k: round(v, 4) for k, v in report.by_dimension.items()},
    }
