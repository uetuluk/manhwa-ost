export type Manga = {
  id: string;
  title: string;
  description?: string;
  status?: string;
  year?: number | null;
  original_language?: string;
  tags?: string[];
  cover?: string | null;
  latest_chapter?: { chapter_id: string; number: string | null; title: string | null; pages: number | null };
};

export type LibraryChapter = {
  chapter_id: string;
  number: string | null;
  title: string | null;
  page_count: number | null;
  composed: boolean;
  sections: number;
};

export type LibrarySeries = {
  series: Manga & { id: string };
  chapters: LibraryChapter[];
};

export type Chapter = {
  id: string;
  number: string | null;
  title: string | null;
  pages: number | null;
  published_at?: string;
};

export type Section = {
  index: number;
  start_page: number;
  end_page: number;
  label: string;
  summary?: string;
  mood: string[];
  energy: number;
  tension: number;
  motif: string;
  arrangement: string;
  transition_in?: "cut" | "crossfade" | "swell";
  cue_id: string;
};

export type Cue = {
  src: string;
  duration_s: number;
  key: string;
  tempo_bpm: number;
  loudness_db: number;
  loop: { start: number; end: number };
  style: string;
  motif: string;
};

export type Timeline = {
  schema_version: number;
  series: { title: string; manga_id: string; source: string };
  chapter: { number: string; title: string | null; page_count: number };
  sections: Section[];
  cues: Record<string, Cue>;
  music?: { abc: string; cue_seconds: number; motifs: string[] };
  generated_at?: string;
  wall_seconds?: number;
};

export type Job = {
  id: string;
  status: "queued" | "running" | "done" | "error";
  progress: number;
  step: string;
  error: string | null;
  result?: Timeline | null;
};
