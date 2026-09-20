import axios from "axios";

function resolveApiBase(): string {
  if (import.meta.env.DEV) {
    return (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
  }
  if (typeof window !== "undefined" && window.__API_BASE__) {
    return window.__API_BASE__.replace(/\/$/, "");
  }
  return (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
}

export const api = axios.create({
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  config.baseURL = resolveApiBase();
  return config;
});

export type HealthResponse = {
  status: string;
};

export async function getHealth(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>("/api/health");
  return response.data;
}

export type AnalyzeVideoRequest = {
  youtube_url: string;
};

export type AnalyzeVideoResponse = {
  video_id: string;
  title: string | null;
  channel: string | null;
  published_at: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  transcript_status: string;
  transcript_error?: string | null;
};

export async function analyzeVideo(youtubeUrl: string): Promise<AnalyzeVideoResponse> {
  const response = await api.post<AnalyzeVideoResponse>("/api/videos/analyze", {
    youtube_url: youtubeUrl,
  });
  return response.data;
}

export async function getVideoTranscript(videoId: string): Promise<{
  video_id: string;
  transcript_status: string;
  segments: { start: number; duration: number; text: string }[];
}> {
  const response = await api.get(`/api/videos/${videoId}/transcript`);
  return response.data;
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return fallback;
}

export type MentionItem = {
  timestamp_seconds: number;
  timestamp: string;
  text: string;
  matched_text: string;
  context_before: string;
  context_after: string;
  mention_type: string;
  confidence: number;
  youtube_url: string;
};

export type MentionSearchResponse = {
  advertiser: string;
  total_mentions: number;
  mentions: MentionItem[];
};

export async function searchMentions(videoId: string, advertiser: string): Promise<MentionSearchResponse> {
  const response = await api.post<MentionSearchResponse>("/api/mentions/search", {
    video_id: videoId,
    advertiser,
  });
  return response.data;
}
