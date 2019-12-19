#!/usr/bin/env bash

app=/skabenclient

. /venv/bin/activate
flake8 $app
pytest -vs $app
