# The image holds the program and its migrations, and no setting: every
# setting (README, 設定) is given when the container starts.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/yc-report

COPY pyproject.toml ./
COPY app ./app
# The program looks for migrations/ beside app/ (app/core/migrate.py).
COPY migrations ./migrations

# Installed in place, as on a developer's machine, so there is one copy of the
# program and migrations/ stays beside it.
RUN pip install --no-cache-dir -e . \
    && useradd --system --no-create-home yc

USER yc

EXPOSE 8000

# All interfaces, on the port the platform gives (PORT), 8000 without one.
# serve applies the migrations first and does not start if that fails.
CMD ["sh", "-c", "exec python -m app serve --host 0.0.0.0 --port \"${PORT:-8000}\""]
