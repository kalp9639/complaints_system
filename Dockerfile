FROM python:3.11-slim

# Install zbar library
RUN apt-get update && apt-get install -y libzbar0

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Run migrations and start the server
CMD python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    gunicorn complaints_system.wsgi --bind 0.0.0.0:$PORT