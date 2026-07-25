// Consume a streaming application/x-ndjson body via fetch.
//
// Each line of the body is a JSON object. The terminal line is either
// {event: "done", data: <T>} or {event: "error", message, data?}.
// All intermediate events are surfaced to `onEvent` so the UI can drive
// real progress indicators.

export interface StreamEvent {
  event: string;
  message?: string;
  data?: any;
}

export class StreamError extends Error {
  detail: any;
  constructor(message: string, detail?: any) {
    super(message);
    this.name = "StreamError";
    this.detail = detail;
  }
}

export async function streamNDJSON<T>(
  url: string,
  init: RequestInit,
  onEvent: (e: StreamEvent) => void,
): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok || !res.body) {
    let body: any = null;
    try { body = await res.json(); } catch { /* keep null */ }
    throw new StreamError(`HTTP ${res.status} ${res.statusText}`, body);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  // Terminal-event handler. Returning means we got what we needed; we cancel
  // the reader so the underlying fetch is aborted (some proxies don't close
  // the connection promptly after the last NDJSON line, which would otherwise
  // make this promise hang indefinitely on `reader.read()`).
  const finalize = async (ev: StreamEvent): Promise<T> => {
    try { await reader.cancel(); } catch { /* already closed, ignore */ }
    if (ev.event === "error") {
      throw new StreamError(ev.message ?? "stream error", ev.data);
    }
    return ev.data as T;
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Split on newlines; keep any trailing partial line in the buffer.
    let newline: number;
    while ((newline = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (!line) continue;
      let ev: StreamEvent;
      try {
        ev = JSON.parse(line);
      } catch {
        // A non-JSON line is a bug on the server side; surface it so we notice.
        throw new StreamError(`Stream returned non-JSON line: ${line.slice(0, 200)}`);
      }
      onEvent(ev);
      if (ev.event === "done" || ev.event === "error") {
        return finalize(ev);
      }
    }
  }

  // The stream closed without ever emitting done/error — try to salvage from
  // a trailing line (server forgot the final \n).
  if (buffer.trim()) {
    try {
      const ev = JSON.parse(buffer.trim());
      onEvent(ev);
      if (ev.event === "done" || ev.event === "error") {
        return finalize(ev);
      }
    } catch {
      // ignore — fall through to the terminal-missing error below
    }
  }

  throw new StreamError("Stream ended without a terminal event");
}
