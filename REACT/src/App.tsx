import { useEffect, useRef, useState } from "react";

type IconName =
  | "wave"
  | "folder"
  | "play"
  | "chevron"
  | "check"
  | "loader"
  | "circle"
  | "copy"
  | "external"
  | "trash"
  | "file"
  | "link"
  | "settings"
  | "alert"
  | "spark";

type StageState = "not-started" | "processing" | "completed" | "failed";
type Stage = {
  id: number;
  name: string;
  description: string;
  state: StageState;
};
type LogEntry = {
  time: string;
  text: string;
  tone: "neutral" | "success" | "processing" | "error";
};

const stageDescriptions = [
  "Import or download source audio",
  "Prepare the working WAV file",
  "Extract the vocal audio track",
  "Create speaker-labeled segments",
];

const initialStages: Stage[] = [
  { id: 1, name: "Ingest", description: stageDescriptions[0], state: "completed" },
  { id: 2, name: "Convert", description: stageDescriptions[1], state: "completed" },
  { id: 3, name: "Separate", description: stageDescriptions[2], state: "processing" },
  { id: 4, name: "Diarize", description: stageDescriptions[3], state: "not-started" },
];

const initialLogs: LogEntry[] = [
  { time: "10:24:01", text: "PodSieve initialized.", tone: "neutral" },
  { time: "10:24:03", text: "Input source selected.", tone: "neutral" },
  { time: "10:24:05", text: "Ingest started.", tone: "processing" },
  { time: "10:24:18", text: "Ingest completed successfully.", tone: "success" },
  { time: "10:24:20", text: "Convert started.", tone: "processing" },
  { time: "10:24:36", text: "Convert completed successfully.", tone: "success" },
  { time: "10:24:38", text: "Separate started.", tone: "processing" },
];

function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  const paths: Record<IconName, React.ReactNode> = {
    wave: (
      <>
        <path d="M3 13v-2M7 17V7M11 20V4M15 17V7M19 14v-4M23 13v-2" />
      </>
    ),
    folder: <path d="M3 18.5V6.8A1.8 1.8 0 0 1 4.8 5h5l2 2h7.4A1.8 1.8 0 0 1 21 8.8v9.7a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5Z" />,
    play: <path d="m8 5 11 7-11 7V5Z" />,
    chevron: <path d="m7 9 5 5 5-5" />,
    check: <path d="m5 12 4 4L19 6" />,
    loader: <path d="M20 12a8 8 0 1 1-2.34-5.66" />,
    circle: <circle cx="12" cy="12" r="7" />,
    copy: (
      <>
        <rect x="8" y="8" width="11" height="11" rx="2" />
        <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
      </>
    ),
    external: (
      <>
        <path d="M14 5h5v5M19 5l-8 8" />
        <path d="M19 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
      </>
    ),
    trash: (
      <>
        <path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" />
      </>
    ),
    file: (
      <>
        <path d="M6 3h8l4 4v14H6z" />
        <path d="M14 3v5h4" />
      </>
    ),
    link: (
      <>
        <path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.15 1.15" />
        <path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.15-1.15" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06-2.12 2.12-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V20h-3v-.08a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06-2.12-2.12.06-.06A1.65 1.65 0 0 0 7.2 15a1.65 1.65 0 0 0-1.51-1H5.6v-3h.09A1.65 1.65 0 0 0 7.2 10a1.65 1.65 0 0 0-.33-1.82l-.06-.06L8.93 6l.06.06a1.65 1.65 0 0 0 1.82.33 1.65 1.65 0 0 0 1-1.51V4.8h3v.08a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06 2.12 2.12-.06.06A1.65 1.65 0 0 0 19.4 10a1.65 1.65 0 0 0 1.51 1H21v3h-.09a1.65 1.65 0 0 0-1.51 1Z" />
      </>
    ),
    alert: (
      <>
        <path d="M12 3 2.8 20h18.4L12 3Z" />
        <path d="M12 9v4M12 17h.01" />
      </>
    ),
    spark: <path d="m12 3 1.4 5.6L19 10l-5.6 1.4L12 17l-1.4-5.6L5 10l5.6-1.4L12 3ZM19 16l.6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6L19 16Z" />,
  };
  return <svg {...common}>{paths[name]}</svg>;
}

function Button({
  children,
  className = "",
  disabled = false,
  onClick,
  title,
}: {
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
  onClick?: () => void;
  title?: string;
}) {
  return (
    <button className={`button ${className}`} disabled={disabled} onClick={onClick} title={title} type="button">
      {children}
    </button>
  );
}

function TextField({
  value,
  onChange,
  placeholder,
  readOnly = false,
  disabled = false,
  mono = false,
  ariaLabel,
}: {
  value: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  readOnly?: boolean;
  disabled?: boolean;
  mono?: boolean;
  ariaLabel: string;
}) {
  return (
    <input
      aria-label={ariaLabel}
      className={`field ${mono ? "mono" : ""}`}
      disabled={disabled}
      onChange={(event) => onChange?.(event.target.value)}
      placeholder={placeholder}
      readOnly={readOnly}
      value={value}
    />
  );
}

function CardHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="card-header">
      <div>
        <div className="card-title">{title}</div>
        {description && <div className="card-description">{description}</div>}
      </div>
      {action}
    </div>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <button aria-label={label} aria-pressed={checked} className={`toggle ${checked ? "on" : ""}`} onClick={onChange} type="button">
      <span />
    </button>
  );
}

function now() {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

export default function App() {
  const [sourceType, setSourceType] = useState<"file" | "url">("file");
  const [filePath, setFilePath] = useState("/home/user/audio/podcast_episode_001.mp3");
  const [url, setUrl] = useState("");
  const [optionalOpen, setOptionalOpen] = useState(true);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [speakerId, setSpeakerId] = useState("speaker_001");
  const [sourceId, setSourceId] = useState("source_001");
  const [speakerName, setSpeakerName] = useState("");
  const [overwrite, setOverwrite] = useState(false);
  const [evidence, setEvidence] = useState(true);
  const [quality, setQuality] = useState(true);
  const [stages, setStages] = useState(initialStages);
  const [logs, setLogs] = useState(initialLogs);
  const [copied, setCopied] = useState(false);
  const [folderNotice, setFolderNotice] = useState(false);
  const [running, setRunning] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);
  const timers = useRef<number[]>([]);

  const outputPath = `data/speakers/${speakerId || "speaker_001"}/diarization/${sourceId || "source_001"}/final/segments`;
  const idValid = /^speaker_\d{3,6}$/.test(speakerId) && /^source_\d{3,6}$/.test(sourceId);
  const sourceValid =
    sourceType === "file"
      ? /\.(mp3|wav|m4a|flac|ogg)$/i.test(filePath)
      : /^https?:\/\/(www\.)?(youtube\.com|youtu\.be|castbox\.fm)\//i.test(url);
  const canRun = idValid && sourceValid && !running;
  const completedCount = stages.filter((stage) => stage.state === "completed").length;
  const canRunFull = canRun && (completedCount === 0 || overwrite);
  const failedStage = stages.find((stage) => stage.state === "failed");
  const processingStage = stages.find((stage) => stage.state === "processing");
  const diarizeComplete = stages[3].state === "completed";

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setStages((current) => current.map((stage) => (stage.id === 3 ? { ...stage, state: "completed" } : stage)));
      setLogs((current) => [...current, { time: now(), text: "Separate completed successfully.", tone: "success" }]);
      setRunning(false);
    }, 2600);
    timers.current.push(timer);
    return () => timers.current.forEach(window.clearTimeout);
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const addLog = (text: string, tone: LogEntry["tone"] = "neutral") =>
    setLogs((current) => [...current, { time: now(), text, tone }]);

  const simulateStages = (startIndex: number, runAll: boolean) => {
    if (!canRun) return;
    const indexes = runAll ? [0, 1, 2, 3] : [startIndex];
    setRunning(true);
    setFolderNotice(false);
    setStages((current) =>
      current.map((stage, index) => ({
        ...stage,
        state:
          indexes.includes(index) || (!runAll && index > startIndex)
            ? "not-started"
            : stage.state,
      })),
    );
    indexes.forEach((stageIndex, sequence) => {
      const startTimer = window.setTimeout(() => {
        setStages((current) =>
          current.map((stage, index) => (index === stageIndex ? { ...stage, state: "processing" } : stage)),
        );
        addLog(`${initialStages[stageIndex].name} started.`, "processing");
      }, sequence * 1100);
      const completeTimer = window.setTimeout(
        () => {
          setStages((current) =>
            current.map((stage, index) => (index === stageIndex ? { ...stage, state: "completed" } : stage)),
          );
          addLog(`${initialStages[stageIndex].name} completed successfully.`, "success");
          if (sequence === indexes.length - 1) setRunning(false);
        },
        sequence * 1100 + 900,
      );
      timers.current.push(startTimer, completeTimer);
    });
  };

  const chooseSource = (type: "file" | "url") => {
    if (running) return;
    setSourceType(type);
    setStages((current) =>
      current.map((stage) => ({ ...stage, state: "not-started" })),
    );
    addLog(`${type === "file" ? "Local file" : "URL"} input selected.`);
  };

  const browse = () => {
    setFilePath("/home/user/audio/podcast_episode_002.mp3");
    setStages((current) =>
      current.map((stage) => ({ ...stage, state: "not-started" })),
    );
    addLog("Audio file selected: podcast_episode_002.mp3");
  };

  const copyPath = async () => {
    try {
      await navigator.clipboard?.writeText(outputPath);
    } catch {
      // Clipboard APIs can be restricted inside embedded previews.
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-mark"><Icon name="wave" size={27} /></div>
        <div className="brand-copy">
          <div className="brand-name">PodSieve</div>
          <div className="brand-subtitle">Local Audio Processing Workspace</div>
        </div>
        <div className="local-badge"><span /> Local processing</div>
      </header>

      <main className="workspace">
        <section className="column left-column" aria-label="Configuration and controls">
          <div className="card input-card">
            <CardHeader title="Input Source" description="Select a local audio file or provide a supported URL." />
            <div className="source-switch" role="group" aria-label="Input source type">
              <button className={sourceType === "file" ? "active" : ""} onClick={() => chooseSource("file")} type="button">
                <Icon name="file" /> Local file
              </button>
              <button className={sourceType === "url" ? "active" : ""} onClick={() => chooseSource("url")} type="button">
                <Icon name="link" /> URL
              </button>
            </div>
            <div className="input-row">
              <TextField
                ariaLabel={sourceType === "file" ? "Audio file path" : "Audio URL"}
                mono
                onChange={sourceType === "url" ? setUrl : setFilePath}
                placeholder={sourceType === "url" ? "https://www.youtube.com/watch?v=VIDEO_ID" : "Select an audio file"}
                readOnly={sourceType === "file"}
                value={sourceType === "file" ? filePath : url}
              />
              {sourceType === "file" && (
                <Button className="browse-button" disabled={running} onClick={browse}>
                  <Icon name="folder" /> Browse
                </Button>
              )}
            </div>
            <div className={`field-note ${sourceValid ? "" : "error"}`}>
              {sourceType === "file"
                ? "MP3, WAV, M4A, FLAC, or OGG"
                : sourceValid || !url
                  ? "YouTube and Castbox links are supported"
                  : "Enter a valid YouTube or Castbox URL"}
            </div>
          </div>

          <div className={`card settings-card ${optionalOpen ? "open" : ""}`}>
            <button className="collapsible-title" onClick={() => setOptionalOpen(!optionalOpen)} type="button">
              <span className="title-with-icon"><Icon name="settings" /> Optional Settings</span>
              <span className="collapse-copy">{optionalOpen ? "Hide" : "Show"} <Icon name="chevron" /></span>
            </button>
            {optionalOpen && (
              <div className="settings-content">
                <div className="form-grid">
                  <label>
                    <span>Speaker ID</span>
                    <TextField ariaLabel="Speaker ID" mono onChange={setSpeakerId} value={speakerId} />
                    <small className={!/^speaker_\d{3,6}$/.test(speakerId) ? "error-text" : ""}>speaker_ + 3–6 digits</small>
                  </label>
                  <label>
                    <span>Source ID</span>
                    <TextField ariaLabel="Source ID" mono onChange={setSourceId} value={sourceId} />
                    <small className={!/^source_\d{3,6}$/.test(sourceId) ? "error-text" : ""}>source_ + 3–6 digits</small>
                  </label>
                  <label>
                    <span>Language</span>
                    <select aria-label="Language" className="field" defaultValue="fa">
                      <option value="fa">Persian (fa)</option>
                      <option value="en">English (en)</option>
                      <option value="ar">Arabic (ar)</option>
                    </select>
                  </label>
                </div>
                <button className="advanced-trigger" onClick={() => setAdvancedOpen(!advancedOpen)} type="button">
                  <span>Advanced settings</span>
                  <Icon name="chevron" />
                </button>
                {advancedOpen && (
                  <div className="advanced-panel">
                    <div className="compact-fields">
                      <TextField ariaLabel="Speaker name" onChange={setSpeakerName} placeholder="Speaker name" value={speakerName} />
                      <select aria-label="Gender" className="field" defaultValue="">
                        <option value="">Gender — Not set</option>
                        <option>Female</option>
                        <option>Male</option>
                        <option>Non-binary</option>
                      </select>
                      <select aria-label="Expected number of speakers" className="field" defaultValue="auto">
                        <option value="auto">Speakers — Auto</option>
                        <option>1</option>
                        <option>2</option>
                        <option>3</option>
                        <option>4</option>
                      </select>
                    </div>
                    <div className="switch-list">
                      <div><span>Overwrite existing output</span><Toggle checked={overwrite} label="Overwrite existing output" onChange={() => setOverwrite(!overwrite)} /></div>
                      <div><span>Save diarization evidence</span><Toggle checked={evidence} label="Save diarization evidence" onChange={() => setEvidence(!evidence)} /></div>
                      <div><span>Automatic quality analysis</span><Toggle checked={quality} label="Automatic quality analysis" onChange={() => setQuality(!quality)} /></div>
                    </div>
                    <Button className="model-button"><Icon name="settings" /> Advanced model configuration</Button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card controls-card">
            <CardHeader title="Pipeline Controls" description="Run an individual stage or execute the complete pipeline." />
            <div className="stage-actions">
              {initialStages.map((stage, index) => {
                const complete = stages[index].state === "completed";
                const prerequisiteReady = index === 0 || stages[index - 1].state === "completed";
                const stageDisabled = !canRun || !prerequisiteReady || (complete && !overwrite);
                const disabledReason = running
                  ? "A pipeline stage is already running"
                  : !sourceValid || !idValid
                    ? "Select a valid source and IDs first"
                    : !prerequisiteReady
                      ? `Complete ${initialStages[index - 1].name} first`
                      : complete && !overwrite
                        ? "Enable overwrite in Advanced Settings to run this stage again"
                        : `Run ${stage.name}`;
                return (
                  <Button
                    className={`stage-button ${complete ? "complete" : ""}`}
                    disabled={stageDisabled}
                    key={stage.name}
                    onClick={() => simulateStages(index, false)}
                    title={disabledReason}
                  >
                    {complete ? <Icon name="check" /> : <span className="stage-action-number">{index + 1}</span>}
                    {stage.name}
                  </Button>
                );
              })}
            </div>
            <Button
              className="primary-action"
              disabled={!canRunFull}
              onClick={() => simulateStages(0, true)}
              title={
                running
                  ? "Wait for the active stage to finish"
                  : !sourceValid || !idValid
                    ? "Resolve the highlighted input validation first"
                    : completedCount > 0 && !overwrite
                      ? "Enable overwrite in Advanced Settings to rerun completed stages"
                      : "Run all four stages"
              }
            >
              {running ? <Icon name="loader" /> : <Icon name="play" />}
              {running ? `${processingStage?.name ?? "Pipeline"} in progress` : "Run Full Pipeline"}
              <span>Ingest → Convert → Separate → Diarize</span>
            </Button>
            {!canRun && !running && <div className="action-hint"><Icon name="alert" /> Resolve source or ID validation to run the pipeline.</div>}
            {canRun && !canRunFull && <div className="action-hint"><Icon name="alert" /> Enable overwrite in Advanced Settings to rerun the full pipeline.</div>}
          </div>
        </section>

        <section className="column right-column" aria-label="Processing monitor and output">
          <div className="card status-card">
            <CardHeader title="Stage Status" description="Monitor the current status of each processing stage." />
            <div className="stage-list">
              {stages.map((stage) => (
                <div className={`stage-row ${stage.state}`} key={stage.id}>
                  <div className="stage-number">{stage.state === "completed" ? <Icon name="check" /> : stage.id}</div>
                  <div className="stage-copy">
                    <strong>{stage.name}</strong>
                    <span>{stage.description}</span>
                  </div>
                  <div className={`status-badge ${stage.state}`}>
                    {stage.state === "completed" && <Icon name="check" />}
                    {stage.state === "processing" && <Icon name="loader" />}
                    {stage.state === "failed" && <Icon name="alert" />}
                    {stage.state === "not-started" && <Icon name="circle" />}
                    {stage.state === "not-started" ? "Not started" : stage.state[0].toUpperCase() + stage.state.slice(1)}
                  </div>
                  <div className="progress-track">
                    <span className={stage.state === "processing" ? "indeterminate" : ""} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card log-card">
            <CardHeader
              title="Process Log"
              description="Live messages from the local processing service."
              action={
                <Button className="clear-button" onClick={() => setLogs([])}>
                  <Icon name="trash" /> Clear logs
                </Button>
              }
            />
            <div className="log-viewer" ref={logRef}>
              {logs.length ? (
                logs.map((entry, index) => (
                  <div className={`log-line ${entry.tone}`} key={`${entry.time}-${index}`}>
                    <span>[{entry.time}]</span>
                    <p>{entry.text}</p>
                  </div>
                ))
              ) : (
                <div className="empty-log">No process messages yet.</div>
              )}
              {running && <div className="log-cursor" />}
            </div>
          </div>

          <div className={`card output-card ${diarizeComplete ? "available" : ""}`}>
            <CardHeader
              title="Diarized Output Location"
              description={diarizeComplete ? "Output is available and ready to review." : "Expected location after diarization completes."}
              action={<span className={`availability ${diarizeComplete ? "ready" : ""}`}><span /> {diarizeComplete ? "Available" : "Pending"}</span>}
            />
            <div className="output-row">
              <TextField ariaLabel="Diarized output path" mono readOnly value={outputPath} />
              <Button className="icon-action" onClick={copyPath} title="Copy output path">
                {copied ? <Icon name="check" /> : <Icon name="copy" />} <span>{copied ? "Copied" : "Copy path"}</span>
              </Button>
              <Button
                className="icon-action"
                disabled={!diarizeComplete}
                onClick={() => {
                  setFolderNotice(true);
                  addLog(`Opened output folder: ${outputPath}`);
                }}
                title={diarizeComplete ? "Open output folder" : "Folder will be available after diarization"}
              >
                <Icon name="external" /> <span>Open folder</span>
              </Button>
            </div>
            {folderNotice && <div className="toast"><Icon name="folder" /> Output folder opened</div>}
          </div>
        </section>
      </main>

      <footer className={`pipeline-summary ${failedStage ? "failed" : diarizeComplete ? "success" : "processing"}`}>
        <div className="summary-icon">
          {failedStage ? <Icon name="alert" /> : diarizeComplete ? <Icon name="check" /> : <Icon name={running ? "loader" : "spark"} />}
        </div>
        <div className="summary-copy">
          <strong>{failedStage ? "Pipeline Failed" : diarizeComplete ? "Pipeline Completed Successfully" : running ? "Pipeline in Progress" : "Ready for Diarization"}</strong>
          <span>
            {failedStage
              ? `${failedStage.name} failed. Review the process log for details.`
              : diarizeComplete
                ? "All four stages completed. Your diarized audio files are ready."
                : running
                  ? `${completedCount} of 4 stages completed. ${processingStage?.name ?? "Processing"} is currently running.`
                  : `${completedCount} of 4 stages completed. Continue when ready.`}
          </span>
        </div>
        <div className="summary-progress"><span style={{ width: `${(completedCount / 4) * 100}%` }} /></div>
        <div className="summary-count">{completedCount}<span>/4</span></div>
      </footer>
    </div>
  );
}
