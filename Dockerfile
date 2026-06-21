# JCI 専務理事エージェント — Cloud Run 用イメージ（マルチステージ）
# Stage 1: SPA(web) を Vite でビルド
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

# Stage 2: Python ランタイム
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Tokyo

WORKDIR /srv
COPY app/requirements.txt ./app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY app ./app
# SPA ビルド成果物を同梱（管理サービスが /app で配信）
COPY --from=web /web/dist ./web/dist

ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
