# ---------- Etapa 1: build del frontend (React + Vite) ----------
FROM node:20.18-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---------- Etapa 2: backend (FastAPI) que también sirve el frontend ----------
FROM python:3.12-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    CC_DIRECTORIO_DATOS=/app/datos CC_DIRECTORIO_FRONTEND=/app/frontend/dist PORT=8000
WORKDIR /app
COPY requirements.txt ./
# libexpat1: dependencia nativa de pyosmium (lectura del extracto PBF de OSM)
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -r requirements.txt
COPY backend/ backend/
COPY algoritmos/ algoritmos/
COPY estructuras/ estructuras/
COPY simulacion/ simulacion/
COPY benchmark/ benchmark/
COPY mapas/ mapas/
COPY tests/ tests/
COPY pyproject.toml ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
# Los grafos/BD viven en un volumen (docker-compose) o disco persistente (Render).
RUN mkdir -p /app/datos/grafos /app/datos/cache /app/datos/base_datos && useradd -m -u 1000 app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/salud', timeout=4)" || exit 1
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
