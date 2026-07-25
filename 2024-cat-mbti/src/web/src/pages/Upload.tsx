import { useNavigate } from "react-router-dom";
import { useRef } from "react";
import { useAnalysisStore } from "@/store/analysis";
import { SAMPLE_CATS } from "@/data/samples";

export default function UploadPage() {
  const nav = useNavigate();
  const setVideo = useAnalysisStore((s) => s.setVideo);
  const setSample = useAnalysisStore((s) => s.setSample);
  const inputRef = useRef<HTMLInputElement>(null);

  const onPick = () => inputRef.current?.click();

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setVideo(file);
    nav("/analyzing");
  };

  const onSample = (id: string) => {
    setSample(id);
    nav("/analyzing");
  };

  return (
    <div className="animate-soft-fade px-5 pb-6 pt-2">
      {/* Header */}
      <header className="relative px-1 pb-5 pt-8 text-center">
        <div className="mb-1 inline-block animate-gentle-bob text-[42px]">🐱</div>
        <h1 className="text-[28px] font-bold tracking-wider text-brown">喵格匹配</h1>
        <p className="mt-1 text-[13px] font-medium text-brown-light">
          读懂你的小毛孩,找到 TA 的灵魂伙伴
        </p>
        <span className="pointer-events-none absolute bottom-1 right-7 -rotate-12 text-[22px] opacity-25">
          🐾
        </span>
      </header>

      {/* Upload zone */}
      <button
        onClick={onPick}
        className="block w-full cursor-pointer rounded-[28px] border-2 border-dashed border-orange bg-white/60 p-10 text-center backdrop-blur transition hover:-translate-y-0.5 hover:bg-white hover:shadow-warm"
      >
        <div className="inline-block animate-gentle-bob text-[56px]">🎥</div>
        <div className="mt-3 text-[17px] font-semibold text-brown">
          上传一段你家猫的视频
        </div>
        <div className="mt-1 text-xs text-brown-light">
          10-30 秒,记录 TA 的日常瞬间 ✨
        </div>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        hidden
        onChange={onFile}
      />

      {/* Sample grid */}
      <section className="mt-7">
        <div className="mb-3 pl-2 text-sm font-semibold text-brown-light">
          🐾 试试示例猫咪
        </div>
        <div className="grid grid-cols-3 gap-3">
          {SAMPLE_CATS.map((s) => (
            <button
              key={s.id}
              onClick={() => onSample(s.id)}
              className="relative flex aspect-[3/4] flex-col items-center justify-center overflow-hidden rounded-[20px] border-2 border-transparent bg-white shadow-soft transition hover:-translate-y-1.5 hover:scale-[1.02] hover:border-orange hover:shadow-warm"
            >
              <span className="absolute right-2 top-2 rounded-[10px] bg-peach px-2 py-0.5 text-[9px] font-semibold text-orange-deep">
                {s.badge}
              </span>
              <span className="text-[44px] drop-shadow-sm">{s.emoji}</span>
              <span className="mt-2 text-sm font-bold text-brown">{s.name}</span>
              <span className="mt-1 px-1.5 text-center text-[10px] font-medium text-brown-light">
                {s.desc}
              </span>
            </button>
          ))}
        </div>
      </section>

      <p className="mt-8 text-center text-[11px] font-medium text-muted">
        娱乐结果仅供参考 · 抖音 AI 创变者计划
        <span className="mt-1 block tracking-[4px] opacity-40">🐾 🐾 🐾</span>
      </p>
    </div>
  );
}
