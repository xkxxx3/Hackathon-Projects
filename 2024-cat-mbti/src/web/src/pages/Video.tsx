import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { generateVideo } from "@/api/client";
import { useAnalysisStore } from "@/store/analysis";
import type { JobStatus, VideoScript } from "@/types/api";

type Phase = "script" | "render" | "done" | "error";

interface Progress {
  phase: Phase;
  scriptChunks: number;
  scriptSize: number;
  renderChunks: number;
  renderSize: number;
  pollAttempt: number;
  pollElapsedSec: number;
  scriptPreview: VideoScript | null;
  error: string | null;
}

const initialProgress: Progress = {
  phase: "script",
  scriptChunks: 0,
  scriptSize: 0,
  renderChunks: 0,
  renderSize: 0,
  pollAttempt: 0,
  pollElapsedSec: 0,
  scriptPreview: null,
  error: null,
};

export default function VideoPage() {
  const nav = useNavigate();
  const analysis = useAnalysisStore((s) => s.analysis);
  const video = useAnalysisStore((s) => s.video);
  const setGeneratedVideo = useAnalysisStore((s) => s.setGeneratedVideo);

  const [prog, setProg] = useState<Progress>(initialProgress);

  useEffect(() => {
    if (!analysis) {
      nav("/", { replace: true });
      return;
    }
    if (video) return;

    let alive = true;
    setProg(initialProgress);

    generateVideo(
      {
        mbti: analysis.report.mbti,
        keyframe_data_url: analysis.keyframe_data_url,
        duration: 8,
        cat_name: "你家猫",
        owner_name: "铲屎官",
      },
      (snap: JobStatus) => {
        if (!alive) return;
        setProg((p) => mergeStatus(p, snap));
      },
    )
      .then((res) => alive && setGeneratedVideo(res))
      .catch((e) => {
        if (!alive) return;
        const msg = e?.detail?.message ?? e?.detail?.upstream_body?.error?.message
                  ?? e?.message ?? "生成失败";
        setProg((p) => ({ ...p, phase: "error", error: msg }));
      });

    return () => { alive = false; };
  }, [analysis, video, nav, setGeneratedVideo]);

  if (!analysis) return null;

  const onRegenerate = () => setGeneratedVideo(null);

  // Derive view state from data, not a separate `loading` flag — having both
  // creates a race: when `setGeneratedVideo(res)` fires, the useEffect cleanup
  // runs (because `video` is in the deps), flipping `alive = false` BEFORE the
  // .finally that would have set loading=false. Net result: LoadingPanel sticks.
  const showResult  = !!video;
  const showError   = !video && prog.phase === "error";
  const showLoading = !video && prog.phase !== "error";

  return (
    <div className="animate-soft-fade px-5 pb-10 pt-2">
      <header className="relative px-1 pb-3 pt-6 text-center">
        <div className="mb-1 inline-block animate-gentle-bob text-[36px]">🐱</div>
        <h1 className="text-2xl font-bold tracking-wider text-brown">让 TA 开口</h1>
        <p className="mt-1 text-[12px] text-brown-light">
          {analysis.report.mbti} · {analysis.report.nickname}
        </p>
      </header>

      {showLoading && <LoadingPanel prog={prog} />}

      {showError && (
        <ErrorPanel
          message={prog.error ?? "未知错误"}
          onRetry={() => setGeneratedVideo(null)}
          onBack={() => nav(-1)}
        />
      )}

      {showResult && (
        <ResultPanel
          videoUrl={video.video_url}
          script={video.script}
          onRegenerate={onRegenerate}
          onBack={() => nav(-1)}
        />
      )}
    </div>
  );
}


function mergeStatus(p: Progress, snap: JobStatus): Progress {
  // Translate the server-side JobState snapshot into the UI's Progress shape.
  // status="done"/"error" are handled in the .then/.catch of generateVideo, so
  // here we only ever see running snapshots — phase reflects which stage is
  // active inside the pipeline (script vs render).
  const phase: Phase = snap.phase === "error" ? "error"
                     : snap.phase === "done"  ? "done"
                     : snap.phase === "render" ? "render"
                     : "script";

  // Fill the script preview card the moment the script stage finishes.
  // Backend sends a small subset (title/scene/expression_style/spoken_script);
  // pad missing fields so the existing render path doesn't trip on undefined.
  let scriptPreview = p.scriptPreview;
  if (snap.script && (snap.script.title || snap.script.spoken_script)) {
    scriptPreview = {
      title: snap.script.title ?? "",
      mbti: snap.script.mbti ?? p.scriptPreview?.mbti ?? "ISFP",
      selected_profile_summary: snap.script.selected_profile_summary ?? "",
      theme_category: snap.script.theme_category ?? "",
      scene: snap.script.scene ?? "",
      expression_style: snap.script.expression_style ?? "",
      emotion_curve: snap.script.emotion_curve ?? "",
      setting: snap.script.setting ?? "",
      cat_visual_behavior: snap.script.cat_visual_behavior ?? [],
      spoken_script: snap.script.spoken_script ?? "",
      shot_plan: snap.script.shot_plan ?? [],
      video_prompt: snap.script.video_prompt ?? "",
      negative_prompt: snap.script.negative_prompt ?? "",
    };
  }

  return {
    ...p,
    phase,
    scriptChunks: snap.script_chunks,
    scriptSize: snap.script_size,
    renderChunks: snap.render_chunks,
    renderSize: snap.render_size,
    pollAttempt: snap.poll_attempt,
    pollElapsedSec: snap.poll_elapsed_sec,
    scriptPreview,
  };
}


function LoadingPanel({ prog }: { prog: Progress }) {
  const steps = [
    {
      key: "script",
      emoji: "✍️",
      label: "为你家猫写专属台词",
      detail: prog.scriptChunks > 0
        ? `${prog.scriptChunks} chunks · ${prog.scriptSize} 字符`
        : "正在调用 Gemini...",
    },
    {
      key: "render",
      emoji: "🎥",
      label: "AI 渲染视频",
      detail: prog.pollAttempt > 0
        ? `Veo 渲染队列中 · 已等待 ${prog.pollElapsedSec}s (第 ${prog.pollAttempt} 次轮询)`
        : prog.renderChunks > 0
        ? `${prog.renderChunks} chunks · ${prog.renderSize} 字符`
        : "请耐心等待 60-180s",
    },
    {
      key: "done",
      emoji: "✨",
      label: "马上让 TA 开口啦",
      detail: "",
    },
  ] as const;

  const order: Phase[] = ["script", "render", "done"];
  const currentIdx = order.indexOf(prog.phase);

  return (
    <div className="mt-6 flex flex-col items-center">
      <div className="inline-block animate-cat-jump text-[80px]">🎬</div>
      <h2 className="mt-6 text-[16px] font-semibold text-brown">
        AI 正在让你家猫开口...
      </h2>
      <p className="mt-1 text-xs text-brown-light">
        全程实时进度,别离开哦
      </p>

      <ul className="mt-7 w-full max-w-xs space-y-2 text-sm">
        {steps.map((s, i) => {
          const state = i < currentIdx ? "done" : i === currentIdx ? "active" : "pending";
          return (
            <li
              key={s.key}
              className={[
                "mx-auto max-w-[300px] rounded-2xl px-4 py-3 font-medium transition-all",
                state === "active"  && "scale-[1.03] bg-peach text-orange-deep",
                state === "done"    && "bg-matcha/15 text-matcha opacity-70",
                state === "pending" && "opacity-40 text-muted",
              ].filter(Boolean).join(" ")}
            >
              <div className="text-center">
                <span className="mr-1.5">{s.emoji}</span>{s.label}
              </div>
              {state === "active" && s.detail && (
                <div className="mt-1 text-center text-[10px] opacity-80">
                  {s.detail}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {prog.scriptPreview && prog.phase === "render" && (
        <div className="mt-5 w-full rounded-2xl bg-white p-4 shadow-soft">
          <p className="text-[11px] font-bold text-orange-deep">
            📜 {prog.scriptPreview.title || "台词已写好"}
          </p>
          {(prog.scriptPreview.scene || prog.scriptPreview.expression_style) && (
            <p className="mt-1 text-[10px] text-brown-light">
              {prog.scriptPreview.scene}
              {prog.scriptPreview.expression_style && ` · ${prog.scriptPreview.expression_style}`}
            </p>
          )}
          {prog.scriptPreview.spoken_script && (
            <p className="mt-2 whitespace-pre-line text-[12px] leading-6 text-brown">
              {prog.scriptPreview.spoken_script}
            </p>
          )}
        </div>
      )}
    </div>
  );
}


function ResultPanel({
  videoUrl, script, onRegenerate, onBack,
}: {
  videoUrl: string;
  script: VideoScript;
  onRegenerate: () => void;
  onBack: () => void;
}) {
  return (
    <div>
      <div className="overflow-hidden rounded-[28px] bg-black shadow-warm">
        <video
          src={videoUrl}
          controls
          autoPlay
          loop
          playsInline
          className="aspect-[9/16] w-full bg-black object-contain"
        />
      </div>

      <div className="mt-4 rounded-2xl bg-white p-4 shadow-soft">
        <p className="text-[11px] font-bold text-orange-deep">📜 {script.title}</p>
        <p className="mt-1 text-[10px] text-brown-light">
          {script.theme_category} · {script.scene} · {script.expression_style}
        </p>
        <p className="mt-3 whitespace-pre-line text-[13px] leading-6 text-brown">
          {script.spoken_script}
        </p>
        {script.cat_visual_behavior.length > 0 && (
          <p className="mt-3 text-[10px] text-brown-light">
            🐾 {script.cat_visual_behavior.join(" · ")}
          </p>
        )}
      </div>

      <div className="mt-5 flex gap-2.5">
        <a
          href={videoUrl}
          target="_blank"
          rel="noreferrer"
          download
          className="flex-1 rounded-2xl border-2 border-peach px-3 py-3 text-center text-sm font-semibold text-brown-light transition hover:border-orange hover:bg-peach hover:text-orange-deep"
        >
          📥 下载视频
        </a>
        <button
          onClick={onRegenerate}
          className="flex-1 rounded-2xl border-2 border-peach px-3 py-3 text-sm font-semibold text-brown-light transition hover:border-orange hover:bg-peach hover:text-orange-deep"
        >
          🔄 换一段对话
        </button>
      </div>

      <button
        onClick={onBack}
        className="mt-3 w-full rounded-2xl border-2 border-peach/40 px-3 py-2.5 text-xs font-medium text-brown-light"
      >
        ← 返回报告卡
      </button>
    </div>
  );
}


function ErrorPanel({
  message, onRetry, onBack,
}: {
  message: string;
  onRetry: () => void;
  onBack: () => void;
}) {
  return (
    <div className="mt-8 flex flex-col items-center">
      <div className="text-[64px]">😿</div>
      <p className="mt-4 text-sm font-semibold text-brown">视频生成失败</p>
      <p className="mt-2 max-w-xs text-center text-[11px] text-brown-light break-all">
        {message}
      </p>
      <div className="mt-5 flex w-full max-w-xs gap-2.5">
        <button
          onClick={onRetry}
          className="flex-1 rounded-2xl bg-gradient-to-br from-orange to-orange-deep px-3 py-3 text-sm font-bold text-white shadow-warm"
        >
          🔄 重试
        </button>
        <button
          onClick={onBack}
          className="flex-1 rounded-2xl border-2 border-peach px-3 py-3 text-sm font-semibold text-brown-light"
        >
          ← 返回
        </button>
      </div>
    </div>
  );
}
