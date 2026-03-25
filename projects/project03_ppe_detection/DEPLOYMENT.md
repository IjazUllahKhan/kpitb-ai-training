# 🚀 Free Deployment Guide — PPE Detection System

## Architecture

```
[React Frontend]  →  Vercel (free)         → yourapp.vercel.app
[FastAPI Backend] →  HuggingFace Spaces    → yourname-ppe-api.hf.space
```

Both are 100% free. No credit card needed.

---

## PART 1 — Deploy Backend to HuggingFace Spaces

### Prerequisites

- Create a free account at https://huggingface.co
- Install git: https://git-scm.com/downloads
- Install git-lfs (for the model file): https://git-lfs.github.com

### Step 1 — Install git-lfs

```bash
git lfs install
```

### Step 2 — Create a new Space on HuggingFace

1. Go to https://huggingface.co/new-space
2. Fill in:
   - Space name: `ppe-detection-api`
   - License: MIT
   - SDK: **Docker** ← IMPORTANT, select Docker
   - Hardware: CPU basic ← free tier
3. Click "Create Space"

### Step 3 — Clone your new Space locally

```bash
# Replace YOUR_USERNAME with your HuggingFace username
git clone https://huggingface.co/spaces/YOUR_USERNAME/ppe-detection-api
cd ppe-detection-api
```

### Step 4 — Copy backend files into the cloned folder

Copy ALL files from your `backend/` folder into the cloned space folder:

```
ppe-detection-api/
├── main.py
├── detector.py
├── requirements.txt
├── Dockerfile
├── README.md          ← the one with the HF metadata header
└── model/
    └── best.pt
```

### Step 5 — Track the model file with git-lfs

```bash
cd ppe-detection-api
git lfs track "*.pt"
git add .gitattributes
```

### Step 6 — Push to HuggingFace

```bash
git add .
git commit -m "Initial deployment"
git push
```

### Step 7 — Wait for build

- Go to your Space page: https://huggingface.co/spaces/YOUR_USERNAME/ppe-detection-api
- Click the "Logs" tab — watch Docker build (takes ~3-5 minutes first time)
- Status becomes green "Running" when ready

### Step 8 — Get your backend URL

Your API is now live at:

```

https://YOUR_USERNAME-ppe-detection-api.hf.space
```

Test it:

```
https://YOUR_USERNAME-ppe-detection-api.hf.space/health
```

Should return: {"status":"ok","service":"PPE Detection API v2.1"}

---

## PART 2 — Deploy Frontend to Vercel

### Prerequisites

- Create free account at https://vercel.com (sign in with GitHub)
- Push your frontend to a GitHub repo

### Step 1 — Push frontend to GitHub

```bash
cd frontend

# If you don't have a git repo yet:
git init
git add .
git commit -m "Initial frontend"

# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/ppe-detection-frontend.git
git push -u origin main
```

### Step 2 — Set your backend URL in .env.production

Edit `frontend/.env.production`:

```
VITE_API_URL=https://YOUR_USERNAME-ppe-detection-api.hf.space
```

Commit and push this change.

### Step 3 — Import to Vercel

1. Go to https://vercel.com/new
2. Click "Import Git Repository"
3. Select your `ppe-detection-frontend` repo
4. Configure:
   - Framework Preset: **Vite**
   - Root Directory: `.` (or `frontend/` if you pushed the whole monorepo)
   - Build Command: `npm run build`
   - Output Directory: `dist`
5. Add Environment Variable:
   - Name: `VITE_API_URL`
   - Value: `https://YOUR_USERNAME-ppe-detection-api.hf.space`
6. Click **Deploy**

### Step 4 — Done!

Your frontend is live at:

```
https://ppe-detection-frontend.vercel.app
```

---

## PART 3 — Important Notes

### ⚠️ Webcam limitation in production

- The `/webcam` endpoint streams from the SERVER's webcam, not the user's browser webcam.
- On HuggingFace Spaces (a cloud server), there is NO physical webcam.
- **Solution**: The webcam feature only works when running locally.
- For production, consider disabling the webcam tab or replacing it with browser-side webcam capture.

### ⚠️ HuggingFace free tier limits

- CPU only (no GPU) — inference is slower (~2-5 sec per image)
- 16 GB RAM, 2 CPU cores
- Space goes to "sleep" after 30 min of inactivity (cold start ~30 sec)
- No persistent storage — processed videos are lost on restart

### ⚠️ File upload size on HF Spaces

- Default request size limit may be low. If you hit issues, files >50MB may fail.
- For large videos, this platform is better used locally.

### 💡 To keep Space always awake (prevent cold starts)

Use a free uptime monitor like https://uptimerobot.com to ping your /health endpoint every 25 minutes.

---

## PART 4 — Alternative Free Platforms

| Platform     | Backend  | Notes                                       |
| ------------ | -------- | ------------------------------------------- |
| HuggingFace  | ✅ Best  | Made for ML, Docker support, free CPU       |
| Render.com   | ✅ Good  | 512MB RAM free, sleeps after 15min          |
| Railway.app  | ✅ Good  | $5 free credit/month, then paid             |
| Fly.io       | ✅ Good  | 256MB free, good uptime                     |
| Google Colab | ⚠️ Hacky | Not for production, manual tunnel via ngrok |

| Platform     | Frontend | Notes                                    |
| ------------ | -------- | ---------------------------------------- |
| Vercel       | ✅ Best  | Instant deploys, free custom domain      |
| Netlify      | ✅ Good  | Also great, drag-and-drop deploy         |
| GitHub Pages | ✅ OK    | Static only, needs `vite build` manually |

---

## Quick Summary (TL;DR)

```
1. huggingface.co → New Space → Docker → name: ppe-detection-api
2. git clone the space, copy backend files in, git push
3. Edit frontend/.env.production with your HF space URL
4. Push frontend to GitHub
5. vercel.com → Import GitHub repo → set VITE_API_URL env var → Deploy
6. Done ✅
```
