# Dependency environment for snippetbox. The platform supplies the repository
# at /app; this image contains dependencies only.
FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
        pip==24.2 \
        setuptools==75.1.0 \
        wheel==0.44.0 \
        pytest==8.3.3 \
        pytest-cov==5.0.0 \
        ruff==0.6.9
