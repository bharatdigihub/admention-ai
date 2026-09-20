import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  analyzeVideo,
  AnalyzeVideoResponse,
  getApiErrorMessage,
  getHealth,
  getVideoTranscript,
  MentionItem,
  MentionSearchResponse,
  searchMentions,
} from "../api/client";

const STATUS_LABELS: Record<string, string> = {
  pending: "Loading transcript...",
  available: "YouTube transcript available",
  fixture: "Local development transcript fixture",
  whisper: "Transcript generated with Whisper fallback",
  unavailable: "Transcript unavailable",
};

export function HomePage() {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [advertiser, setAdvertiser] = useState("never gonna");
  const [video, setVideo] = useState<AnalyzeVideoResponse | null>(null);
  const [results, setResults] = useState<MentionSearchResponse | null>(null);

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: false,
  });

  const analyzeMutation = useMutation({
    mutationFn: analyzeVideo,
    onSuccess: (data) => {
      setVideo(data);
      setResults(null);
    },
  });

  useQuery({
    queryKey: ["transcript", video?.video_id, video?.transcript_status],
    enabled: Boolean(video?.video_id) && video?.transcript_status === "pending",
    queryFn: async () => {
      const transcript = await getVideoTranscript(video!.video_id);
      setVideo((current) =>
        current ? { ...current, transcript_status: transcript.transcript_status } : current,
      );
      return transcript;
    },
    retry: 1,
  });

  const searchMutation = useMutation({
    mutationFn: ({ videoId, name }: { videoId: string; name: string }) => searchMentions(videoId, name),
    onSuccess: setResults,
  });

  const healthLabel = healthQuery.isLoading
    ? "Checking backend..."
    : healthQuery.isError
      ? "Backend unavailable"
      : `Backend ${healthQuery.data?.status ?? "unknown"}`;

  function handleAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    analyzeMutation.mutate(youtubeUrl.trim());
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!video) {
      return;
    }
    searchMutation.mutate({ videoId: video.video_id, name: advertiser.trim() });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-3">
        <p className="text-sm uppercase tracking-[0.2em] text-sky-300">Sports media ops</p>
        <h1 className="text-4xl font-semibold text-white">AdMention AI</h1>
        <p className="max-w-2xl text-slate-300">Track every advertiser mention, automatically.</p>
        <div
          className={`w-fit rounded-full px-3 py-1 text-sm ${
            healthQuery.isSuccess ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-200"
          }`}
        >
          {healthLabel}
        </div>
      </header>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
        <h2 className="text-xl font-medium text-white">Advertiser Mention Tracker</h2>
        <p className="mt-2 text-slate-400">
          Paste a YouTube URL, then search the transcript for an advertiser or phrase.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Demo: analyze https://www.youtube.com/watch?v=dQw4w9WgXcQ and search “never gonna”. Those
          words are actually sung at 00:00:43.
        </p>

        <form className="mt-6 flex flex-col gap-3 sm:flex-row" onSubmit={handleAnalyze}>
          <input
            type="url"
            required
            value={youtubeUrl}
            onChange={(event) => setYoutubeUrl(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=VIDEO_ID"
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-white outline-none ring-sky-400 placeholder:text-slate-500 focus:ring-2"
          />
          <button
            type="submit"
            disabled={analyzeMutation.isPending}
            className="rounded-xl bg-sky-500 px-5 py-3 font-medium text-slate-950 hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {analyzeMutation.isPending ? "Fetching video and transcript..." : "Analyze Video"}
          </button>
        </form>

        {analyzeMutation.isError && (
          <p className="mt-4 text-sm text-rose-300">
            {getApiErrorMessage(analyzeMutation.error, "Unable to analyze that YouTube URL.")}
          </p>
        )}
      </section>

      {video && <VideoCard video={video} />}

      {video && (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          <h2 className="text-xl font-medium text-white">Find mentions</h2>
          <form className="mt-6 flex flex-col gap-3 sm:flex-row" onSubmit={handleSearch}>
            <input
              type="text"
              required
              minLength={2}
              value={advertiser}
              onChange={(event) => setAdvertiser(event.target.value)}
              placeholder="Advertiser or phrase"
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-white outline-none ring-sky-400 placeholder:text-slate-500 focus:ring-2"
            />
            <button
              type="submit"
              disabled={
                searchMutation.isPending ||
                video.transcript_status === "unavailable" ||
                video.transcript_status === "pending"
              }
              className="rounded-xl bg-emerald-400 px-5 py-3 font-medium text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {searchMutation.isPending ? "Searching..." : "Find Mentions"}
            </button>
          </form>
          {searchMutation.isError && (
            <p className="mt-4 text-sm text-rose-300">
              {getApiErrorMessage(searchMutation.error, "Unable to search mentions.")}
            </p>
          )}
        </section>
      )}

      {results && <ResultsList results={results} />}
    </main>
  );
}

function VideoCard({ video }: { video: AnalyzeVideoResponse }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70 shadow-xl">
      <div className="grid gap-6 p-6 md:grid-cols-[240px_1fr]">
        {video.thumbnail_url && (
          <img
            src={video.thumbnail_url}
            alt={video.title ?? "YouTube thumbnail"}
            className="h-40 w-full rounded-xl object-cover"
          />
        )}
        <div className="flex flex-col gap-2">
          <p className="text-sm uppercase tracking-wide text-slate-400">Video information</p>
          <h3 className="text-2xl font-semibold text-white">{video.title ?? "Untitled video"}</h3>
          <p className="text-slate-300">{video.channel ?? "Unknown channel"}</p>
          <dl className="mt-2 grid gap-2 text-sm text-slate-400 sm:grid-cols-2">
            <div>
              <dt className="text-slate-500">Video ID</dt>
              <dd className="text-slate-200">{video.video_id}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Published</dt>
              <dd className="text-slate-200">{video.published_at ?? "Unavailable without YouTube API key"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Duration</dt>
              <dd className="text-slate-200">
                {video.duration_seconds != null ? `${video.duration_seconds} seconds` : "Unavailable without YouTube API key"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Transcript</dt>
              <dd className="text-slate-200">{STATUS_LABELS[video.transcript_status] ?? video.transcript_status}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}

function ResultsList({ results }: { results: MentionSearchResponse }) {
  if (results.total_mentions === 0) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-slate-300">
        No mentions of {results.advertiser} were found in this transcript.
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
      <h2 className="text-xl font-medium text-white">
        {results.total_mentions} mention{results.total_mentions === 1 ? "" : "s"} of {results.advertiser}
      </h2>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="border-b border-slate-800 px-3 py-2 font-medium">Timestamp</th>
              <th className="border-b border-slate-800 px-3 py-2 font-medium">Mention</th>
              <th className="border-b border-slate-800 px-3 py-2 font-medium">Context</th>
              <th className="border-b border-slate-800 px-3 py-2 font-medium">Type</th>
              <th className="border-b border-slate-800 px-3 py-2 font-medium">Confidence</th>
              <th className="border-b border-slate-800 px-3 py-2 font-medium">Watch</th>
            </tr>
          </thead>
          <tbody>
            {results.mentions.map((mention) => (
              <MentionRow key={`${mention.timestamp_seconds}-${mention.matched_text}`} mention={mention} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MentionRow({ mention }: { mention: MentionItem }) {
  return (
    <tr className="align-top text-slate-200">
      <td className="border-b border-slate-800 px-3 py-3">
        <a href={mention.youtube_url} target="_blank" rel="noreferrer" className="text-sky-300 hover:underline">
          {mention.timestamp}
        </a>
      </td>
      <td className="border-b border-slate-800 px-3 py-3">{mention.text}</td>
      <td className="border-b border-slate-800 px-3 py-3 text-slate-400">
        {mention.context_before && <div>{mention.context_before}</div>}
        {mention.context_after && <div>{mention.context_after}</div>}
      </td>
      <td className="border-b border-slate-800 px-3 py-3 capitalize">{mention.mention_type}</td>
      <td className="border-b border-slate-800 px-3 py-3">{Math.round(mention.confidence * 100)}%</td>
      <td className="border-b border-slate-800 px-3 py-3">
        <a href={mention.youtube_url} target="_blank" rel="noreferrer" className="text-sky-300 hover:underline">
          Watch on YouTube
        </a>
      </td>
    </tr>
  );
}
