import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Reader } from "./components/Reader";
import type { Chapter, Manga } from "./types";

type View = { name: "browse" } | { name: "series"; manga: Manga } | { name: "reader"; manga: Manga; chapter: Chapter };

export default function App() {
  const [view, setView] = useState<View>({ name: "browse" });
  const [popular, setPopular] = useState<Manga[]>([]);
  const [results, setResults] = useState<Manga[] | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [seriesLoading, setSeriesLoading] = useState(false);

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
      .popular(18)
      .then(setPopular)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

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

  const openSeriesRef = useRef<(m: Manga) => void>(undefined);

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

  openSeriesRef.current = openSeries;

  if (view.name === "reader") {
    return (
      <Reader
        manga={view.manga}
        chapter={view.chapter}
        onBack={() => {
          window.location.hash = `#/m/${view.manga.id}`;
          setView({ name: "series", manga: view.manga });
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
          {m.cover && <img className="cover" src={`/api/image?u=${encodeURIComponent(m.cover)}`} alt="" />}
          <div>
            <h1>{m.title}</h1>
            <p className="muted">
              {[m.status, m.year, ...(m.tags ?? []).slice(0, 3)].filter(Boolean).join(" · ")}
            </p>
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
          {!seriesLoading && chapters.length === 0 && <div className="muted">No English chapters on this source.</div>}
          <ul>
            {chapters.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => {
                    window.location.hash = `#/c/${m.id}/${c.id}`;
                    setView({ name: "reader", manga: m, chapter: c });
                  }}
                >
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

  const list = results ?? popular;
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

      <section className="sources">
        <div className="source-card active">
          <div className="source-name">MangaDex</div>
          <div className="muted">public API · english chapters</div>
        </div>
        <div className="source-card">
          <div className="source-name">Local CBZ</div>
          <div className="muted">not wired yet</div>
        </div>
        <div className="source-card">
          <div className="source-name">Mihon extensions</div>
          <div className="muted">android-only, deferred to the Mihon fork</div>
        </div>
      </section>

      {error && <div className="error">{error}</div>}
      {loading && <div className="muted">loading…</div>}

      <section className="grid">
        {list.map((m) => (
          <article key={m.id} className="card" onClick={() => openSeries(m)}>
            {m.cover ? (
              <img src={`/api/image?u=${encodeURIComponent(m.cover)}`} alt="" loading="lazy" />
            ) : (
              <div className="no-cover" />
            )}
            <div className="card-body">
              <strong>{m.title}</strong>
              <span className="muted">{[m.status, m.year].filter(Boolean).join(" · ")}</span>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
