FROM python:3.9-slim

# Evitar interacción en la instalación
ENV DEBIAN_FRONTEND=noninteractive

# Establecer directorio de trabajo
WORKDIR /app

# Actualizar e instalar librerías necesarias del sistema
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libopenblas-dev \
        liblapack-dev \
        libffi-dev \
        wget \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copiar archivos
COPY requirements.txt .
COPY mode_semantic.py .
COPY recomendacion.csv .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Exponer el puerto de Flask
EXPOSE 5000

# Comando por defecto
CMD ["python", "mode_semantic.py"]
