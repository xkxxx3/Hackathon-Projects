import { forwardRef } from "react";
import type { MBTIReport } from "@/types/api";

interface Props {
  report: MBTIReport;
}

const ReportCard = forwardRef<HTMLDivElement, Props>(function ReportCard(
  { report },
  ref,
) {
  const highlight = report.highlights[0];

  return (
    <div
      ref={ref}
      className="relative overflow-hidden rounded-[28px] p-7 shadow-warm"
      style={{
        background:
          "linear-gradient(135deg, #FFE4D6 0%, #FFD4B8 50%, #FFB088 100%)",
      }}
    >
      <span className="pointer-events-none absolute right-4 top-4 rotate-[15deg] text-[64px] opacity-10">
        🐾
      </span>
      <span className="pointer-events-none absolute -bottom-2 left-3 -rotate-[25deg] text-[42px] opacity-10">
        🐾
      </span>

      <div className="relative z-10 flex flex-wrap items-baseline gap-3">
        <div className="text-[38px] font-bold tracking-[3px] text-brown">
          {report.mbti}
        </div>
        <div className="text-[22px] font-bold text-brown">{report.nickname}</div>
      </div>

      <div className="relative z-10 mt-4 flex flex-wrap gap-1.5">
        {report.tags.map((t) => (
          <span
            key={t}
            className="rounded-2xl bg-white/75 px-3 py-1 text-[11px] font-semibold text-brown backdrop-blur"
          >
            #{t}
          </span>
        ))}
      </div>

      <p className="relative z-10 mt-4 text-[13.5px] font-medium leading-7 text-brown">
        {report.summary}
      </p>

      {/* Highlight inline panel */}
      <div className="relative z-10 mt-4 rounded-2xl bg-white/75 p-3.5 text-[12.5px] leading-6 text-brown backdrop-blur">
        <strong className="block text-[11px] font-bold text-orange-deep">
          📸 高光时刻
        </strong>
        <span>
          {highlight
            ? `${highlight.start_sec === highlight.end_sec
                ? `0:${String(Math.floor(highlight.start_sec)).padStart(2, "0")}`
                : `0:${String(Math.floor(highlight.start_sec)).padStart(2, "0")}`} — ${highlight.caption}`
            : "本段视频未提取到突出片段"}
        </span>
      </div>

      {/* Dimension bars (subtle, for shareability) */}
      <div className="relative z-10 mt-5 space-y-2">
        {report.dimensions.map((d) => {
          const onRight = d.score >= 50;
          return (
            <div key={d.axis}>
              <div className="flex justify-between text-[10px] text-brown/70">
                <span className={onRight ? "" : "font-semibold text-brown"}>
                  {d.label_left}
                </span>
                <span className={onRight ? "font-semibold text-brown" : ""}>
                  {d.label_right}
                </span>
              </div>
              <div className="relative mt-1 h-1.5 rounded-full bg-white/40">
                <div
                  className="absolute inset-y-0 rounded-full bg-orange-deep"
                  style={{
                    left: onRight ? "50%" : `${d.score}%`,
                    width: onRight ? `${d.score - 50}%` : `${50 - d.score}%`,
                  }}
                />
                <div className="absolute inset-y-0 left-1/2 w-px bg-brown/20" />
              </div>
            </div>
          );
        })}
      </div>

      <p className="relative z-10 mt-5 text-center text-[10px] text-brown/60">
        仅供娱乐 · 喵格匹配 CatMBTI
      </p>
    </div>
  );
});

export default ReportCard;
