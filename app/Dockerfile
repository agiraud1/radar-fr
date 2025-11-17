FROM python:3.11-slim

# Déps système minimales
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# On travaille à la racine du projet dans le conteneur
WORKDIR /code

# 1) Dépendances Python (requirements dans app/)
COPY app/requirements.txt ./app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

# 2) Code backend : on copie tout le package app/ tel quel
COPY app/ ./app

ENV PORT=8080
EXPOSE 8080

# 3) Lancement de l'API FastAPI
# -> module app.main, objet app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
