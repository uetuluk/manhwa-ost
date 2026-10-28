import type { Chapter, Job, LibrarySeries, Manga, Timeline } from "./types";

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  popular: (limit = 18) => json<Manga[]>(`/api/mangadex/popular?limit=${limit}`),
  latest: (limit = 24) => json<Manga[]>(`/api/mangadex/latest?limit=${limit}`),
  library: () => json<LibrarySeries[]>("/api/library"),
  search: (q: string) => json<Manga[]>(`/api/mangadex/search?q=${encodeURIComponent(q)}`),
  manga: (id: string) => json<Manga>(`/api/mangadex/manga/${id}`),
  chapters: (id: string) => json<Chapter[]>(`/api/mangadex/manga/${id}/chapters`),
  pages: (mangaId: string, chapterId: string) =>
    json<{ page_count: number; pages: string[] }>(`/api/pages/${mangaId}/${chapterId}`),
  score: (mangaId: string, chapterId: string) =>
    json<Timeline>(`/api/score/mangadex/${mangaId}/${chapterId}`),
  compose: (body: Record<string, unknown>) =>
    json<Job>("/api/compose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  job: (id: string) => json<Job>(`/api/jobs/${id}`),
};
