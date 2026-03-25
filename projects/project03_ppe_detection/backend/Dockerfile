# ── PPE Detection Backend — HuggingFace Spaces Dockerfile ──────────────────
# Base: slim Python 3.11 (no GPU needed for inference on CPU)
FROM python:3.11-slim

# HuggingFace Spaces runs as user 1000 — required
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /home/user/app

# ── System deps for OpenCV ──────────────────────────────────────────────────
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
USER user

# ── Python dependencies ─────────────────────────────────────────────────────
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── App source ──────────────────────────────────────────────────────────────
COPY --chown=user . .

# Create outputs dir
RUN mkdir -p outputs

# HuggingFace Spaces exposes port 7860
EXPOSE 7860

# ── Start FastAPI ────────────────────────────────────────────────────────────
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
