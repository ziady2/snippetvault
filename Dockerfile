# Runtime image for the snippetbox CLI.
FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /src

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir \
        pip==24.2 \
        setuptools==75.1.0 \
        wheel==0.44.0 \
    && pip install --no-cache-dir .

WORKDIR /data
VOLUME ["/data"]

ENTRYPOINT ["snippetbox"]
CMD ["--help"]
