FROM python:3.11-slim

# 1) Pré-requis système minimum
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# 2) Dépendances Python
COPY app/requirements.txt ./app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

# 3) Code backend : on copie tout le package app/
COPY app/ ./app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
