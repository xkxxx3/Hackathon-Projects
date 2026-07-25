"""MBTI rule engine.

Pipeline (per docs/喵格MBTI映射规则.md):

    video → gemini_client.extract_signals_via_gemini → BehaviorSignals
    BehaviorSignals → weighted scoring per signals.SCORING_TABLE
    per-axis (right, left) scores → tiebreaker → 4-letter MBTI

Fallbacks:
- No GEMINI_API_KEY set         → deterministic hash-based stub (dev mode).
- Gemini call fails             → ISFP (per doc §4 兜底).
- Overall confidence below min  → ISFP.
"""
from __future__ import annotations

import hashlib
import logging
import random
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core import gemini_client
from app.core.signals import (
    SCORING_TABLE,
    TIE_THRESHOLD,
    BehaviorSignals,
)
from app.models.schemas import (
    Axis,
    DimensionScore,
    HighlightClip,
    MBTIReport,
    MBTIType,
)

if TYPE_CHECKING:
    from app.core.video_frames import FrameBundle

logger = logging.getLogger(__name__)


# 16 型猫格档案 — 昵称/关键词严格对齐 docs/喵格MBTI映射规则.md §2
TYPE_PROFILE: dict[MBTIType, tuple[str, str, list[str]]] = {
    "INTJ": ("战略家猫", "高处俯瞰一切的孤狼,不轻易出手。", ["高冷", "计划", "独立"]),
    "INTP": ("哲学家猫", "长时间凝视虚空,对新事物冷静研究。", ["发呆", "思考", "好奇"]),
    "ENTJ": ("老板猫", "家里它最大,逗猫棒它说了算。", ["强势", "领地感", "果断"]),
    "ENTP": ("话痨猫", "喵喵不停,见谁都想搞点事。", ["调皮", "社交", "爱挑事"]),
    "INFJ": ("神秘主义猫", "默默陪伴,看穿你的情绪但不说。", ["安静", "敏感", "深情"]),
    "INFP": ("艺术家猫", "纸箱诗人,藏在小角落发呆。", ["内向", "温柔", "易感"]),
    "ENFJ": ("暖男猫", "主人难过它就会过来蹭。", ["主动关怀", "亲人", "治愈"]),
    "ENFP": ("阳光猫", "见谁都贴贴,对什么都感兴趣。", ["热情", "好奇", "外向"]),
    "ISTJ": ("老干部猫", "准点吃饭准点睡,作息精准如表。", ["规律", "稳重", "传统"]),
    "ISFJ": ("居家猫", "不爱出门,对主人忠心耿耿。", ["温顺", "恋家", "害羞"]),
    "ESTJ": ("队长猫", "别的猫吵架它先冲上去管。", ["自律", "控场", "爱管"]),
    "ESFJ": ("社牛猫", "来客人比谁都兴奋,自带聚光灯。", ["热情", "合群", "爱被夸"]),
    "ISTP": ("工匠猫", "默默拆家,研究每一个角落。", ["冷静", "动手派", "探索"]),
    "ISFP": ("文艺猫", "喜欢晒太阳,慢节奏地享受生活。", ["温柔", "随性", "爱美"]),
    "ESTP": ("冒险家猫", "飞檐走壁,五米起跳的运动派。", ["敏捷", "刺激", "好动"]),
    "ESFP": ("戏精猫", "看见手机就开始营业的表演型选手。", ["表演型", "爱镜头", "享乐"]),
}


def _axis_score(sig: BehaviorSignals, axis: Axis) -> tuple[float, float]:
    cfg = SCORING_TABLE[axis]
    right = sum(getattr(sig, k) * w for k, w in cfg["right_signals"])
    left  = sum(getattr(sig, k) * w for k, w in cfg["left_signals"])
    return float(right), float(left)


def _pick_pole(axis: Axis, right: float, left: float) -> str:
    """Pick winning pole; on tie return the doc-defined default pole."""
    cfg = SCORING_TABLE[axis]
    if abs(right - left) <= TIE_THRESHOLD:
        return cfg["default_pole"]
    return cfg["right_pole"] if right > left else cfg["left_pole"]


def _display_score(right: float, left: float) -> float:
    """0–100, where 100 means fully on the right pole side."""
    total = right + left
    if total <= 0:
        return 50.0
    return round(100 * right / total, 1)


def _build_dimensions(sig: BehaviorSignals) -> tuple[MBTIType, list[DimensionScore]]:
    code = ""
    dims: list[DimensionScore] = []
    for axis in ("EI", "SN", "TF", "JP"):
        cfg = SCORING_TABLE[axis]
        right, left = _axis_score(sig, axis)  # type: ignore[arg-type]
        code += _pick_pole(axis, right, left)  # type: ignore[arg-type]
        dims.append(DimensionScore(
            axis=axis,  # type: ignore[arg-type]
            score=_display_score(right, left),
            label_left=cfg["label_left"],
            label_right=cfg["label_right"],
        ))
    return code, dims  # type: ignore[return-value]


def _stub_signals(seed_hint: str | None) -> BehaviorSignals:
    """Deterministic stub for dev environments without an API key."""
    seed_src = seed_hint or "default-demo"
    seed = int(hashlib.md5(seed_src.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    fields = BehaviorSignals.model_fields
    data: dict = {
        name: rng.randint(0, 3)
        for name in fields
        if not name.startswith("confidence_") and name != "notes" and name != "highlights"
    }
    data["confidence_ei"] = 0.8
    data["confidence_sn"] = 0.8
    data["confidence_tf"] = 0.8
    data["confidence_jp"] = 0.6
    data["notes"] = "本地 stub 数据(未调用 Gemini)"
    data["highlights"] = []
    return BehaviorSignals(**data)


def _build_highlights(sig: BehaviorSignals) -> list[HighlightClip]:
    """Use the model's own timestamped highlights when available; fall back to
    the single-sentence note for older outputs that don't include them."""
    if sig.highlights:
        return [
            HighlightClip(
                start_sec=h.time_sec,
                end_sec=h.time_sec,  # point-in-time, not a range
                caption=h.caption,
            )
            for h in sig.highlights if h.caption
        ]
    if sig.notes:
        return [HighlightClip(start_sec=0.0, end_sec=0.0, caption=sig.notes)]
    return []


def _avg_confidence(sig: BehaviorSignals) -> float:
    return (sig.confidence_ei + sig.confidence_sn
            + sig.confidence_tf + sig.confidence_jp) / 4


def _format_error(exc: BaseException) -> str:
    """Distill an LLM exception into one user-visible line.

    OpenAI SDK errors carry the upstream proxy's JSON body in `.body`; pull
    out `error.message` if present, otherwise fall back to str(exc).
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return f"AI 分析失败 · {err['message']}"
    msg = str(exc).strip()
    if len(msg) > 200:
        msg = msg[:200] + "…"
    return f"AI 分析失败 · {msg or type(exc).__name__}"


def _fallback_report(reason: str) -> MBTIReport:
    """Doc §4 兜底: low info → ISFP (文艺猫)."""
    mbti: MBTIType = "ISFP"
    nickname, summary, tags = TYPE_PROFILE[mbti]
    dims = [
        DimensionScore(axis=axis, score=score,  # type: ignore[arg-type]
                       label_left=SCORING_TABLE[axis]["label_left"],
                       label_right=SCORING_TABLE[axis]["label_right"])
        for axis, score in (("EI", 40), ("SN", 40), ("TF", 60), ("JP", 40))
    ]
    return MBTIReport(
        mbti=mbti,
        nickname=nickname,
        summary=summary,
        tags=tags,
        dimensions=dims,
        highlights=[HighlightClip(start_sec=0.0, end_sec=0.0,
                                  caption=f"兜底输出 · {reason}")],
        confidence=0.0,
    )


def build_report_streaming(
    bundle: "FrameBundle | None" = None,
    seed_hint: str | None = None,
):
    """Streaming variant of :func:`build_report` — yields progress events,
    returns the final :class:`MBTIReport`.

    Capture the result via ``yield from`` in an outer generator, or use the
    sync wrapper :func:`build_report` which drains it.
    """
    try:
        if gemini_client.is_enabled() and bundle is not None:
            signals = yield from gemini_client.extract_signals_streaming(bundle)
        else:
            logger.info("gemini disabled or no frames; using stub signals")
            yield {"event": "stub", "message": "本地 stub 模式(未调用 AI)"}
            signals = _stub_signals(seed_hint)
    except Exception as exc:  # noqa: BLE001 — doc §4 兜底
        logger.exception("gemini analysis failed; falling back to ISFP")
        reason = _format_error(exc)
        yield {"event": "warn", "message": f"AI 失败 · 走 ISFP 兜底",
               "data": {"reason": reason}}
        return _fallback_report(reason)

    confidence = _avg_confidence(signals)
    if confidence < settings.gemini_min_confidence:
        logger.info("low confidence %.2f, falling back to ISFP", confidence)
        yield {"event": "warn", "message": "置信度不足 · 走 ISFP 兜底",
               "data": {"confidence": confidence}}
        return _fallback_report("视频信息量不足,建议重新上传")

    yield {"event": "scoring", "message": "规则引擎打分",
           "data": {"confidence": round(confidence, 2)}}

    mbti, dims = _build_dimensions(signals)
    nickname, summary, tags = TYPE_PROFILE[mbti]

    return MBTIReport(
        mbti=mbti,
        nickname=nickname,
        summary=summary,
        tags=tags,
        dimensions=dims,
        highlights=_build_highlights(signals),
        confidence=round(confidence, 2),
    )


def build_report(
    bundle: "FrameBundle | None" = None,
    seed_hint: str | None = None,
) -> MBTIReport:
    """Synchronous drain-wrapper for callers that don't need progress events."""
    gen = build_report_streaming(bundle, seed_hint)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value
