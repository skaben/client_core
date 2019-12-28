FROM python:3.7-buster
MAINTAINER zerthmonk

ENV PYTHONUBUFFERED=1
ENV PATH="/venv/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    sqlite3

COPY ./testing/requirements.txt /requirements.txt
COPY ./requirements.txt /temp_requirements.txt
RUN cat /temp_requirements.txt >> /requirements.txt
RUN rm /temp_requirements.txt

ENV VENV="/venv"
RUN python -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

RUN python -m pip install --upgrade pip && \
    python -m pip install -r /requirements.txt
