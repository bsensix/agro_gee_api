FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn earthengine-api

COPY agro_gee_api /app/agro_gee_api

EXPOSE 8000

CMD ["uvicorn", "agro_gee_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
