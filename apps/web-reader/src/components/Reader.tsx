import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { engine } from "../audio/engine";
import type { Chapter, Cue, Job, Manga, Section, Timeline } from "../types";

type Props = {
  manga: Manga;
  chapter: Chapter;
  onBack: () => void;
};

const HEAD_PROBE = 0.42;

export function Reader({ manga, chapter, onBack }: Props) {
  const [pages, setPages] = useState<string[]>([]);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ostOn, setOstOn] = useState(false);
  const [current, setCurrent] = useState<Section | null>(null);
  const [cue, setCue] = useState<Cue | null>(null);
  const [showSheet, setShowSheet] = useState(false);
  const [progress, setProgress] = useState(0);

  const tops = useRef<number[]>([]);
  const heights = useRef<number[]>([]);
  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);
  const pagesRef = useRef<HTMLDivElement | null>(null);
  const sectionRef = useRef<Section | null>(null);
  const timelineRef = useRef<Timeline | null>(null);
  const ostOnRef = useRef(false);

  timelineRef.current = timeline;
  ostOnRef.current = ostOn;

  const sections = timeline?.sections ?? [];

  useEffect(() => {
    engine.onCue = (c) => setCue(c);
  }, []);

  // pages
  useEffect(() => {
    let cancelled = false;
    api
      .pages(manga.id, chapter.id)
      .then((d) => !cancelled && setPages(d.pages))
      .catch((e) => setError(String(e)));
    api
      .score(manga.id, chapter.id)
      .then((t) => !cancelled && !("analysis_only" in t) && setTimeline(t))
      .catch(() => undefined);
    return () => {
      cancelled = true;
      engine.stop();
    };
  }, [chapter.id, manga.id]);

  // job polling
  useEffect(() => {
    if (!job || job.status === "done" || job.status === "error") return;
    const id = window.setInterval(async () => {
      try {
        const next = await api.job(job.id);
        setJob(next);
        if (next.status === "done") {
          const t = await api.score(manga.id, chapter.id);
          setTimeline(t);
          setJob(null);
        }
      } catch (e) {
        setError(String(e));
        setJob(null);
      }
    }, 1500);
    return () => window.clearInterval(id);
  }, [job, manga.id, chapter.id]);

  const measure = useCallback(() => {
    tops.current = pageRefs.current.map((el) => (el ? el.offsetTop : 0));
    heights.current = pageRefs.current.map((el) => (el ? el.offsetHeight : 1));
  }, []);

  useEffect(() => {
    measure();
    const onResize = () => measure();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [pages, measure]);

  const goToPage = useCallback((page: number) => {
    const el = pageRefs.current[page - 1];
    if (el) window.scrollTo({ top: el.offsetTop - 8, behavior: "smooth" });
  }, []);

  const applySection = useCallback(
    (section: Section | undefined, sectionIndex: number, pageFraction: number) => {
      if (!section) return;
      if (sectionRef.current?.index === section.index) return;
      const previous = sectionRef.current;
      sectionRef.current = section;
      setCurrent(section);

      const tl = timelineRef.current;
      if (!tl || !ostOnRef.current) return;
      const target = tl.cues[section.cue_id];
      if (!target) return;

      const onePage = section.start_page === section.end_page;
      const offset = onePage || pageFraction > 0.5 ? target.loop.start : 0;
      const fade = section.transition_in === "cut" ? 0.7 : section.transition_in === "swell" ? 4.5 : 2.4;

      if (!previous || sectionIndex === 0) {
        void engine.start(target, offset);
      } else {
        void engine.crossfade(target, fade, offset);
      }
    },
    [],
  );

  // page under the probe line → progress → section
  const sync = useCallback(() => {
    const t = tops.current;
    if (!t.length) return;
    // Images report zero height until they decode; a probe against zeroed
    // offsets would claim the last page. Wait for real layout.
    if (t[t.length - 1] === 0) return;
    const probe = window.scrollY + window.innerHeight * HEAD_PROBE;
    let i = 0;
    while (i + 1 < t.length && t[i + 1] <= probe) i++;
    const h = heights.current[i] || 1;
    const frac = Math.max(0, Math.min(1, (probe - t[i]) / h));
    const page = Math.min(t.length, i + 1);
    setProgress((i + frac) / t.length);

    const tl = timelineRef.current;
    if (!tl) return;
    const idx = tl.sections.findIndex((s) => page >= s.start_page && page <= s.end_page);
    if (idx >= 0) applySection(tl.sections[idx], idx, frac);
  }, [applySection]);

  useEffect(() => {
    let raf = 0;
    const onScroll = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(() => {
        raf = 0;
        sync();
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    sync();
    return () => window.removeEventListener("scroll", onScroll);
  }, [pages, sync]);

  // Re-measure and re-sync when images finish decoding (and on any reflow).
  useEffect(() => {
    const el = pagesRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      measure();
      sync();
    });
    ro.observe(el);
    const t = window.setTimeout(() => {
      measure();
      sync();
    }, 400);
    return () => {
      ro.disconnect();
      window.clearTimeout(t);
    };
  }, [pages, measure, sync]);

  const toggleOst = async () => {
    if (ostOn) {
      engine.stop();
      setOstOn(false);
      return;
    }
    await engine.unlock();
    setOstOn(true);
    ostOnRef.current = true;
    const tl = timelineRef.current;
    if (tl && current) {
      const target = tl.cues[current.cue_id];
      if (target) await engine.start(target, target.loop.start);
    } else if (tl) {
      const first = tl.sections[0];
      const target = tl.cues[first.cue_id];
      if (target) {
        sectionRef.current = first;
        setCurrent(first);
        await engine.start(target, target.loop.start);
      }
    }
  };

  const compose = async () => {
    setError(null);
    try {
      const j = await api.compose({
        manga_id: manga.id,
        chapter_id: chapter.id,
        series_title: manga.title,
        chapter_number: chapter.number ?? "?",
        chapter_title: chapter.title,
      });
      setJob(j);
    } catch (e) {
      setError(String(e));
    }
  };

  const currentCue = useMemo(() => (current && timeline ? timeline.cues[current.cue_id] : null), [current, timeline]);

  return (
    <div className="reader">
      <header className="reader-bar">
        <button className="ghost" onClick={onBack}>
          ←
        </button>
        <div className="titles">
          <strong>{manga.title}</strong>
          <span>
            Ch. {chapter.number} {chapter.title ? `· ${chapter.title}` : ""}
          </span>
        </div>
        <div className="bar-actions">
          {timeline && (
            <>
              <button className={`ost ${ostOn ? "on" : ""}`} onClick={toggleOst}>
                {ostOn ? "OST on" : "Enable OST"}
              </button>
              <button className="ghost" onClick={() => setShowSheet((v) => !v)}>
                Score
              </button>
            </>
          )}
          {!timeline && !job && (
            <button className="ost" onClick={compose}>
              Compose OST
            </button>
          )}
        </div>
      </header>

      {job && (
        <div className="jobbar">
          <div className="jobbar-fill" style={{ width: `${Math.round(job.progress * 100)}%` }} />
          <span>
            {job.step} · {Math.round(job.progress * 100)}%
          </span>
        </div>
      )}
      {error && <div className="error">{error}</div>}

      {currentCue && ostOn && (
        <div className="now">
          <span className="now-motif">{currentCue.motif}</span>
          <span className="now-label">{current?.label}</span>
          <span className="now-meta">
            {currentCue.key} · {Math.round(currentCue.tempo_bpm)} bpm
          </span>
        </div>
      )}

      <div className="pages" ref={pagesRef}>
        {pages.map((src, i) => {
          const marker = timeline?.sections.find((s) => s.start_page === i + 1);
          return (
            <div key={src}>
              {marker && (
                <div className={`section-marker ${current?.index === marker.index ? "active" : ""}`}>
                  <span className="sm-index">§{marker.index}</span>
                  <span className="sm-label">{marker.label}</span>
                  <span className="sm-meta">
                    {marker.motif} · {marker.mood.join("/")} · e{marker.energy.toFixed(2)}
                  </span>
                </div>
              )}
              <div
                className="page"
                ref={(el) => {
                  pageRefs.current[i] = el;
                }}
              >
                <img src={src} alt={`page ${i + 1}`} loading={i < 3 ? "eager" : "lazy"} decoding="async" />
              </div>
            </div>
          );
        })}
      </div>

      {timeline && (
        <nav className="rail" aria-label="AI sections">
          <div className="rail-track">
            {timeline.sections.map((s) => {
              const top = ((s.start_page - 1) / (timeline.chapter.page_count || 1)) * 100;
              const active = current?.index === s.index;
              return (
                <button
                  key={s.index}
                  className={`tick ${active ? "active" : ""}`}
                  style={{ top: `${top}%` }}
                  onClick={() => goToPage(s.start_page)}
                  title={`${s.label} · ${s.motif}`}
                >
                  <span className="tick-dot" />
                  <span className="tick-label">{s.label}</span>
                </button>
              );
            })}
            <div className="rail-progress" style={{ height: `${progress * 100}%` }} />
          </div>
        </nav>
      )}

      {showSheet && timeline && (
        <aside className="sheet">
          <div className="sheet-head">
            <h3>Score sheet</h3>
            <button className="ghost" onClick={() => setShowSheet(false)}>
              ✕
            </button>
          </div>
          <ol>
            {timeline.sections.map((s) => {
              const c = timeline.cues[s.cue_id];
              return (
                <li
                  key={s.index}
                  className={current?.index === s.index ? "active" : ""}
                  onClick={() => {
                    goToPage(s.start_page);
                    setShowSheet(false);
                  }}
                >
                  <div className="sheet-line">
                    <span className="sheet-idx">{s.index}</span>
                    <strong>{s.label}</strong>
                    <span className="sheet-pages">
                      p.{s.start_page}–{s.end_page}
                    </span>
                  </div>
                  <div className="sheet-meta">
                    {s.mood.join(" / ")} · energy {s.energy.toFixed(2)} · {s.motif}
                    {c ? ` · ${c.key} ${Math.round(c.tempo_bpm)}bpm` : ""}
                  </div>
                  <div className="sheet-arr">{s.arrangement}</div>
                </li>
              );
            })}
          </ol>
        </aside>
      )}
    </div>
  );
}
