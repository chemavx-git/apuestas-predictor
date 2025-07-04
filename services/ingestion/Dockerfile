FROM python:3.11-slim

WORKDIR /app
COPY . .

# Instala dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Expone variables en runtime mediante .env
CMD ["sh", "-c", "source .env && python ingest.py"]
