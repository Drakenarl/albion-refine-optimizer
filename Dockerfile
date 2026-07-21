# Backend FastAPI pour l'optimiseur Albion.
# Image mince Python 3.12, installe le package avec l'extra [api] pour
# embarquer fastapi + uvicorn. Lancement via le script console
# ``albion-refine-api`` qui respecte l'env $PORT (Railway/Render).

FROM python:3.12-slim

WORKDIR /app

# Installe les deps systeme utiles a diskcache (sqlite est deja embarque).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copie d'abord les manifestes seulement, pour maximiser le cache Docker :
# tant que pyproject.toml ne change pas, la couche pip install est reutilisee.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir '.[api]'

# Variables d'env par defaut : le port est ecrase par la plateforme.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

# Healthcheck local Docker (Railway et Render ont leurs propres probes qui
# frappent /api/health, mais avoir un HEALTHCHECK aide en debug local).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

CMD ["albion-refine-api"]
