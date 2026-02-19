# Containerfile — PABADA backend (FastAPI + CrewAI)
# Build:  podman build -t pabada:latest -f Containerfile .
#         docker build -t pabada:latest -f Containerfile .

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for the backend process
RUN groupadd -g 1000 pabada && \
    useradd -u 1000 -g pabada -m pabada

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Workspace volume for agent data
VOLUME /research

EXPOSE 8000

USER pabada

CMD ["python", "-m", "backend.api.run"]
