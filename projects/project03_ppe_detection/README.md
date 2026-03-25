# PPE Detection System — Production v2.0

Real-time Personal Protective Equipment (PPE) detection using **YOLOv8 + FastAPI + React**.

---

## Project Structure

```
project03_ppe_detection/
├── backend/
│   ├── main.py            # FastAPI app (all endpoints)
│   ├── detector.py        # YOLO inference + drawing
│   ├── requirements.txt
│   ├── model/
│   │   └── best.pt        # YOLOv8 weights
│   └── outputs/           # Processed videos (auto-created)
└── frontend/
    ├── src/
    │   ├── App.jsx        # Main React app (Image / Webcam / Video modes)
    │   ├── App.css        # Dark SaaS dashboard theme
    │   └── index.css
    └── package.json
```

---

## Quick Start

### 1. Backend

```bash
cd backend

# Create & activate virtual environment (recommended)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: http://127.0.0.1:8000  
Swagger docs: http://127.0.0.1:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at: http://localhost:5173

---

## API Endpoints

| Method | Path             | Description                        |
|--------|------------------|------------------------------------|
| GET    | /health          | Health check                       |
| POST   | /detect-image    | Annotate an image; returns JPEG    |
| POST   | /status          | PPE status only (Safe/Violation)   |
| GET    | /webcam          | MJPEG stream from webcam           |
| POST   | /detect-video    | Process video; returns MP4         |
| GET    | /video/{name}    | Serve a processed video by name    |

---

## Features

- **Image mode** — Upload & detect PPE in photos; side-by-side original vs result
- **Webcam mode** — Live backend-streamed MJPEG with real-time detection
- **Video mode** — Full frame-by-frame processing with downloadable MP4 output
- Drag-and-drop file upload
- Safe / Violation status badge with animated dot
- Toast notifications for errors and success
- Responsive dark SaaS dashboard UI
- Optional ffmpeg re-encoding for broad browser compatibility

---

## Notes

- Make sure `model/best.pt` exists in the `backend/` directory.
- ffmpeg is **optional** but recommended for best video playback compatibility.  
  Install from https://ffmpeg.org/download.html and ensure it's on your PATH.
- Webcam index `0` is used by default. Change `cv2.VideoCapture(0)` in `main.py` if needed.
