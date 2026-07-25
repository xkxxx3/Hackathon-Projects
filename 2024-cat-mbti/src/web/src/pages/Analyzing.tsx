import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeVideo, type StreamEvent } from "@/api/client";
import { useAnalysisStore } from "@/store/analysis";
import { findSample } from "@/data/samples";

// UI step model: an ordered list, each driven by one or more backend events.
// `progress` is a free-form line shown below the active step (e.g. "12 chunks").
type StepKey = "frames" | "analyzing" | "scoring" | "done";
const STEPS: { key: StepKey; emoji: string; label: string }[] = [
  { key: "frames",    emoji: "🎬", label: "提取视频精彩瞬间" },
  { key: "analyzing", emoji: "🔍", label: "AI 观察猫咪小动作" },
  { key: "scoring",   emoji: "💭", label: "规则引擎打分" },
  { key: "done",      emoji: "✨", label: "出 MBTI 报告" },
];

const SAMPLE_STEP_DELAY_MS = 700;

export default function AnalyzingPage() {
  const nav = useNavigate();
  const { videoFile, sampleId, setAnalysis } = useAnalysisStore();
  const [stepIdx, setStepIdx] = useState(0);
  const [progress, setProgress] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoFile && !sampleId) {
      nav("/", { replace: true });
      return;
    }
    let alive = true;

    const finish = (analysis: Parameters<typeof setAnalysis>[0]) => {
      if (!alive) return;
      setStepIdx(STEPS.length - 1);
      setAnalysis(analysis);
      setTimeout(() => alive && nav("/report", { replace: true }), 400);
    };

    if (sampleId) {
      const sample = findSample(sampleId);
      if (!sample) {
        setError("示例数据缺失");
        return;
      }
      // Walk the indicator visually for the demo path (no real backend).
      let i = 0;
      const tick = setInterval(() => {
        i += 1;
        if (i >= STEPS.length - 1) clearInterval(tick);
        setStepIdx(i);
      }, SAMPLE_STEP_DELAY_MS);
      setTimeout(() => {
        clearInterval(tick);
        finish({
          analysis_id: `sample_${sampleId}`,
          report: sample.report,
          keyframe_data_url: "",
        });
      }, SAMPLE_STEP_DELAY_MS * STEPS.length);
      return () => { alive = false; clearInterval(tick); };
    }

    // Real backend path — drive the indicator off real NDJSON events.
    if (!videoFile) return;
    setError(null);
    setStepIdx(0);
    setProgress("");

    analyzeVideo(videoFile, (ev: StreamEvent) => {
      if (!alive) return;
      switch (ev.event) {
        case "uploaded":
          setStepIdx(0);
          setProgress(`已上传 ${ev.data?.size_kb ?? "?"} KB`);
          break;
        case "frames":
          setStepIdx(0);
          setProgress(`抽 ${ev.data?.frame_count} 帧 · 视频时长 ${ev.data?.duration_sec}s`);
          break;
        case "analyzing":
          setStepIdx(1);
          setProgress("Gemini 视觉模型正在分析帧序列...");
          break;
        case "chunk":
          setStepIdx(1);
          setProgress(`已接收 ${ev.data?.chunks} 个 chunk · ${ev.data?.size} 字符`);
          break;
        case "scoring":
          setStepIdx(2);
          setProgress(`置信度 ${ev.data?.confidence}`);
          break;
        case "warn":
          setProgress(`⚠️ ${ev.message ?? ""}`);
          break;
      }
    })
      .then(finish)
      .catch((e) => alive && setError(e?.detail?.message ?? e?.message ?? "分析失败"));

    return () => { alive = false; };
  }, [videoFile, sampleId, nav, setAnalysis]);

  return (
    <div className="animate-soft-fade flex min-h-screen flex-col items-center justify-center px-5 py-16">
      <div className="inline-block animate-cat-jump text-[90px]">🐱</div>

      <h2 className="mt-8 text-[17px] font-semibold text-brown">
        AI 正在读懂你的小毛孩...
      </h2>

      <ul className="mt-8 w-full max-w-xs space-y-1.5 text-sm">
        {STEPS.map((s, i) => {
          const state = i < stepIdx ? "done" : i === stepIdx ? "active" : "pending";
          return (
            <li
              key={s.key}
              className={[
                "mx-auto max-w-[280px] rounded-2xl px-4 py-2.5 text-center font-medium transition-all",
                state === "active"  && "scale-[1.03] bg-peach text-orange-deep opacity-100",
                state === "done"    && "bg-matcha/15 text-matcha opacity-70",
                state === "pending" && "opacity-40 text-muted",
              ].filter(Boolean).join(" ")}
            >
              <span className="mr-1.5">{s.emoji}</span>{s.label}
            </li>
          );
        })}
      </ul>

      {progress && (
        <p className="mt-4 max-w-xs text-center text-[11px] text-brown-light break-all">
          {progress}
        </p>
      )}

      {error && (
        <div className="mt-6 rounded-xl bg-red-50 p-3 text-xs text-red-600 break-all">
          {error}{" "}
          <button className="underline" onClick={() => nav("/")}>
            返回重试
          </button>
        </div>
      )}
    </div>
  );
}
