FROM python:3.11

WORKDIR /app


RUN apt-get update && \
    apt-get install -y tzdata build-essential python3-dev && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
ENV TZ=UTC

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8081

CMD ["python", "manage.py", "runserver", "0.0.0.0:8081"]