FROM python:3.11-slim

WORKDIR /app

# Install system deps (optional, lightweight)
RUN pip install --upgrade pip

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
