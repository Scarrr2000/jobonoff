# Используем базовый образ с Python и установленным Poetry
FROM python:3.12-slim-buster AS builder

# Устанавливаем зависимости для Poetry (может потребоваться корректировка)
RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY pyproject.toml poetry.lock ./

# Устанавливаем Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Активируем виртуальное окружение Poetry и устанавливаем зависимости
ENV PATH="/root/.poetry/bin:$PATH"
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi

# Копируем остальной код
COPY . .

# ---
# Создаем финальный образ (более легковесный)
FROM python:3.12-slim-buster
# или FROM python:3.12-slim для допустим того же ubuntu 22

WORKDIR /app

# Копируем установленные зависимости из builder-этапа
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app /app

# Копируем .env файл
COPY .env .env

# Команда для запуска приложения
CMD ["python", "main.py"]