FROM python:3.11-slim

# Déps système minimales
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Dépendances Python (requirements dans app/)
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 2) Code backend (dossier app/ → /app)
COPY app/ ./

# 3) Assets FastAPI (static + templates à la racine du repo)
COPY static/ ./static
COPY templates/ ./templates

ENV PORT=8080
EXPOSE 8080

# 4) Lancement de l'API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
