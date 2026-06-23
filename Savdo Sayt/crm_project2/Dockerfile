FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Static files
RUN python manage.py collectstatic --noinput

# Port
EXPOSE 8000

# Start gunicorn
CMD ["gunicorn", "qurilish_crm.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
