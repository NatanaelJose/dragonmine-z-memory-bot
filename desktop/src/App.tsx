import { useEffect, useMemo, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import "./App.css";

type Speed = "fast" | "safe" | "custom";
type Direction = "up" | "down" | "left" | "right";
type Phase = "offline" | "searching" | "armed" | "memorizing" | "sending";
type Theme = "light" | "dark";

interface ProcessStatus {
  running: boolean;
}

interface LogEvent {
  stream: "stdout" | "stderr";
  line: string;
}

interface LogLine extends LogEvent {
  id: number;
  time: string;
}

const speedCopy: Record<Speed, { title: string; timing: string; note: string }> = {
  fast: { title: "Fast", timing: "30 / 30 ms", note: "Verified limit" },
  safe: { title: "Safe", timing: "50 / 50 ms", note: "More margin" },
  custom: { title: "Custom", timing: "Manual", note: "Fine control" },
};

const phaseCopy: Record<Phase, { eyebrow: string; title: string; detail: string }> = {
  offline: { eyebrow: "SYSTEM IDLE", title: "Bot standing by", detail: "Choose a speed profile and initialize the link." },
  searching: { eyebrow: "SCANNING", title: "Looking for DragonMine", detail: "Open the game window. Detection will lock automatically." },
  armed: { eyebrow: "LINK STABLE", title: "Ready for the next round", detail: "The detector is watching for a valid color sequence." },
  memorizing: { eyebrow: "SEQUENCE LOCKED", title: "Pattern memorized", detail: "Waiting for the symbols to clear before sending input." },
  sending: { eyebrow: "INPUT BURST", title: "Replaying sequence", detail: "Native arrow-key events are being sent to the game." },
};

const arrows: Record<Direction, string> = {
  up: "↑",
  down: "↓",
  left: "←",
  right: "→",
};

function parseSequence(line: string): Direction[] | null {
  if (!line.includes("MEMORIZE detectado") && !line.includes("Enviando sequencia")) return null;
  const list = line.match(/\[(.*)]/)?.[1];
  if (!list) return null;
  const values = [...list.matchAll(/['\"](up|down|left|right)['\"]/g)].map(
    (match) => match[1] as Direction,
  );
  return values.length ? values : null;
}

function phaseFromLog(line: string, current: Phase): Phase {
  if (line.includes("MEMORIZE detectado")) return "memorizing";
  if (line.includes("enviando sequencia") || line.includes("Enviando sequencia")) return "sending";
  if (line.includes("Sequencia enviada")) return "armed";
  if (line.includes("Janela encontrada") || line.includes("prompt=")) return "armed";
  if (line.includes("nao encontrada") || line.includes("aguardando ela voltar")) return "searching";
  return current;
}

function ThemeIcon({ theme }: { theme: Theme }) {
  return theme === "dark" ? (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.2 15.1A8.5 8.5 0 0 1 8.9 3.8 8.6 8.6 0 1 0 20.2 15Z" /></svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
  );
}

function App() {
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<Phase>("offline");
  const [speed, setSpeed] = useState<Speed>(() => (localStorage.getItem("speed") as Speed) || "fast");
  const [holdTime, setHoldTime] = useState(0.04);
  const [keyDelay, setKeyDelay] = useState(0.04);
  const [sequence, setSequence] = useState<Direction[]>([]);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("theme") as Theme | null;
    return saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  });
  const logId = useRef(0);
  const logEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("speed", speed);
  }, [speed]);

  useEffect(() => {
    if (!isTauri()) return;
    let alive = true;
    let unlisten: (() => void) | undefined;

    listen<LogEvent>("bot-log", ({ payload }) => {
      const detected = parseSequence(payload.line);
      if (detected) setSequence(detected);
      setPhase((current) => phaseFromLog(payload.line, current));
      if (payload.stream === "stderr") setError(payload.line);
      setLogs((current) => [
        ...current.slice(-119),
        { ...payload, id: ++logId.current, time: new Date().toLocaleTimeString([], { hour12: false }) },
      ]);
    }).then((dispose) => {
      if (alive) unlisten = dispose;
      else dispose();
    });

    const poll = async () => {
      try {
        const status = await invoke<ProcessStatus>("get_bot_status");
        if (!alive) return;
        setRunning(status.running);
        if (!status.running) setPhase("offline");
      } catch (reason) {
        if (alive) setError(String(reason));
      }
    };
    poll();
    const timer = window.setInterval(poll, 1200);
    return () => {
      alive = false;
      window.clearInterval(timer);
      unlisten?.();
    };
  }, []);

  useEffect(() => {
    logEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [logs]);

  const timing = useMemo(() => {
    if (speed === "fast") return { holdTime: 0.03, keyDelay: 0.03 };
    if (speed === "safe") return { holdTime: 0.05, keyDelay: 0.05 };
    return { holdTime, keyDelay };
  }, [speed, holdTime, keyDelay]);

  async function toggleBot() {
    setBusy(true);
    setError(null);
    try {
      if (running) {
        await invoke("stop_bot");
        setRunning(false);
        setPhase("offline");
      } else {
        const status = await invoke<ProcessStatus>("start_bot", {
          speed,
          holdTime: speed === "custom" ? timing.holdTime : null,
          keyDelay: speed === "custom" ? timing.keyDelay : null,
        });
        setRunning(status.running);
        setPhase("searching");
        setLogs([]);
        setSequence([]);
      }
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  const phaseInfo = phaseCopy[phase];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>PR</span></div>
          <div>
            <p className="overline">DRAGONMINE Z // CONTROL UNIT</p>
            <h1>Perfect Recall</h1>
          </div>
        </div>
        <div className="topbar-actions">
          <div className={`connection-chip ${running ? "is-online" : ""}`}>
            <span className="signal-dot" />
            {running ? "CORE ONLINE" : "CORE OFFLINE"}
          </div>
          <button className="icon-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            <ThemeIcon theme={theme} />
          </button>
        </div>
      </header>

      <section className="command-deck">
        <div className="status-stage">
          <div className={`scanner ${running ? "is-active" : ""}`} aria-hidden="true">
            <div className="scanner-ring ring-one" />
            <div className="scanner-ring ring-two" />
            <div className="scanner-crosshair" />
            <span>{running ? "LIVE" : "IDLE"}</span>
          </div>
          <div className="status-copy">
            <p className="status-eyebrow">{phaseInfo.eyebrow}</p>
            <h2>{phaseInfo.title}</h2>
            <p>{phaseInfo.detail}</p>
          </div>
          <button className={`power-button ${running ? "stop" : "start"}`} onClick={toggleBot} disabled={busy}>
            <span className="power-symbol" aria-hidden="true" />
            <span>
              <small>{busy ? "PROCESSING" : running ? "END SESSION" : "INITIALIZE"}</small>
              {busy ? "Please wait" : running ? "Stop bot" : "Start bot"}
            </span>
          </button>
        </div>

        <div className="sequence-panel">
          <div className="section-heading">
            <div>
              <p className="overline">MEMORY BUFFER</p>
              <h3>Last sequence</h3>
            </div>
            <span className="sequence-count">{String(sequence.length).padStart(2, "0")} INPUTS</span>
          </div>
          <div className={`sequence-track ${sequence.length ? "has-data" : ""}`}>
            {sequence.length ? sequence.map((direction, index) => (
              <div className={`direction direction-${direction}`} key={`${direction}-${index}`} style={{ "--index": index } as React.CSSProperties}>
                <span>{arrows[direction]}</span>
                <small>{index + 1}</small>
              </div>
            )) : (
              <div className="sequence-empty">
                <span className="empty-pulse" />
                Awaiting visual lock
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="lower-deck">
        <div className="speed-control">
          <div className="section-heading">
            <div>
              <p className="overline">INPUT CALIBRATION</p>
              <h3>Response profile</h3>
            </div>
            <span className="timing-readout">{Math.round(timing.holdTime * 1000)} / {Math.round(timing.keyDelay * 1000)} ms</span>
          </div>
          <div className="speed-selector" role="radiogroup" aria-label="Input speed">
            {(Object.keys(speedCopy) as Speed[]).map((option) => (
              <button key={option} role="radio" aria-checked={speed === option} className={speed === option ? "selected" : ""} onClick={() => setSpeed(option)} disabled={running}>
                <span>{speedCopy[option].title}</span>
                <strong>{speedCopy[option].timing}</strong>
                <small>{speedCopy[option].note}</small>
              </button>
            ))}
          </div>
          <div className={`custom-timing ${speed === "custom" ? "is-open" : ""}`} aria-hidden={speed !== "custom"}>
            <label>
              Hold time
              <span><input type="number" min="0.025" max="0.2" step="0.005" value={holdTime} onChange={(event) => setHoldTime(Number(event.target.value))} disabled={running || speed !== "custom"} /> seconds</span>
            </label>
            <label>
              Key interval
              <span><input type="number" min="0.025" max="0.2" step="0.005" value={keyDelay} onChange={(event) => setKeyDelay(Number(event.target.value))} disabled={running || speed !== "custom"} /> seconds</span>
            </label>
          </div>
        </div>

        <div className="telemetry">
          <div className="section-heading">
            <div>
              <p className="overline">LIVE TELEMETRY</p>
              <h3>Runtime feed</h3>
            </div>
            <button className="text-button" onClick={() => setLogs([])} disabled={!logs.length}>Clear</button>
          </div>
          <div className="log-window" aria-live="polite">
            {logs.length ? logs.map((entry) => (
              <div className={`log-line ${entry.stream === "stderr" ? "is-error" : ""}`} key={entry.id}>
                <time>{entry.time}</time><span>{entry.line}</span>
              </div>
            )) : (
              <div className="log-empty">Telemetry will appear after initialization.</div>
            )}
            <div ref={logEnd} />
          </div>
        </div>
      </section>

      {error && (
        <aside className="error-strip" role="alert">
          <strong>LINK ERROR</strong><span>{error}</span><button onClick={() => setError(null)} aria-label="Dismiss error">×</button>
        </aside>
      )}

      <footer>
        <span>PERFECT RECALL // v0.1.0</span>
        <span>LOCAL PROCESSING · NO FRAME UPLOAD</span>
      </footer>
    </main>
  );
}

export default App;
