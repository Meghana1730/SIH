# Backend API image (FastAPI). Used by Render (render.yaml); see docs/08-deployment.md.
# Build from the REPOSITORY ROOT, because the app also needs config/ and data/:
#   docker build -f backend/Dockerfile -t innovprocure-api .
# Run (the database URL and JWT secret come from the environment, never from the image):
#   docker run -p 8000:8000 -e DATABASE_URL=... -e JWT_SECRET=... innovprocure-api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    EMBEDDINGS_ENABLED=false

# Same layout as the repository: the app finds config/ and data/ from its own location
# (backend/app/core/settings.py REPO_ROOT), so /srv plays the role of the repository root.
WORKDIR /srv/backend

# Dependencies first, so code changes do not reinstall them. No PyTorch: semantic matching
# (requirements-embeddings.lock.txt) is optional and too big for a free 512 MB instance.
COPY backend/requirements.lock.txt ./
RUN pip install -r requirements.lock.txt

COPY config /srv/config
COPY data /srv/data
COPY backend /srv/backend

RUN useradd --create-home --uid 10001 app && chown -R app:app /srv
USER app

EXPOSE 8000

# On every start: apply new database migrations, then serve. Render sets $PORT.
# --proxy-headers: take the client IP from X-Forwarded-For (set by Render's proxy), so login
# rate limiting counts real visitors instead of the proxy.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
