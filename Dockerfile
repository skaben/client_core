FROM python:3.7-buster
MAINTAINER zerthmonk

ENV PYTHONUBUFFERED=1
ENV PATH="/venv/bin:$PATH"

COPY ./testing/requirements.txt /requirements.txt
COPY ./skabenclient /skabenclient
WORKDIR /skabenclient

ENV VENV="/venv"
RUN python -m venv $VENV
ENV PATH="$VENV/bin:$PATH"

RUN python -m pip install --upgrade pip && \
    python -m pip install -r /requirements.txt

COPY ./testing/start.sh start.sh
RUN chmod +x start.sh

ENTRYPOINT ["/skabenclient/start.sh"]
