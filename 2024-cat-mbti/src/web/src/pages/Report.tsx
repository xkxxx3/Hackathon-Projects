import { useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toPng } from "html-to-image";
import ReportCard from "@/components/ReportCard";
import ProfilePanel from "@/components/ProfilePanel";
import { useAnalysisStore } from "@/store/analysis";

export default function ReportPage() {
  const nav = useNavigate();
  const analysis = useAnalysisStore((s) => s.analysis);
  const reset = useAnalysisStore((s) => s.reset);
  const cardRef = useRef<HTMLDivElement>(null);

  if (!analysis) {
    nav("/", { replace: true });
    return null;
  }

  const onSave = async () => {
    if (!cardRef.current) return;
    const dataUrl = await toPng(cardRef.current, { pixelRatio: 2 });
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `cat-mbti-${analysis.report.mbti}.png`;
    a.click();
  };

  const onReset = () => {
    reset();
    nav("/");
  };

  const onTalk = () => nav("/video");

  return (
    <div className="animate-soft-fade px-5 pb-10 pt-2">
      <header className="relative px-1 pb-3 pt-6 text-center">
        <div className="mb-1 inline-block animate-gentle-bob text-[36px]">🐱</div>
        <h1 className="text-2xl font-bold tracking-wider text-brown">喵格匹配</h1>
      </header>

      {analysis.report.confidence === 0 && (
        <div className="mb-3 rounded-2xl bg-orange-light/40 p-3 text-xs text-orange-deep">
          ⚠️ 视频信息量不足或 AI 分析失败,已为你输出兜底结果(文艺猫 ISFP)。
          建议重拍一段包含更丰富行为的视频。
        </div>
      )}

      <ReportCard ref={cardRef} report={analysis.report} />

      {/* 16 型猫格详细解析 — 不进 PNG 导出,仅页面阅读 */}
      <ProfilePanel mbti={analysis.report.mbti} />

      {/* Primary CTA — kicks off the talking-cat video pipeline (M3) */}
      <button
        onClick={onTalk}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-br from-orange to-orange-deep px-4 py-4 font-bold text-white shadow-warm transition active:scale-[0.98]"
      >
        <span className="text-xl">🎬</span>
        <span>让 TA 开口对你说话</span>
        <span className="text-xs opacity-80">· AI 生成专属视频</span>
      </button>
      <p className="mt-2 text-center text-[11px] text-brown-light">
        AI 根据 {analysis.report.mbti} 性格写台词,猫亲口对你说,约 60s 生成
      </p>

      <div className="mt-5 flex gap-2.5">
        <button
          onClick={onSave}
          className="flex-1 rounded-2xl border-2 border-peach px-3 py-3 text-sm font-semibold text-brown-light transition hover:border-orange hover:bg-peach hover:text-orange-deep"
        >
          📥 保存图片
        </button>
        <button
          onClick={onReset}
          className="flex-1 rounded-2xl border-2 border-peach px-3 py-3 text-sm font-semibold text-brown-light transition hover:border-orange hover:bg-peach hover:text-orange-deep"
        >
          ↻ 重新测试
        </button>
      </div>

      <p className="mt-7 text-center text-[11px] font-medium text-muted">
        娱乐结果仅供参考 · 抖音 AI 创变者计划
        <span className="mt-1 block tracking-[4px] opacity-40">🐾 🐾 🐾</span>
      </p>
    </div>
  );
}
