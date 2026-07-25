import { create } from "zustand";
import type { AnalyzeResponse, VideoGenerationResponse } from "@/types/api";
import { findSample } from "@/data/samples";

interface AnalysisState {
  videoFile: File | null;
  videoUrl: string | null;
  sampleId: string | null;
  analysis: AnalyzeResponse | null;
  // Generated talking-cat video (M3)
  video: VideoGenerationResponse | null;

  setVideo: (file: File) => void;
  setSample: (id: string) => void;
  setAnalysis: (a: AnalyzeResponse) => void;
  setGeneratedVideo: (v: VideoGenerationResponse | null) => void;
  reset: () => void;
}

export const useAnalysisStore = create<AnalysisState>((set, get) => ({
  videoFile: null,
  videoUrl: null,
  sampleId: null,
  analysis: null,
  video: null,

  setVideo: (file) => {
    const prev = get().videoUrl;
    if (prev) URL.revokeObjectURL(prev);
    set({
      videoFile: file,
      videoUrl: URL.createObjectURL(file),
      sampleId: null,
      analysis: null,
      video: null,
    });
  },

  setSample: (id) => {
    if (!findSample(id)) return;
    const prev = get().videoUrl;
    if (prev) URL.revokeObjectURL(prev);
    set({
      videoFile: null,
      videoUrl: null,
      sampleId: id,
      analysis: null,
      video: null,
    });
  },

  setAnalysis: (a) => set({ analysis: a, video: null }),
  setGeneratedVideo: (v) => set({ video: v }),

  reset: () => {
    const prev = get().videoUrl;
    if (prev) URL.revokeObjectURL(prev);
    set({
      videoFile: null,
      videoUrl: null,
      sampleId: null,
      analysis: null,
      video: null,
    });
  },
}));
