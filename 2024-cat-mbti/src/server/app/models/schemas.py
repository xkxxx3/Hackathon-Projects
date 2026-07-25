from typing import Literal

from pydantic import BaseModel, Field

MBTIType = Literal[
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]

# Axis names follow MBTI convention: E/I, S/N, T/F, J/P.
# score >= 50 picks the right pole; right pole letters are E, N, F, J.
Axis = Literal["EI", "SN", "TF", "JP"]


class DimensionScore(BaseModel):
    axis: Axis
    score: float = Field(ge=0, le=100)
    label_left: str
    label_right: str


class HighlightClip(BaseModel):
    start_sec: float
    end_sec: float
    caption: str


class MBTIReport(BaseModel):
    mbti: MBTIType
    nickname: str
    summary: str
    tags: list[str]
    dimensions: list[DimensionScore]
    highlights: list[HighlightClip]
    confidence: float = Field(ge=0, le=1, default=1.0)


class AnalyzeResponse(BaseModel):
    analysis_id: str
    report: MBTIReport
    # Representative frame as `data:image/jpeg;base64,...`. The frontend keeps
    # this around so that POST /api/video/generate can hand it to Veo without
    # re-uploading the video.
    keyframe_data_url: str = ""


# -------- Video generation --------


class VideoScript(BaseModel):
    """Structured LLM output per docs/生成视频MBTI规则.md §7."""
    title: str
    mbti: MBTIType
    selected_profile_summary: str = ""
    theme_category: str = ""
    scene: str = ""
    expression_style: str = ""
    emotion_curve: str = ""
    setting: str = ""
    cat_visual_behavior: list[str] = Field(default_factory=list)
    spoken_script: str = ""
    shot_plan: list[str] = Field(default_factory=list)
    video_prompt: str
    negative_prompt: str = ""


class VideoGenerationRequest(BaseModel):
    mbti: MBTIType
    keyframe_data_url: str = ""           # may be empty in stub / no-key mode
    duration: int = Field(ge=5, le=15, default=8)
    cat_name: str = "你家猫"
    owner_name: str = "铲屎官"
    tone_preference: str = ""
    extra_traits: str = ""


class VideoGenerationResponse(BaseModel):
    script: VideoScript
    video_url: str
