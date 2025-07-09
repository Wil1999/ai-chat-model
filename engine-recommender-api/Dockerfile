FROM python:3.9-slim

# Configuración básica
ENV DEBIAN_FRONTEND=noninteractive
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_21_11

WORKDIR /app

# 1. Instalar dependencias del sistema (esto cambia poco, se cachea)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libaio1 wget unzip gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/oracle && \
    cd /opt/oracle && \
    wget https://download.oracle.com/otn_software/linux/instantclient/2111000/instantclient-basiclite-linux.x64-21.11.0.0.0dbru.zip && \
    unzip instantclient-basiclite-linux.x64-21.11.0.0.0dbru.zip && \
    rm instantclient-basiclite-linux.x64-21.11.0.0.0dbru.zip && \
    echo "/opt/oracle/instantclient_21_11" > /etc/ld.so.conf.d/oracle-instantclient.conf && \
    ldconfig

# 2. Copiar solo requirements.txt para aprovechar la cache
COPY requirements.txt .

# 3. Instalar las dependencias Python (esto se cachea si requirements.txt no cambia)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Copiar el resto del código (cambia más seguido)
COPY . .

EXPOSE 5000

CMD ["python", "mode_semantic.py"]