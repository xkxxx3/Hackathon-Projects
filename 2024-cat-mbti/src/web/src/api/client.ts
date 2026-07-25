import { streamNDJSON, type StreamEvent } from "./stream";
import type {
  AnalyzeResponse,
  JobStatus,
  VideoGenerationRequest,
  VideoGenerationResponse,
} from "@/types/api";

export type { StreamEvent } from "./stream";

const API_BASE = "/api";


export async function analyzeVideo(
  file: File,
  onEvent: (e: StreamEvent) => void,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("video", file);
  return streamNDJSON<AnalyzeResponse>(
    `${API_BASE}/analyze`,
    { method: "POST", body: form },
    onEvent,
  );
}


// Poll cadence for /video/status. 2.5s is the sweet spot: fast enough that
// chunk/render counters look live, slow enough that we don't bombard the API
// during a 3-5 min Veo render. Each request is <1s, so individual mobile
// network drops are recoverable on the next tick instead of fatal.
const POLL_INTERVAL_MS = 2500;

// Soft ceiling. Veo budget inside _poll_async_task is 360s; tack on the script
// stage (~15s) and slack for the initial Veo stream (~3min) and you get ~10min.
const POLL_BUDGET_MS = 10 * 60 * 1000;


export async function generateVideo(
  req: VideoGenerationRequest,
  onStatus: (s: JobStatus) => void,
): Promise<VideoGenerationResponse> {
  // Stage 1: kick off the job. <1s round-trip.
  const startRes = await fetch(`${API_BASE}/video/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!startRes.ok) {
    let body: any = null;
    try { body = await startRes.json(); } catch { /* keep null */ }
    const err = new Error(`HTTP ${startRes.status} ${startRes.statusText}`);
    (err as any).detail = body;
    throw err;
  }
  const { job_id } = await startRes.json() as { job_id: string };

  // Stage 2: poll status until terminal. Each poll is its own short HTTP
  // request, so phone screen-lock / NAT idle / Wi-Fi roam can't break the
  // pipeline anymore — at worst we drop a couple of polls and resume.
  const startedAt = Date.now();
  while (true) {
    if (Date.now() - startedAt > POLL_BUDGET_MS) {
      throw new Error("视频任务轮询超时(>10min) — 请稍后重试");
    }

    let snap: JobStatus | null = null;
    try {
      const r = await fetch(`${API_BASE}/video/status/${job_id}`);
      if (r.ok) snap = await r.json() as JobStatus;
      // Non-OK responses (transient 502/504 from a flaky tunnel) just fall
      // through to the sleep + retry below. Don't fail the whole job on a
      // single bad poll.
    } catch {
      // Network error on this individual poll — retry on the next tick.
    }

    if (snap) {
      onStatus(snap);
      if (snap.status === "done") {
        if (!snap.result) {
          throw new Error("任务标记为 done 但缺少结果");
        }
        return snap.result;
      }
      if (snap.status === "error") {
        const err = new Error(snap.error ?? "视频生成失败");
        (err as any).detail = {
          message: snap.error,
          upstream_body: snap.upstream_body,
          exception: snap.exception_type,
        };
        throw err;
      }
    }

    await new Promise((res) => setTimeout(res, POLL_INTERVAL_MS));
  }
}
