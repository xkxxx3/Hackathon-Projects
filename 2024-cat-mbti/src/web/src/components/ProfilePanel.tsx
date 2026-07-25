import type { MBTIType } from "@/types/api";
import { CAT_PROFILES } from "@/data/profiles";

interface Props {
  mbti: MBTIType;
}

// Four sections of the 16-type profile, displayed below the report card.
// Source: docs/16型猫格解析.md.
const SECTIONS: { key: keyof typeof CAT_PROFILES["INTJ"]; emoji: string; label: string }[] = [
  { key: "overall",    emoji: "💫", label: "结果总评" },
  { key: "dimensions", emoji: "📊", label: "维度倾向" },
  { key: "behavior",   emoji: "🔬", label: "行为学解读" },
  { key: "with_you",   emoji: "💞", label: "和你相处" },
];

export default function ProfilePanel({ mbti }: Props) {
  const profile = CAT_PROFILES[mbti];
  if (!profile) return null;

  return (
    <section className="mt-6 space-y-3">
      <div className="flex items-baseline justify-between px-1">
        <h2 className="text-[15px] font-bold text-brown">
          {mbti} · {profile.nickname} 详细解析
        </h2>
        <span className="text-[10px] text-brown-light">娱乐向</span>
      </div>

      {SECTIONS.map((s) => (
        <div
          key={s.key}
          className="rounded-2xl bg-white/85 p-4 shadow-soft backdrop-blur"
        >
          <p className="flex items-center gap-1.5 text-[11px] font-bold text-orange-deep">
            <span>{s.emoji}</span>
            <span>{s.label}</span>
          </p>
          <p className="mt-2 text-[13px] leading-7 text-brown">
            {profile[s.key]}
          </p>
        </div>
      ))}
    </section>
  );
}
