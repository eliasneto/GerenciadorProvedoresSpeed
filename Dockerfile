# Usa uma versão leve do Python
FROM python:3.12-slim

# Impede o Python de criar arquivos .pyc e força os logs a aparecerem no terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Garante que "config" (raiz do projeto) seja importavel mesmo quando um
# script e chamado por caminho relativo (ex.: "python ops/setup_speed.py"),
# caso em que o Python so poe o diretorio do proprio script no sys.path.
ENV PYTHONPATH=/app

# Cria a pasta do sistema dentro do Docker
WORKDIR /app

# MÁGICA SPEED + AD AUTH: Instala as ferramentas do Linux necessárias
RUN apt-get update && apt-get install -y \
    default-mysql-client \
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
CMD ["sh", "-c", "python ops/setup_speed.py && exec gunicorn --bind 0.0.0.0:8000 --timeout 3600 config.wsgi:application"]

