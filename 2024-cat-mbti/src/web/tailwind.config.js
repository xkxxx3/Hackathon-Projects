/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 治愈版色卡 — 见 docs/demo_治愈版.html :root
        cream:         "#FFF8F0",
        "cream-dark":  "#FAEFE0",
        orange:        "#FFB088",
        "orange-light":"#FFD4B8",
        "orange-deep": "#FF9A6C",
        matcha:        "#A8C97F",
        "matcha-light":"#C8DFA0",
        peach:         "#FFE4D6",
        brown:         "#5C4033",
        "brown-light": "#8B6F5B",
        muted:         "#B5A399",
      },
      fontFamily: {
        sans: ["Quicksand", "PingFang SC", "Microsoft YaHei", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft:   "0 4px 20px rgba(196, 145, 110, 0.12)",
        medium: "0 8px 30px rgba(196, 145, 110, 0.18)",
        warm:   "0 10px 40px rgba(255, 154, 108, 0.25)",
      },
      keyframes: {
        "gentle-bob": {
          "0%, 100%": { transform: "translateY(0) rotate(-5deg)" },
          "50%":      { transform: "translateY(-6px) rotate(5deg)" },
        },
        "cat-jump": {
          from: { transform: "translateY(0) rotate(-3deg) scale(1)" },
          to:   { transform: "translateY(-16px) rotate(3deg) scale(1.05)" },
        },
        "soft-fade": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "modal-pop": {
          from: { opacity: "0", transform: "scale(0.9)" },
          to:   { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        "gentle-bob": "gentle-bob 3s ease-in-out infinite",
        "cat-jump":   "cat-jump 0.8s cubic-bezier(0.4, 0, 0.2, 1) infinite alternate",
        "soft-fade":  "soft-fade 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
        "modal-pop":  "modal-pop 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
      },
    },
  },
  plugins: [],
};
