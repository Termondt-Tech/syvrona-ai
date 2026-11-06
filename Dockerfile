# syntax=docker/dockerfile:1
# Two images from one file:
#   test     runtime dependencies + pytest; the compose `test` service and CI run it
#   runtime  what gunicorn serves; built by default because it is the last stage
# Both install from hash-pinned locks generated from pyproject.toml (see CLAUDE.md).

FROM python:3.13.17-slim-trixie AS base
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
WORKDIR /app
# tiktoken's BPE file is fetched at build time and verified by tiktoken against its
# pinned hash, so the server never downloads it while answering a request.
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken

FROM base AS test
# The container is thrown away after each run, and /app stays root-owned.
ENV PYTEST_ADDOPTS="-p no:cacheprovider"
COPY requirements-dev.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.txt \
    && python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"
COPY --chown=appuser:appgroup . .
USER appuser
CMD ["pytest"]

FROM base AS runtime
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    && python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"
COPY --chown=appuser:appgroup . .
USER appuser
EXPOSE 5000
CMD ["gunicorn", "-c", "app/gunicorn.conf.py", "app:create_app()"]
