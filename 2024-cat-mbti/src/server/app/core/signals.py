"""Behavior signals schema + scoring weights.

Signal taxonomy mirrors docs/喵格MBTI映射规则.md §1.
Weights mirror docs/喵格MBTI映射规则.md §3.
Tiebreaker default poles mirror §1 (each axis spells out the default).

Keep this file adjacent to mbti.py so doc-vs-code drift is easy to audit.
"""
from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class SignalHighlight(BaseModel):
    time_sec: float = Field(ge=0, default=0.0)
    caption: str = ""


class BehaviorSignals(BaseModel):
    """Per-signal intensity 0–3 (0 = not observed, 3 = strongly observed)."""

    # E / I
    approach_camera_or_person: int = Field(ge=0, le=3, default=0)
    excited_to_stimuli:        int = Field(ge=0, le=3, default=0)
    hide_from_stimuli:         int = Field(ge=0, le=3, default=0)
    vocal_frequent:            int = Field(ge=0, le=3, default=0)
    vocal_silent:              int = Field(ge=0, le=3, default=0)
    wide_exploration:          int = Field(ge=0, le=3, default=0)
    stay_in_corner:            int = Field(ge=0, le=3, default=0)
    enjoy_petting:             int = Field(ge=0, le=3, default=0)
    avoid_petting:             int = Field(ge=0, le=3, default=0)

    # S / N
    direct_pounce:                    int = Field(ge=0, le=3, default=0)
    observe_before_act:               int = Field(ge=0, le=3, default=0)
    chases_invisible:                 int = Field(ge=0, le=3, default=0)
    short_staring:                    int = Field(ge=0, le=3, default=0)
    long_staring_distant:             int = Field(ge=0, le=3, default=0)
    sniff_new_object:                 int = Field(ge=0, le=3, default=0)
    observe_new_object_from_distance: int = Field(ge=0, le=3, default=0)
    repetitive_behavior:              int = Field(ge=0, le=3, default=0)

    # T / F
    nuzzle_frequent:        int = Field(ge=0, le=3, default=0)
    nuzzle_rare:            int = Field(ge=0, le=3, default=0)
    self_play_when_ignored: int = Field(ge=0, le=3, default=0)
    meow_when_ignored:      int = Field(ge=0, le=3, default=0)
    long_eye_contact:       int = Field(ge=0, le=3, default=0)
    short_eye_contact:      int = Field(ge=0, le=3, default=0)
    alone_adapts_well:      int = Field(ge=0, le=3, default=0)
    alone_distressed:       int = Field(ge=0, le=3, default=0)
    emotional_reactions:    int = Field(ge=0, le=3, default=0)

    # J / P
    fixed_sleep_location:      int = Field(ge=0, le=3, default=0)
    random_sleep_location:     int = Field(ge=0, le=3, default=0)
    regular_meal_time:         int = Field(ge=0, le=3, default=0)
    irregular_meal_time:       int = Field(ge=0, le=3, default=0)
    long_term_toy_preference:  int = Field(ge=0, le=3, default=0)
    novelty_seeking_toys:      int = Field(ge=0, le=3, default=0)
    sensitive_to_env_change:   int = Field(ge=0, le=3, default=0)
    indifferent_to_env_change: int = Field(ge=0, le=3, default=0)
    few_sudden_bursts:         int = Field(ge=0, le=3, default=0)
    many_sudden_bursts:        int = Field(ge=0, le=3, default=0)

    # Per-axis observability confidence (0–1).
    confidence_ei: float = Field(ge=0, le=1, default=0.5)
    confidence_sn: float = Field(ge=0, le=1, default=0.5)
    confidence_tf: float = Field(ge=0, le=1, default=0.5)
    confidence_jp: float = Field(ge=0, le=1, default=0.5)

    # 2–3 salient moments with timestamps the model identified, used as the
    # report card's "视频高光时刻" section.
    highlights: list[SignalHighlight] = Field(default_factory=list)

    # Fallback one-sentence note when `highlights` is empty (older prompts /
    # models that don't follow the schema).
    notes: str = ""


class SignalHighlight(BaseModel):
    time_sec: float = Field(ge=0, default=0.0)
    caption: str = ""


class AxisDef(TypedDict):
    right_pole: str          # letter shown when right side wins (E/N/F/J)
    left_pole: str           # letter shown when left side wins  (I/S/T/P)
    default_pole: str        # used when |right_score - left_score| <= TIE_THRESHOLD
    right_signals: list[tuple[str, int]]
    left_signals: list[tuple[str, int]]
    label_left: str
    label_right: str


# Per docs/喵格MBTI映射规则.md §1: default pole is the one to fall back to
# when the score gap is too small (E/I → I, S/N → S, T/F → F, J/P → P).
SCORING_TABLE: dict[str, AxisDef] = {
    "EI": {
        "right_pole":  "E",
        "left_pole":   "I",
        "default_pole":"I",
        "right_signals": [
            ("approach_camera_or_person", 2),
            ("excited_to_stimuli", 2),
            ("vocal_frequent", 1),
            ("wide_exploration", 1),
            ("enjoy_petting", 1),
        ],
        "left_signals": [
            ("hide_from_stimuli", 2),
            ("vocal_silent", 1),
            ("stay_in_corner", 1),
            ("avoid_petting", 1),
        ],
        "label_left":  "慵懒宅家",
        "label_right": "活跃外向",
    },
    "SN": {
        "right_pole":  "N",
        "left_pole":   "S",
        "default_pole":"S",
        "right_signals": [
            ("observe_before_act", 2),
            ("chases_invisible", 2),
            ("long_staring_distant", 2),
            ("observe_new_object_from_distance", 1),
        ],
        "left_signals": [
            ("direct_pounce", 2),
            ("short_staring", 1),
            ("sniff_new_object", 1),
            ("repetitive_behavior", 1),
        ],
        "label_left":  "守旧务实",
        "label_right": "探索好奇",
    },
    "TF": {
        "right_pole":  "F",
        "left_pole":   "T",
        "default_pole":"F",
        "right_signals": [
            ("nuzzle_frequent", 2),
            ("meow_when_ignored", 2),
            ("long_eye_contact", 1),
            ("alone_distressed", 1),
            ("emotional_reactions", 1),
        ],
        "left_signals": [
            ("nuzzle_rare", 2),
            ("self_play_when_ignored", 2),
            ("short_eye_contact", 1),
            ("alone_adapts_well", 1),
        ],
        "label_left":  "冷静观察",
        "label_right": "情绪丰富",
    },
    "JP": {
        "right_pole":  "J",
        "left_pole":   "P",
        "default_pole":"P",
        "right_signals": [
            ("fixed_sleep_location", 2),
            ("regular_meal_time", 1),
            ("long_term_toy_preference", 1),
            ("sensitive_to_env_change", 1),
            ("few_sudden_bursts", 1),
        ],
        "left_signals": [
            ("random_sleep_location", 2),
            ("irregular_meal_time", 1),
            ("novelty_seeking_toys", 1),
            ("indifferent_to_env_change", 1),
            ("many_sudden_bursts", 2),
        ],
        "label_left":  "随机散漫",
        "label_right": "计划规律",
    },
}


# When |right - left| <= TIE_THRESHOLD, return the axis's default pole.
TIE_THRESHOLD = 2
