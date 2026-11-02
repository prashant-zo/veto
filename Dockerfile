FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /bin/uv
ENV UV_PYTHON_DOWNLOADS=0 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable
ENV PATH="/app/.venv/bin:$PATH"
USER 65532
EXPOSE 8080
CMD ["uvicorn", "veto.serve.app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
