FROM python:3.14-slim
WORKDIR /app
RUN apt-get update && apt-get install --no-install-recommends -y default-mysql-client && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY public ./public
EXPOSE 8081
CMD ["python", "app.py"]
