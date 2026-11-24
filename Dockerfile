FROM python:3.12-slim-bookworm@sha256:44cf1793efa7c7a476bb0f2cff81443f4a072c90c1cb127e2924933daa3e8c64
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY vendor/ /tmp/wheels/
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels boto3==1.43.118 && rm -rf /tmp/wheels
COPY app/ /app/
USER 65532:65532
ENTRYPOINT ["python", "/app/job.py"]
