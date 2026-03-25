"""
main.py - FastAPI Backend for PPE Detection System
Production-quality: proper error handling, memory management, logging.
Supports SSE progress streaming for long video jobs.
"""

import io
import os
import json
import time
import uuid
import logging
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse

from detector import Detector

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ppe_backend")

# ─── App & CORS ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="PPE Detection API",
    description="Real-time PPE detection using YOLO",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Detector (singleton) ─────────────────────────────────────────────────────
detector = Detector()

# ─── Output directory ─────────────────────────────────────────────────────────
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── Config ───────────────────────────────────────────────────────────────────
MAX_IMAGE_SIZE_MB  = 20
MAX_VIDEO_SIZE_MB  = 500
MAX_FRAME_DIM      = 1080   # Downscale to 1080p max (handles 4K efficiently)
WEBCAM_FPS_TARGET  = 20

# ─── In-memory job store ──────────────────────────────────────────────────────
# job_id -> { status, progress, total, message, output_path, error }
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def decode_image(data: bytes) -> np.ndarray:
    if not data:
        raise HTTPException(status_code=400, detail="Empty file received.")
    npimg = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=422, detail="Cannot decode image. Unsupported format or corrupted file.")
    return img


def encode_jpeg(img: np.ndarray, quality: int = 85) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Failed to encode frame as JPEG.")
    return buf.tobytes()


def _reencode_for_web(src: str, dst: str) -> bool:
    """Re-encode with ffmpeg: H.264 + moov faststart for browser play."""
    cmd = [
        "ffmpeg", "-y",
        "-i", src,
        "-vcodec", "libx264",
        "-crf", "23",
        "-preset", "fast",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        dst,
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=600)
        if result.returncode != 0:
            logger.warning(f"ffmpeg error: {result.stderr.decode(errors='ignore')[:400]}")
            return False
        return True
    except FileNotFoundError:
        logger.warning("ffmpeg not found — serving raw mp4v output.")
        return False
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg timed out.")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND VIDEO PROCESSING WORKER
# ═══════════════════════════════════════════════════════════════════════════════

def _process_video_job(job_id: str, tmp_input: str, output_path: str):
    """
    Runs in a background thread. Updates _jobs[job_id] with live progress.
    """
    def update(status="processing", progress=0, total=1, message=""):
        with _jobs_lock:
            _jobs[job_id].update({
                "status": status,
                "progress": progress,
                "total": total,
                "message": message,
            })

    tmp_raw = output_path.replace(".mp4", "_raw.mp4")

    try:
        cap = cv2.VideoCapture(tmp_input)
        if not cap.isOpened():
            raise RuntimeError("Cannot open video file.")

        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  or 640
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        fps    = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps > 120:
            fps = 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

        logger.info(f"[job {job_id}] {width}x{height} @ {fps:.1f}fps  frames={total_frames}")
        update(message=f"Opened: {width}x{height} @ {fps:.0f}fps — {total_frames} frames",
               total=total_frames)

        # ── Downscale if larger than MAX_FRAME_DIM ────────────────────────────
        if max(width, height) > MAX_FRAME_DIM:
            scale  = MAX_FRAME_DIM / max(width, height)
            width  = int(width  * scale)
            height = int(height * scale)
            do_resize = True
            logger.info(f"[job {job_id}] Downscaling to {width}x{height}")
            update(message=f"Downscaling 4K → {width}x{height} for fast processing…",
                   total=total_frames)
        else:
            do_resize = False

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(tmp_raw, fourcc, fps, (width, height))

        frame_count = 0
        t_start = time.time()

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if do_resize:
                frame = cv2.resize(frame, (width, height))

            annotated, _ = detector.detect(frame)
            writer.write(annotated)
            frame_count += 1

            # Update progress every 5 frames to avoid lock overhead
            if frame_count % 5 == 0 or frame_count == total_frames:
                elapsed = time.time() - t_start
                fps_real = frame_count / elapsed if elapsed > 0 else 0
                eta = int((total_frames - frame_count) / fps_real) if fps_real > 0 else 0
                update(
                    progress=frame_count,
                    total=total_frames,
                    message=f"Processing frame {frame_count}/{total_frames}  |  {fps_real:.1f} fps  |  ETA {eta}s",
                )

        cap.release()
        writer.release()

        logger.info(f"[job {job_id}] Wrote {frame_count} frames → {tmp_raw}")

        if frame_count == 0:
            raise RuntimeError("No frames could be read from the video.")

        # ── Re-encode for browser ─────────────────────────────────────────────
        update(progress=total_frames, total=total_frames,
               message="Re-encoding for browser compatibility…")

        ffmpeg_ok = _reencode_for_web(tmp_raw, output_path)
        if not ffmpeg_ok:
            os.rename(tmp_raw, output_path)
        else:
            try:
                os.unlink(tmp_raw)
            except Exception:
                pass

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError("Output video is empty after encoding.")

        logger.info(f"[job {job_id}] Done — {os.path.getsize(output_path)} bytes")
        with _jobs_lock:
            _jobs[job_id].update({
                "status": "done",
                "progress": total_frames,
                "total": total_frames,
                "message": "Processing complete!",
                "output_path": output_path,
                "filename": Path(output_path).name,
            })

    except Exception as e:
        logger.error(f"[job {job_id}] Error: {e}")
        with _jobs_lock:
            _jobs[job_id].update({"status": "error", "error": str(e)})
    finally:
        try:
            os.unlink(tmp_input)
        except Exception:
            pass
        try:
            if os.path.exists(tmp_raw):
                os.unlink(tmp_raw)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"status": "ok", "service": "PPE Detection API v2.1"}


# ─── Image Detection ──────────────────────────────────────────────────────────

@app.post("/detect-image")
async def detect_image(file: UploadFile = File(...)):
    logger.info(f"detect-image | {file.filename}")
    data = await file.read()
    if len(data) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image exceeds {MAX_IMAGE_SIZE_MB} MB.")
    img = decode_image(data)
    h, w = img.shape[:2]
    if max(h, w) > MAX_FRAME_DIM:
        scale = MAX_FRAME_DIM / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    annotated, status = detector.detect(img)
    logger.info(f"detect-image | status={status}")
    return StreamingResponse(
        io.BytesIO(encode_jpeg(annotated)),
        media_type="image/jpeg",
        headers={"X-PPE-Status": status, "Access-Control-Expose-Headers": "X-PPE-Status"},
    )


@app.post("/status")
async def get_status(file: UploadFile = File(...)):
    data = await file.read()
    img = decode_image(data)
    _, status = detector.detect(img)
    return {"status": status}


# ─── Webcam Stream ────────────────────────────────────────────────────────────

def _webcam_generator():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Cannot open webcam.")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, WEBCAM_FPS_TARGET)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    interval = 1.0 / WEBCAM_FPS_TARGET
    logger.info("Webcam stream started.")
    try:
        while True:
            t0 = time.time()
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            annotated, _ = detector.detect(frame)
            jpeg = encode_jpeg(annotated, quality=80)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            sleep = interval - (time.time() - t0)
            if sleep > 0:
                time.sleep(sleep)
    except GeneratorExit:
        logger.info("Webcam: client disconnected.")
    finally:
        cap.release()
        logger.info("Webcam capture released.")


@app.get("/webcam")
def webcam_feed():
    return StreamingResponse(
        _webcam_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ─── Video: Submit job ────────────────────────────────────────────────────────

@app.post("/detect-video-submit")
async def detect_video_submit(file: UploadFile = File(...)):
    """
    Upload a video, start background processing, return a job_id immediately.
    Poll /video-progress/{job_id} for SSE progress updates.
    Fetch result from /video-result/{job_id} when done.
    """
    logger.info(f"detect-video-submit | {file.filename}")

    data = await file.read()
    if len(data) > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Video exceeds {MAX_VIDEO_SIZE_MB} MB.")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty video file.")

    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_in.write(data)
    tmp_in.close()

    job_id = str(uuid.uuid4())
    output_path = str(OUTPUT_DIR / f"output_{job_id}.mp4")

    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "total": 1,
            "message": "Job queued, starting…",
            "output_path": None,
            "filename": None,
            "error": None,
        }

    t = threading.Thread(
        target=_process_video_job,
        args=(job_id, tmp_in.name, output_path),
        daemon=True,
    )
    t.start()

    return {"job_id": job_id}


# ─── Video: SSE progress stream ───────────────────────────────────────────────

@app.get("/video-progress/{job_id}")
def video_progress(job_id: str):
    """
    Server-Sent Events stream. Sends progress updates every ~800ms until done/error.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    def _event_stream():
        while True:
            with _jobs_lock:
                job = dict(_jobs.get(job_id, {}))

            data = json.dumps(job)
            yield f"data: {data}\n\n"

            if job.get("status") in ("done", "error"):
                break
            time.sleep(0.8)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Video: Download result ───────────────────────────────────────────────────

@app.get("/video-result/{job_id}")
def video_result(job_id: str):
    """Return the finished processed video file."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] == "error":
        raise HTTPException(status_code=500, detail=job.get("error", "Processing failed."))
    if job["status"] != "done":
        raise HTTPException(status_code=202, detail="Processing not yet complete.")

    path = job["output_path"]
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Output file not found.")

    return FileResponse(
        path,
        media_type="video/mp4",
        filename="ppe_result.mp4",
        headers={"Content-Disposition": "inline; filename=ppe_result.mp4"},
    )


# ─── Legacy single-request video endpoint (kept for compatibility) ─────────────

@app.post("/detect-video")
async def detect_video(file: UploadFile = File(...)):
    """
    Synchronous video endpoint — fine for short clips only.
    For long/4K videos use /detect-video-submit + /video-progress/{id}.
    """
    logger.info(f"detect-video (sync) | {file.filename}")
    data = await file.read()
    if len(data) > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Video too large.")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")

    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_in.write(data)
    tmp_in.close()

    output_path = str(OUTPUT_DIR / f"output_{int(time.time() * 1000)}.mp4")
    tmp_raw = output_path.replace(".mp4", "_raw.mp4")

    cap = cv2.VideoCapture(tmp_in.name)
    if not cap.isOpened():
        os.unlink(tmp_in.name)
        raise HTTPException(status_code=422, detail="Cannot open video.")

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  or 640
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    fps    = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps > 120:
        fps = 25.0

    if max(width, height) > MAX_FRAME_DIM:
        scale  = MAX_FRAME_DIM / max(width, height)
        width  = int(width  * scale)
        height = int(height * scale)
        do_resize = True
    else:
        do_resize = False

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(tmp_raw, fourcc, fps, (width, height))
    frame_count = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if do_resize:
                frame = cv2.resize(frame, (width, height))
            annotated, _ = detector.detect(frame)
            writer.write(annotated)
            frame_count += 1
    finally:
        cap.release()
        writer.release()
        os.unlink(tmp_in.name)

    if frame_count == 0:
        raise HTTPException(status_code=422, detail="No frames read.")

    ffmpeg_ok = _reencode_for_web(tmp_raw, output_path)
    if not ffmpeg_ok:
        os.rename(tmp_raw, output_path)
    else:
        try:
            os.unlink(tmp_raw)
        except Exception:
            pass

    return FileResponse(output_path, media_type="video/mp4", filename="ppe_result.mp4")
