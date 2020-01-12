#!/usr/bin/env bash

version=$(cat setup.py |grep version |cut -f2 -d "'")
FURY_TOKEN=$(cat ~/dev/.token/gemfury_push)

if [ -d ./venv ]; then
  python3.7 -m venv venv
  . ./venv/bin/activate
  pip install --upgrade pip 
  pip install wheel
fi

. ./venv/bin/activate
python setup.py build sdist bdist_wheel

for entry in $(ls dist | grep $version)
do
    curl -F package=@dist/$entry https://$FURY_TOKEN@push.fury.io/zerthmonk
done
