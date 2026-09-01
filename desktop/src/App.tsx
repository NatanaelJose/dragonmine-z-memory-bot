import { useEffect, useMemo, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import "./App.css";
import { translations, type Language } from "./i18n";

type Speed = "fast" | "safe" | "custom";
type GameMode = "memory" | "rhythm";
type Direction = "up" | "down" | "left" | "right";
type Phase = "offline" | "searching" | "armed" | "memorizing" | "sending" | "tracking";
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
  if (line.includes("RHYTHM:TRACKING") || line.includes("RHYTHM:HIT") || line.includes("RHYTHM:HOLD")) return "tracking";
  if (line.includes("RHYTHM:READY") || line.includes("RHYTHM:START")) return "armed";
  if (line.includes("RHYTHM:WAITING")) return "searching";
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
  const [game, setGame] = useState<GameMode>(() => localStorage.getItem("game") === "rhythm" ? "rhythm" : "memory");
  const [speed, setSpeed] = useState<Speed>(() => (localStorage.getItem("speed") as Speed) || "fast");
  const [holdTime, setHoldTime] = useState(0.04);
  const [keyDelay, setKeyDelay] = useState(0.04);
  const [sequence, setSequence] = useState<Direction[]>([]);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language>(() => localStorage.getItem("language") === "pt-BR" ? "pt-BR" : "en");
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
    document.documentElement.lang = language;
    localStorage.setItem("language", language);
  }, [language]);

  useEffect(() => {
    localStorage.setItem("speed", speed);
  }, [speed]);

  useEffect(() => {
    localStorage.setItem("game", game);
  }, [game]);

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
          game,
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

  function selectGame(mode: GameMode) {
    if (running) return;
    setGame(mode);
    setPhase("offline");
    setLogs([]);
    setSequence([]);
  }

  const isRhythm = game === "rhythm";
  const copy = translations[language];
  const speedCopy = copy.speed;
  const phaseCopy = copy.phase;
  const gameCopy = copy.game;
  const phaseInfo = phase === "offline" && isRhythm
    ? copy.rhythmIdle
    : phaseCopy[phase];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>PR</span></div>
          <div>
            <p className="overline">{copy.brandOverline}</p>
            <h1>Perfect Recall</h1>
          </div>
        </div>
        <div className="topbar-actions">
          <div className={`connection-chip ${running ? "is-online" : ""}`}>
            <span className="signal-dot" />
            {running ? copy.online : copy.offline}
          </div>
          <div className="language-switcher" role="group" aria-label={copy.languageLabel}>
            <button className={language === "en" ? "is-selected" : ""} onClick={() => setLanguage("en")} aria-pressed={language === "en"} title={copy.english}>EN</button>
            <button className={language === "pt-BR" ? "is-selected" : ""} onClick={() => setLanguage("pt-BR")} aria-pressed={language === "pt-BR"} title={copy.portuguese}>PT</button>
          </div>
          <button className="icon-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={copy.themeLabel(theme === "dark" ? copy.light : copy.dark)}>
            <ThemeIcon theme={theme} />
          </button>
        </div>
      </header>

      <nav className="game-switcher" aria-label={copy.gameMode}>
        {(Object.keys(gameCopy) as GameMode[]).map((mode) => (
          <button
            key={mode}
            className={game === mode ? "is-selected" : ""}
            onClick={() => selectGame(mode)}
            disabled={running}
            aria-pressed={game === mode}
          >
            <small>{gameCopy[mode].kicker}</small>
            <strong>{gameCopy[mode].label}</strong>
            <span>{gameCopy[mode].description}</span>
          </button>
        ))}
      </nav>

      <section className="command-deck">
        <div className="status-stage">
          <div className={`scanner ${running ? "is-active" : ""}`} aria-hidden="true">
            <div className="scanner-ring ring-one" />
            <div className="scanner-ring ring-two" />
            <div className="scanner-crosshair" />
            <span>{running ? copy.live : copy.idle}</span>
          </div>
          <div className="status-copy">
            <p className="status-eyebrow">{phaseInfo.eyebrow}</p>
            <h2>{phaseInfo.title}</h2>
            <p>{phaseInfo.detail}</p>
          </div>
          <button className={`power-button ${running ? "stop" : "start"}`} onClick={toggleBot} disabled={busy}>
            <span className="power-symbol" aria-hidden="true" />
            <span>
              <small>{busy ? copy.processing : running ? copy.endSession : copy.initialize}</small>
              {busy ? copy.pleaseWait : running ? copy.stopBot : isRhythm ? copy.startRhythm : copy.startBot}
            </span>
          </button>
        </div>

        <div className="sequence-panel">
          <div className="section-heading">
            <div>
              <p className="overline">{isRhythm ? copy.dualLane : copy.memoryBuffer}</p>
              <h3>{isRhythm ? copy.liveGeometry : copy.lastSequence}</h3>
            </div>
            <span className="sequence-count">{isRhythm ? copy.tapHold : `${String(sequence.length).padStart(2, "0")} ${copy.inputs}`}</span>
          </div>
          {isRhythm ? (
            <div className="rhythm-target">
              <div className="lane-visual" aria-hidden="true">
                <span className="note note-left">←</span>
                <span className="hit-line line-left" />
                <span className="lane-core">PR</span>
                <span className="hit-line line-right" />
                <span className="note note-up">↑</span>
              </div>
              <div className="capture-result">
                <strong>{copy.centerPrediction}</strong>
                <span>{copy.centerPredictionDetail}</span>
              </div>
            </div>
          ) : (
          <div className={`sequence-track ${sequence.length ? "has-data" : ""}`}>
            {sequence.length ? sequence.map((direction, index) => (
              <div className={`direction direction-${direction}`} key={`${direction}-${index}`} style={{ "--index": index } as React.CSSProperties}>
                <span>{arrows[direction]}</span>
                <small>{index + 1}</small>
              </div>
            )) : (
              <div className="sequence-empty">
                <span className="empty-pulse" />
                {copy.awaitingLock}
              </div>
            )}
          </div>
          )}
        </div>
      </section>

      <section className="lower-deck">
        {isRhythm ? (
        <div className="capture-protocol">
          <div className="section-heading">
            <div>
              <p className="overline">{copy.autoplayProtocol}</p>
              <h3>{copy.beforeInitialization}</h3>
            </div>
            <span className="timing-readout">{copy.live}</span>
          </div>
          <ol className="protocol-list">
            {copy.protocol.map(([title, detail], index) => (
              <li key={title}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{title}</strong><small>{detail}</small></div></li>
            ))}
          </ol>
        </div>
        ) : (
        <div className="speed-control">
          <div className="section-heading">
            <div>
              <p className="overline">{copy.inputCalibration}</p>
              <h3>{copy.responseProfile}</h3>
            </div>
            <span className="timing-readout">{Math.round(timing.holdTime * 1000)} / {Math.round(timing.keyDelay * 1000)} ms</span>
          </div>
          <div className="speed-selector" role="radiogroup" aria-label={copy.inputSpeed}>
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
              {copy.holdTime}
              <span><input type="number" min="0.025" max="0.2" step="0.005" value={holdTime} onChange={(event) => setHoldTime(Number(event.target.value))} disabled={running || speed !== "custom"} /> {copy.seconds}</span>
            </label>
            <label>
              {copy.keyInterval}
              <span><input type="number" min="0.025" max="0.2" step="0.005" value={keyDelay} onChange={(event) => setKeyDelay(Number(event.target.value))} disabled={running || speed !== "custom"} /> {copy.seconds}</span>
            </label>
          </div>
        </div>
        )}

        <div className="telemetry">
          <div className="section-heading">
            <div>
              <p className="overline">{copy.liveTelemetry}</p>
              <h3>{copy.runtimeFeed}</h3>
            </div>
            <button className="text-button" onClick={() => setLogs([])} disabled={!logs.length}>{copy.clear}</button>
          </div>
          <div className="log-window" aria-live="polite">
            {logs.length ? logs.map((entry) => (
              <div className={`log-line ${entry.stream === "stderr" ? "is-error" : ""}`} key={entry.id}>
                <time>{entry.time}</time><span>{entry.line}</span>
              </div>
            )) : (
              <div className="log-empty">{copy.telemetryEmpty}</div>
            )}
            <div ref={logEnd} />
          </div>
        </div>
      </section>

      {error && (
        <aside className="error-strip" role="alert">
          <strong>{copy.linkError}</strong><span>{error}</span><button onClick={() => setError(null)} aria-label={copy.dismissError}>×</button>
        </aside>
      )}

      <footer>
        <span>PERFECT RECALL // v0.2.1</span>
        <span>{copy.localProcessing}</span>
      </footer>
    </main>
  );
}

export default App;
