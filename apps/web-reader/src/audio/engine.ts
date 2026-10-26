import type { Cue } from "../types";

type Deck = {
  el: HTMLAudioElement;
  gain: GainNode;
  ready: boolean;
};

const FADE_DEFAULT = 2.4;

/**
 * Two-deck cue player. Every cue is a finished render, so the player only has
 * to do three things well: start a cue at the right offset, crossfade decks,
 * and loop inside the cue's usable window.
 */
export class CueEngine {
  private ctx: AudioContext | null = null;
  private decks: Deck[] = [];
  private active = 0;
  private volume = 0.85;
  private loop: { start: number; end: number } | null = null;
  private cue: Cue | null = null;
  private started = false;
  onCue?: (cue: Cue | null) => void;

  async unlock(): Promise<void> {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.decks = [0, 1].map(() => this.makeDeck());
    }
    await this.ctx.resume();
    this.started = true;
  }

  private makeDeck(): Deck {
    const el = new Audio();
    el.preload = "auto";
    el.crossOrigin = "anonymous";
    const source = this.ctx!.createMediaElementSource(el);
    const gain = this.ctx!.createGain();
    gain.gain.value = 0;
    source.connect(gain).connect(this.ctx!.destination);
    const deck: Deck = { el, gain, ready: false };
    el.addEventListener("timeupdate", () => {
      if (this.decks[this.active] !== deck) return;
      const loop = this.loop;
      if (loop && el.currentTime >= loop.end - 0.05) {
        el.currentTime = loop.start;
      }
    });
    return deck;
  }

  get enabled(): boolean {
    return this.started;
  }

  setVolume(v: number): void {
    this.volume = v;
    if (this.decks[this.active] && this.ctx) {
      this.decks[this.active].gain.gain.setTargetAtTime(v, this.ctx.currentTime, 0.05);
    }
  }

  get currentTime(): number {
    const d = this.decks[this.active];
    return d && d.ready ? d.el.currentTime : 0;
  }

  /** Start a cue from a fresh state (no crossfade) — used on chapter open. */
  async start(cue: Cue, at?: number): Promise<void> {
    await this.unlock();
    const deck = this.decks[this.active];
    this.cue = cue;
    this.loop = cue.loop;
    deck.el.src = cue.src;
    deck.ready = false;
    await this.waitCanPlay(deck.el);
    deck.el.currentTime = at ?? cue.loop.start;
    await deck.el.play().catch(() => undefined);
    deck.ready = true;
    this.decks[this.active].gain.gain.setTargetAtTime(this.volume, this.ctx!.currentTime, 0.15);
    this.onCue?.(cue);
  }

  /** Move to another cue, fading the old deck out. */
  async crossfade(cue: Cue, fade = FADE_DEFAULT, at?: number): Promise<void> {
    if (!this.ctx) {
      await this.start(cue, at);
      return;
    }
    if (this.cue?.src === cue.src) {
      this.cue = cue;
      this.loop = cue.loop;
      return;
    }
    const ctx = this.ctx;
    const now = ctx.currentTime;
    const old = this.decks[this.active];
    const nextIndex = 1 - this.active;
    const next = this.decks[nextIndex];

    next.el.src = cue.src;
    next.ready = false;
    await this.waitCanPlay(next.el);
    next.el.currentTime = at ?? (fade > 3 ? 0 : cue.loop.start);
    await next.el.play().catch(() => undefined);
    next.ready = true;

    next.gain.gain.cancelScheduledValues(now);
    next.gain.gain.setValueAtTime(0, now);
    next.gain.gain.linearRampToValueAtTime(this.volume, now + fade);

    old.gain.gain.cancelScheduledValues(now);
    old.gain.gain.setValueAtTime(old.gain.gain.value, now);
    old.gain.gain.linearRampToValueAtTime(0, now + fade);

    this.active = nextIndex;
    window.setTimeout(() => {
      old.el.pause();
    }, fade * 1000 + 150);

    this.cue = cue;
    this.loop = cue.loop;
    this.onCue?.(cue);
  }

  private waitCanPlay(el: HTMLAudioElement): Promise<void> {
    if (el.readyState >= 2) return Promise.resolve();
    return new Promise((resolve) => {
      const done = () => {
        el.removeEventListener("canplay", done);
        el.removeEventListener("loadeddata", done);
        resolve();
      };
      el.addEventListener("canplay", done);
      el.addEventListener("loadeddata", done);
      window.setTimeout(done, 4000);
    });
  }

  stop(): void {
    for (const deck of this.decks) {
      deck.el.pause();
      deck.gain.gain.value = 0;
    }
    this.cue = null;
    this.loop = null;
    this.onCue?.(null);
  }
}

export const engine = new CueEngine();
