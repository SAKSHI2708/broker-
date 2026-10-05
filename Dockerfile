FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv

RUN uv sync --frozen

COPY up ./up
COPY deploy_update_a2a.py ./

CMD ["uv", "run", "python", "deploy_update_a2a.py"]