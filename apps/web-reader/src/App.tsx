import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Reader } from "./components/Reader";
import type { Chapter, LibrarySeries, Manga } from "./types";

type View = { name: "browse" } | { name: "series"; manga: Manga } | { name: "reader"; manga: Manga; chapter: Chapter };
type Tab = "latest" | "popular" | "library";

const coverSrc = (cover?: string | null) => (cover ? `/api/image?u=${encodeURIComponent(cover)}` : null);

export default function App() {
  const [view, setView] = useState<View>({ name: "browse" });
  const [tab, setTab] = useState<Tab>("latest");
  const [latest, setLatest] = useState<Manga[]>([]);
  const [popular, setPopular] = useState<Manga[] | null>(null);
  const [library, setLibrary] = useState<LibrarySeries[] | null>(null);
  const [results, setResults] = useState<Manga[] | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const openSeriesRef = useRef<(m: Manga) => void>(undefined);

  // Deep links: #/m/<mangaId> and #/c/<mangaId>/<chapterId>
  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "");
    const parts = hash.split("/").filter(Boolean);
    if (parts[0] === "c" && parts[1] && parts[2]) {
      Promise.all([api.manga(parts[1]), api.chapters(parts[1])])
        .then(([m, chs]) => {
          const chapter = chs.find((c) => c.id === parts[2]);
          if (chapter) {
            setChapters(chs);
            setView({ name: "reader", manga: m, chapter });
          }
        })
        .catch((e) => setError(String(e)));
    } else if (parts[0] === "m" && parts[1]) {
      api
        .manga(parts[1])
        .then((m) => openSeriesRef.current?.(m))
        .catch((e) => setError(String(e)));
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    api
      .latest(24)
      .then(setLatest)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (tab === "popular" && !popular) {
      setLoading(true);
      api
        .popular(24)
        .then(setPopular)
        .catch((e) => setError(String(e)))
        .finally(() => setLoading(false));
    }
    if (tab === "library" && !library) {
      setLoading(true);
      api
        .library()
        .then(setLibrary)
        .catch((e) => setError(String(e)))
        .finally(() => setLoading(false));
    }
  }, [tab, popular, library]);

  const search = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!query.trim()) {
        setResults(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        setResults(await api.search(query.trim()));
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    },
    [query],
  );

  const openSeries = useCallback(async (manga: Manga) => {
    window.location.hash = `#/m/${manga.id}`;
    setView({ name: "series", manga });
    setSeriesLoading(true);
    setChapters([]);
    try {
      setChapters(await api.chapters(manga.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setSeriesLoading(false);
    }
  }, []);

  const openChapter = useCallback((manga: Manga, chapter: Chapter) => {
    window.location.hash = `#/c/${manga.id}/${chapter.id}`;
    setView({ name: "reader", manga, chapter });
  }, []);

  openSeriesRef.current = openSeries;

  if (view.name === "reader") {
    const { manga, chapter } = view;
    return (
      <Reader
        manga={manga}
        chapter={chapter}
        onBack={() => {
          window.location.hash = `#/m/${manga.id}`;
          setView({ name: "series", manga });
          api.chapters(manga.id).then(setChapters).catch(() => undefined);
        }}
      />
    );
  }

  if (view.name === "series") {
    const m = view.manga;
    return (
      <div className="shell">
        <button className="ghost back" onClick={() => setView({ name: "browse" })}>
          ← Library
        </button>
        <section className="series-head">
          {coverSrc(m.cover) && <img className="cover" src={coverSrc(m.cover)!} alt="" />}
          <div>
            <h1>{m.title}</h1>
            <p className="muted">{[m.status, m.year, ...(m.tags ?? []).slice(0, 3)].filter(Boolean).join(" · ")}</p>
            <p className="desc">{m.description}</p>
            <div className="chips">
              <span className="chip">{chapters.length} chapters available</span>
              <span className="chip">source: MangaDex</span>
            </div>
          </div>
        </section>

        <section className="chapters">
          <h2>Chapters</h2>
          {seriesLoading && <div className="muted">loading…</div>}
          {!seriesLoading && chapters.length === 0 && (
            <div className="empty">
              <p>
                This series has no readable English chapters on MangaDex — licensed titles are removed from the
                source, even though the series entry stays.
              </p>
              <button onClick={() => setView({ name: "browse" })}>Browse something readable →</button>
            </div>
          )}
          <ul>
            {chapters.map((c) => (
              <li key={c.id}>
                <button onClick={() => openChapter(m, c)}>
                  <span className="ch-num">Ch. {c.number ?? "?"}</span>
                  <span className="ch-title">{c.title ?? ""}</span>
                  <span className="ch-pages">{c.pages ?? "?"}p</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    );
  }

  const list = results ?? (tab === "latest" ? latest : tab === "popular" ? popular ?? [] : []);
  const lib = library ?? [];

  return (
    <div className="shell">
      <header className="masthead">
        <div>
          <h1>manhwa-ost</h1>
          <p className="muted">a reader that scores what you read</p>
        </div>
        <form onSubmit={search} className="search">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search MangaDex…" />
          <button type="submit">Search</button>
          {results && (
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setResults(null);
                setQuery("");
              }}
            >
              Clear
            </button>
          )}
        </form>
      </header>

      <nav className="tabs">
        {(["latest", "popular", "library"] as Tab[]).map((t) => (
          <button key={t} className={tab === t && !results ? "tab active" : "tab"} onClick={() => { setTab(t); setResults(null); }}>
            {t === "latest" ? "Latest updates" : t === "popular" ? "Popular manhwa" : "Local library"}
          </button>
        ))}
        <span className="muted source-note">
          {results ? `${results.length} results` : tab === "library" ? "already downloaded & composed" : "MangaDex · English"}
        </span>
      </nav>

      {error && <div className="error">{error}</div>}
      {loading && <div className="muted">loading…</div>}

      {!results && tab === "library" ? (
        <section className="library">
          {lib.length === 0 && !loading && <div className="muted">Nothing composed yet — compose a chapter first.</div>}
          {lib.map((entry) => (
            <div key={entry.series.id} className="lib-series">
              <h3>{entry.series.title}</h3>
              <ul>
                {entry.chapters.map((c) => (
                  <li key={c.chapter_id}>
                    <button
                      onClick={() =>
                        openChapter(entry.series, {
                          id: c.chapter_id,
                          number: c.number,
                          title: c.title,
                          pages: c.page_count,
                        })
                      }
                    >
                      <span className="ch-num">Ch. {c.number ?? "?"}</span>
                      <span className="ch-title">{c.title ?? ""}</span>
                      <span className="ch-pages">{c.sections} sections</span>
                      <span className={`badge ${c.composed ? "ok" : ""}`}>{c.composed ? "scored" : "analyzed"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      ) : (
        <section className="grid">
          {list.map((m) => (
            <article key={m.id} className="card" onClick={() => openSeries(m)}>
              {coverSrc(m.cover) ? (
                <img src={coverSrc(m.cover)!} alt="" loading="lazy" />
              ) : (
                <div className="no-cover" />
              )}
              <div className="card-body">
                <strong>{m.title}</strong>
                <span className="muted">
                  {m.latest_chapter ? `latest ch. ${m.latest_chapter.number ?? "?"}` : [m.status, m.year].filter(Boolean).join(" · ")}
                </span>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
