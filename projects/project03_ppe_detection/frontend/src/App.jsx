import React, { useState, useRef, useEffect, useCallback } from "react";
import "./App.css";

// Reads VITE_API_URL from .env.local (dev) or .env.production (build)
const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// ─── Utility components ───────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      <span>Processing…</span>
    </div>
  );
}

function StatusBadge({ status }) {
  if (!status) return null;
  const isViolation = status === "Violation";
  return (
    <div className={`status-badge ${isViolation ? "danger" : "safe"}`}>
      <span className="badge-dot" />
      {isViolation ? "⚠ PPE Violation Detected" : "✓ All PPE Compliant — Safe"}
    </div>
  );
}

function Toast({ message, type, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 5000);
    return () => clearTimeout(t);
  }, [onClose]);
  return (
    <div className={`toast toast-${type}`}>
      <span>{message}</span>
      <button onClick={onClose} className="toast-close">×</button>
    </div>
  );
}

function NavItem({ icon, label, active, onClick }) {
  return (
    <button className={`nav-item ${active ? "nav-active" : ""}`} onClick={onClick} title={label}>
      <span className="nav-icon">{icon}</span>
      <span className="nav-label">{label}</span>
    </button>
  );
}

// ─── Progress bar ─────────────────────────────────────────────────────────────

function ProgressBar({ progress, total, message }) {
  const pct = total > 0 ? Math.round((progress / total) * 100) : 0;
  return (
    <div className="progress-wrap">
      <div className="progress-top">
        <span className="progress-msg">{message || "Processing…"}</span>
        <span className="progress-pct">{pct}%</span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      {total > 0 && (
        <div className="progress-sub">Frame {progress} / {total}</div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// IMAGE MODE
// ═══════════════════════════════════════════════════════════════════════════════

function ImageMode({ showToast }) {
  const [preview, setPreview] = useState(null);
  const [result,  setResult]  = useState(null);
  const [status,  setStatus]  = useState("");
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef();

  const processFile = useCallback(async (file) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      showToast("Please select a valid image file.", "error");
      return;
    }
    setPreview(URL.createObjectURL(file));
    setResult(null);
    setStatus("");
    setLoading(true);

    const fd = new FormData();
    fd.append("file", file);

    try {
      const res = await fetch(`${API}/detect-image`, { method: "POST", body: fd });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }
      const blob = await res.blob();
      setResult(URL.createObjectURL(blob));
      const headerStatus = res.headers.get("X-PPE-Status");
      if (headerStatus) {
        setStatus(headerStatus);
      } else {
        const fd2 = new FormData();
        fd2.append("file", file);
        const r2 = await fetch(`${API}/status`, { method: "POST", body: fd2 });
        const d2 = await r2.json();
        setStatus(d2.status);
      }
    } catch (e) {
      showToast(e.message || "Detection failed.", "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  }, [processFile]);

  return (
    <div className="mode-panel">
      <div className="panel-header">
        <h2>Image Detection</h2>
        <p>Upload a photo to detect PPE compliance.</p>
      </div>

      <div
        className={`dropzone ${dragging ? "dragover" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className="dz-inner">
          <span className="dz-icon">📁</span>
          <span className="dz-text">Drop image here or <u>click to browse</u></span>
          <span className="dz-hint">JPG, PNG, WEBP — max 20 MB</span>
        </div>
        <input ref={inputRef} type="file" accept="image/*" hidden
          onChange={(e) => processFile(e.target.files[0])} />
      </div>

      {loading && <Spinner />}

      {(preview || result) && !loading && (
        <div className="results-grid">
          {preview && (
            <div className="result-card">
              <span className="result-label">Original</span>
              <img src={preview} alt="original" />
            </div>
          )}
          {result && (
            <div className="result-card">
              <span className="result-label">Detected</span>
              <img src={result} alt="detected" />
              <a href={result} download="ppe_result.jpg" className="btn btn-sm btn-primary">
                ⬇ Download
              </a>
            </div>
          )}
        </div>
      )}

      {status && !loading && <StatusBadge status={status} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// WEBCAM MODE
// ═══════════════════════════════════════════════════════════════════════════════

function WebcamMode() {
  const [active, setActive] = useState(false);
  const [key, setKey] = useState(0);

  const start = () => { setKey(k => k + 1); setActive(true); };
  const stop  = () => setActive(false);

  return (
    <div className="mode-panel">
      <div className="panel-header">
        <h2>Live Webcam</h2>
        <p>Stream your webcam with real-time PPE detection.</p>
      </div>

      <div className="webcam-controls">
        {!active
          ? <button className="btn btn-primary" onClick={start}>▶ Start Stream</button>
          : <button className="btn btn-danger"  onClick={stop}>■ Stop Stream</button>
        }
      </div>

      {active && (
        <div className="stream-wrap">
          <div className="live-badge">● LIVE</div>
          <img key={key} src={`${API}/webcam`} alt="Webcam Stream"
               className="stream-img" onError={() => {}} />
        </div>
      )}

      {!active && (
        <div className="stream-placeholder">
          <span>🎥</span>
          <p>Click "Start Stream" to begin detection</p>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// VIDEO MODE — async job + SSE progress
// ═══════════════════════════════════════════════════════════════════════════════

function VideoMode({ showToast }) {
  const [phase, setPhase]       = useState("idle");
  const [progress, setProgress] = useState({ progress: 0, total: 1, message: "" });
  const [videoUrl, setVideoUrl] = useState(null);
  const [fileName, setFileName] = useState("");
  const inputRef = useRef();
  const videoRef = useRef();
  const esRef    = useRef(null);

  useEffect(() => () => esRef.current?.close(), []);

  useEffect(() => {
    if (videoRef.current && videoUrl) videoRef.current.load();
  }, [videoUrl]);

  const reset = () => {
    esRef.current?.close();
    setPhase("idle");
    setProgress({ progress: 0, total: 1, message: "" });
    setVideoUrl(null);
    setFileName("");
  };

  const startSSE = useCallback((id) => {
    esRef.current?.close();
    const es = new EventSource(`${API}/video-progress/${id}`);
    esRef.current = es;

    es.onmessage = async (e) => {
      let job;
      try { job = JSON.parse(e.data); } catch { return; }

      setProgress({
        progress: job.progress ?? 0,
        total:    job.total    ?? 1,
        message:  job.message  ?? "",
      });

      if (job.status === "done") {
        es.close();
        setPhase("done");
        try {
          const res = await fetch(`${API}/video-result/${id}`);
          if (!res.ok) throw new Error("Failed to fetch result video.");
          const blob = await res.blob();
          if (blob.size < 1000) throw new Error("Result video appears empty.");
          setVideoUrl(URL.createObjectURL(blob));
          showToast("Video processed successfully!", "success");
        } catch (err) {
          setPhase("error");
          showToast(err.message, "error");
        }
      }

      if (job.status === "error") {
        es.close();
        setPhase("error");
        showToast(job.error || "Processing failed.", "error");
      }
    };

    es.onerror = () => {
      es.close();
      setPhase(prev => prev === "processing" ? "error" : prev);
    };
  }, [showToast]);

  const processVideo = useCallback(async (file) => {
    if (!file) return;
    if (!file.type.startsWith("video/")) {
      showToast("Please select a valid video file.", "error");
      return;
    }
    reset();
    setFileName(file.name);
    setPhase("uploading");
    setProgress({ progress: 0, total: 1, message: "Uploading video to server…" });

    const fd = new FormData();
    fd.append("file", file);

    try {
      const res = await fetch(`${API}/detect-video-submit`, { method: "POST", body: fd });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Upload error ${res.status}`);
      }
      const { job_id } = await res.json();
      setPhase("processing");
      setProgress({ progress: 0, total: 1, message: "Starting detection…" });
      startSSE(job_id);
    } catch (e) {
      setPhase("error");
      showToast(e.message || "Upload failed.", "error");
    }
  }, [showToast, startSSE]);

  const isbusy = phase === "uploading" || phase === "processing";

  return (
    <div className="mode-panel">
      <div className="panel-header">
        <h2>Video Detection</h2>
        <p>Upload a video — every frame is analysed for PPE compliance.</p>
      </div>

      <div
        className={`dropzone ${isbusy ? "dz-busy" : ""}`}
        onClick={() => !isbusy && inputRef.current?.click()}
        style={{ cursor: isbusy ? "not-allowed" : "pointer" }}
      >
        <div className="dz-inner">
          <span className="dz-icon">{isbusy ? "⏳" : "🎬"}</span>
          {isbusy
            ? <span className="dz-text">{progress.message || "Processing…"}</span>
            : <>
                <span className="dz-text">Drop video here or <u>click to browse</u></span>
                <span className="dz-hint">MP4, AVI, MOV — max 500 MB</span>
              </>
          }
        </div>
        <input ref={inputRef} type="file" accept="video/*" hidden
          onChange={(e) => processVideo(e.target.files[0])} />
      </div>

      {isbusy && (
        <ProgressBar
          progress={progress.progress}
          total={progress.total}
          message={progress.message}
        />
      )}

      {phase === "error" && (
        <div className="error-box">
          <span>❌ Processing failed.</span>
          <button className="btn btn-secondary btn-sm" onClick={reset}>Try again</button>
        </div>
      )}

      {phase === "done" && videoUrl && (
        <div className="video-result">
          <div className="result-label">{fileName ? `Result: ${fileName}` : "Processed Video"}</div>
          <video ref={videoRef} controls autoPlay muted playsInline className="result-video">
            <source src={videoUrl} type="video/mp4" />
            Your browser does not support HTML5 video.
          </video>
          <div className="video-actions">
            <a href={videoUrl} download="ppe_result.mp4" className="btn btn-primary">
              ⬇ Download Result
            </a>
            <button className="btn btn-secondary" onClick={reset}>✕ Clear</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════════

const MODES = [
  { id: "image",  icon: "📷", label: "Image"  },
  { id: "webcam", icon: "🎥", label: "Webcam" },
  { id: "video",  icon: "🎬", label: "Video"  },
];

export default function App() {
  const [mode,  setMode]  = useState("image");
  const [toast, setToast] = useState(null);

  const showToast = useCallback((message, type = "info") => {
    setToast({ message, type, id: Date.now() });
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span className="logo-icon">🦺</span>
          <div className="logo-text">
            <span className="logo-title">SafetyAI</span>
            <span className="logo-sub">PPE Monitor</span>
          </div>
        </div>
        <nav className="sidebar-nav">
          <span className="nav-section-label">Detection</span>
          {MODES.map(m => (
            <NavItem key={m.id} icon={m.icon} label={m.label}
              active={mode === m.id} onClick={() => setMode(m.id)} />
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="footer-badge">● API Connected</span>
        </div>
      </aside>

      <main className="main-content">
        <header className="top-bar">
          <h1 className="page-title">
            {MODES.find(m => m.id === mode)?.icon}{" "}
            {MODES.find(m => m.id === mode)?.label} Detection
          </h1>
          <span className="api-url">API: {API}</span>
        </header>
        <div className="content-area">
          {mode === "image"  && <ImageMode  showToast={showToast} />}
          {mode === "webcam" && <WebcamMode />}
          {mode === "video"  && <VideoMode  showToast={showToast} />}
        </div>
      </main>

      {toast && (
        <Toast key={toast.id} message={toast.message}
          type={toast.type} onClose={() => setToast(null)} />
      )}
    </div>
  );
}
