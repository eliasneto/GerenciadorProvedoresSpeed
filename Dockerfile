# Usa uma versão leve do Python
FROM python:3.12-slim

# Impede o Python de criar arquivos .pyc e força os logs a aparecerem no terminal
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Cria a pasta do sistema dentro do Docker
WORKDIR /app

# MÁGICA SPEED + AD AUTH: Instala as ferramentas do Linux necessárias
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala as bibliotecas primeiro (isso deixa o Docker mais rápido)
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copia o resto do seu código
COPY . /app/

# Libera a porta 8000
EXPOSE 8000

# O comando que prepara o sistema E mantém ele no ar profissionalmente!
CMD python setup_speed.py && gunicorn --bind 0.0.0.0:8000 --timeout 1200 config.wsgi:application
