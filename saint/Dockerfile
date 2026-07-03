# Steady-state runtime only — this image runs main.py, never authorize.py.
# OAuth's interactive browser-consent flow cannot run in a headless container;
# authorize.py is always run locally, once per account, before this image starts.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
