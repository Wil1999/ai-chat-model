FROM python:3.10-slim

# Instalar locales
RUN apt-get update && apt-get install -y locales && \
    echo "es_ES.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen es_ES.UTF-8

# Establecer el locale por defecto
ENV LANG=es_ES.UTF-8 \
    LANGUAGE=es_ES:es \
    LC_ALL=es_ES.UTF-8

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

EXPOSE 5050

CMD ["uvicorn", "webhook:app", "--host", "0.0.0.0", "--port", "5050"]
