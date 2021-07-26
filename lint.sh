#!/usr/bin/env sh

flake8 /app/skabenclient --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
autoflake --remove-all-unused-imports --remove-unused-variables --recursive --in-place /app/skabenclient --exclude=__init__.py,tests/
isort --multi-line=3 --trailing-comma --force-grid-wrap=0 --combine-as --line-width 127 /app/skabenclient
