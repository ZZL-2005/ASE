FROM docker.1ms.run/library/python:3.11-slim

WORKDIR /app

# Build deps for tiktoken + install useful tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir readability-lxml requests lxml

COPY agent/ ./agent/
COPY orchestrator/ ./orchestrator/
COPY scripts/ ./scripts/
COPY config.py .

# Create workspace directory
RUN mkdir -p /app/workspace /app/trajectories

ENV PYTHONPATH=/app
ENV AGENT_WORKSPACE=/app/workspace

CMD ["python", "scripts/run_nanobot_agent.py"]
