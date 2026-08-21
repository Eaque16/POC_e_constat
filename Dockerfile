FROM python:3.11.9-slim
WORKDIR /app
COPY pyproject.toml .
COPY econstat ./econstat
RUN pip install --no-cache-dir .
CMD ["uvicorn", "econstat.main:app", "--host", "0.0.0.0", "--port", "8000"]
