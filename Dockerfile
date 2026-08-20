# ShieldAI API — one container for demos / grading (includes spaCy en_core_web_lg).
FROM node:20-alpine AS dashboard-build
WORKDIR /dashboard
COPY app/dashboard/package*.json ./
RUN npm ci
COPY app/dashboard ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md SETUP.md FOR_INSTRUCTORS.md INTEGRATION.md ./
COPY app ./app
COPY tests ./tests
COPY --from=dashboard-build /dashboard/dist ./app/dashboard/dist

RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -e ".[dev]" \
    && python -m spacy download en_core_web_lg

EXPOSE 8888

CMD ["python", "-m", "uvicorn", "app.proxy.main:app", "--host", "0.0.0.0", "--port", "8888"]
