FROM python:3.11-slim

# Instalar librerías del sistema necesarias para OpenCV/ultralytics
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "-m", "gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--timeout", "120"]
