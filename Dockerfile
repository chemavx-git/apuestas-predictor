# Imagen base
FROM python:3.10-slim

# Crea directorio de trabajo
WORKDIR /app

# Copia código y ficheros de dependencias
COPY . .

# Instala dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Ajusta este CMD al comando que arranca tu app principal
CMD ["python", "main.py"]
