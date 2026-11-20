# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements/base.txt requirements/base.txt
RUN pip install -r requirements/base.txt

COPY . .

# Admin panel statik fayllari (build vaqtida maxfiy kalit kerak emas)
RUN DJANGO_SETTINGS_MODULE=config.settings.dev python manage.py collectstatic --noinput

RUN useradd --system --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", \
     "--access-logfile", "-", "--timeout", "60"]
