#!/usr/bin/env bash

version=$(cat setup.py |grep version |cut -f2 -d "'")

. ./venv/bin/activate
python setup.py build sdist bdist_wheel

for entry in $(ls dist | grep $version)
do
    curl -F package=@dist/$entry https://$FURY_TOKEN@push.fury.io/zerthmonk
done
