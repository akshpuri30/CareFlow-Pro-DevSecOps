FROM python:3.12-alpine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup -g 10001 -S careflow && adduser -u 10001 -S -D -H -G careflow careflow
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py manage.py ./
COPY templates ./templates
COPY static ./static
RUN mkdir -p /app/instance && chown -R careflow:careflow /app
USER careflow
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)" || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app:app"]
