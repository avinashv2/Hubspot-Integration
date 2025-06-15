FROM python:3.11-slim

WORKDIR /app

COPY ./backend/ .

RUN apt-get update && \
    apt-get install -y build-essential curl libcurl4-openssl-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
