// Pre-baked sample cats shown on the upload page (治愈版 sample-grid 风格).
// Clicking a sample short-circuits the upload flow and pushes a hardcoded
// MBTIReport into the store, then routes straight to /report. Useful for demo
// stability when there's no internet / Gemini quota.

import type { MBTIReport, MBTIType } from "@/types/api";

export interface SampleCat {
  id: string;
  emoji: string;
  badge: string;
  name: string;
  desc: string;
  report: MBTIReport;
}

const sampleReport = (
  mbti: MBTIType,
  nickname: string,
  summary: string,
  tags: string[],
  highlight: string,
  scores: { EI: number; SN: number; TF: number; JP: number },
): MBTIReport => ({
  mbti,
  nickname,
  summary,
  tags,
  dimensions: [
    { axis: "EI", score: scores.EI, label_left: "慵懒宅家", label_right: "活跃外向" },
    { axis: "SN", score: scores.SN, label_left: "守旧务实", label_right: "探索好奇" },
    { axis: "TF", score: scores.TF, label_left: "冷静观察", label_right: "情绪丰富" },
    { axis: "JP", score: scores.JP, label_left: "随机散漫", label_right: "计划规律" },
  ],
  highlights: [{ start_sec: 8, end_sec: 8, caption: highlight }],
  confidence: 0.85,
});

export const SAMPLE_CATS: SampleCat[] = [
  {
    id: "qiuqiu",
    emoji: "😺",
    badge: "活泼",
    name: "球球",
    desc: "凑镜头爱蹭人",
    report: sampleReport(
      "ENFP",
      "阳光猫",
      "这只猫见谁都贴贴,对什么都感兴趣。镜头是它的舞台,铲屎官的腿是它的家。典型的无社恐版猫咪,能把家变成派对现场。",
      ["热情", "好奇", "外向", "社交牛猫症"],
      "主动凑近镜头,连续蹭头 3 次,尾巴竖成感叹号",
      { EI: 82, SN: 65, TF: 78, JP: 32 },
    ),
  },
  {
    id: "xiaohei",
    emoji: "🐈‍⬛",
    badge: "高冷",
    name: "小黑",
    desc: "高处观察一切",
    report: sampleReport(
      "INTJ",
      "战略家猫",
      "这只猫站在高处观察一切。它不会轻易出手,但每一次行动都精准。它不需要你的爱,但你需要它的认可。",
      ["高冷", "计划", "独立", "思考型"],
      "在柜顶静默观察 12 秒后,精准跳到目标位置",
      { EI: 22, SN: 75, TF: 25, JP: 80 },
    ),
  },
  {
    id: "tuanzi",
    emoji: "😽",
    badge: "文艺",
    name: "团子",
    desc: "躲纸箱发呆",
    report: sampleReport(
      "INFP",
      "艺术家猫",
      "这只猫住在自己的精神世界里。纸箱是它的工作室,阳光是它的灵感。它不爱热闹,但你只要轻轻坐在旁边,就是它最大的安全感。",
      ["内向", "温柔", "敏感", "发呆派"],
      "在纸箱中凝视远方 18 秒,期间瞳孔放大、尾尖微动",
      { EI: 28, SN: 75, TF: 72, JP: 30 },
    ),
  },
];

export const findSample = (id: string) =>
  SAMPLE_CATS.find((s) => s.id === id);
