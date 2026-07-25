// Mirrors backend Pydantic schemas in app/models/schemas.py.

export type MBTIType =
  | "INTJ" | "INTP" | "ENTJ" | "ENTP"
  | "INFJ" | "INFP" | "ENFJ" | "ENFP"
  | "ISTJ" | "ISFJ" | "ESTJ" | "ESFJ"
  | "ISTP" | "ISFP" | "ESTP" | "ESFP";

export type Axis = "EI" | "SN" | "TF" | "JP";

export interface DimensionScore {
  axis: Axis;
  score: number;
  label_left: string;
  label_right: string;
}

export interface HighlightClip {
  start_sec: number;
  end_sec: number;
  caption: string;
}

export interface MBTIReport {
  mbti: MBTIType;
  nickname: string;
  summary: string;
  tags: string[];
  dimensions: DimensionScore[];
  highlights: HighlightClip[];
  confidence: number;
}

export interface AnalyzeResponse {
  analysis_id: string;
  report: MBTIReport;
  keyframe_data_url: string;
}

// -------- Video generation --------

export interface VideoScript {
  title: string;
  mbti: MBTIType;
  selected_profile_summary: string;
  theme_category: string;
  scene: string;
  expression_style: string;
  emotion_curve: string;
  setting: string;
  cat_visual_behavior: string[];
  spoken_script: string;
  shot_plan: string[];
  video_prompt: string;
  negative_prompt: string;
}

export interface VideoGenerationRequest {
  mbti: MBTIType;
  keyframe_data_url: string;
  duration?: number;
  cat_name?: string;
  owner_name?: string;
  tone_preference?: string;
  extra_traits?: string;
}

export interface VideoGenerationResponse {
  script: VideoScript;
  video_url: string;
}

// Mirrors core.video_jobs.JobState. The frontend polls
// GET /api/video/status/{job_id} for this shape every couple of seconds.
export interface JobStatus {
  job_id: string;
  status: "running" | "done" | "error";
  phase: "script" | "render" | "done" | "error";

  script_chunks: number;
  script_size: number;
  render_chunks: number;
  render_size: number;
  poll_attempt: number;
  poll_elapsed_sec: number;

  // Filled after the script-writing stage completes. Subset of VideoScript.
  script: Partial<VideoScript> | null;

  // Set on terminal success.
  result: VideoGenerationResponse | null;

  // Set on terminal failure.
  error: string | null;
  upstream_body: any;
  exception_type: string | null;

  created_at: number;
  updated_at: number;
}
