FROM python:3.7-slim
MAINTAINER zerthmonk

ENV PYTHONUBUFFERED=1
ENV PATH="/venv/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends libglib2.0-0 iproute2 curl gcc \
    portaudio19-dev python3-pyaudio

COPY build_requirements.txt /build_requirements.txt

ENV VENV="/venv"
RUN python -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

RUN python -m pip install --upgrade pip && \
    python -m pip install -r /build_requirements.txt

RUN mkdir /app
COPY deploy_to_repo.sh /app/deploy_to_repo.sh
WORKDIR /app

