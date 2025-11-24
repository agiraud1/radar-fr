FROM python:3.11-slim

# 0) Dépendances système minimales
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# 1) Dépendances Python
# -> requirements.txt à la racine (pas dans app/)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 2) Code backend : on copie tout le package app/
COPY app/ ./app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
