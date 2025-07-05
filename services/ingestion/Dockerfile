FROM python:3.11-slim

WORKDIR /app
COPY . .

# Instala dependencias
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "ingest.py"]
