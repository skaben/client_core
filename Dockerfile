FROM python:3.7-slim as base
MAINTAINER zerthmonk

ENV PYTHONUBUFFERED=1
ENV PATH="/venv/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends libglib2.0-0 iproute2 curl gcc \
    portaudio19-dev python3-pyaudio

FROM base as builder

WORKDIR /app

COPY build_requirements.txt /build_requirements.txt

RUN python -m pip install --upgrade pip && \
    python -m pip install -r /build_requirements.txt

COPY lint.sh /lint.sh
RUN chmod +x /lint.sh
