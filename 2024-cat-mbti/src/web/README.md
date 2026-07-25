# CatMBTI Web

React + Vite + TypeScript + Tailwind 移动端 H5。

## 环境

- Node.js 18+ (推荐 20)
- 后端默认跑在 http://localhost:8000(由 [vite.config.ts](vite.config.ts) 中的 `/api` 代理转发)

## 运行

```bash
cd idea2/src/web
npm install
npm run dev
```

打开 http://localhost:5173,用手机 viewport 调试(已锁 480px 宽度)。

## 页面路由

| 路径 | 文件 | 说明 |
| --- | --- | --- |
| `/` | [src/pages/Upload.tsx](src/pages/Upload.tsx) | 上传猫视频 |
| `/analyzing` | [src/pages/Analyzing.tsx](src/pages/Analyzing.tsx) | 分析中 Loading |
| `/report` | [src/pages/Report.tsx](src/pages/Report.tsx) | MBTI 报告卡(可下载图片分享) |
| `/matches` | [src/pages/Matches.tsx](src/pages/Matches.tsx) | 同型号网红猫 TOP3 |

## 关键模块

- [src/api/client.ts](src/api/client.ts) — axios 实例 + 两个接口封装
- [src/store/analysis.ts](src/store/analysis.ts) — Zustand 全局状态(视频 / 报告 / 匹配)
- [src/components/ReportCard.tsx](src/components/ReportCard.tsx) — 报告卡组件,用 `html-to-image` 导出 PNG
- [src/types/api.ts](src/types/api.ts) — 与后端 Pydantic schema 一一对应的 TS 类型
