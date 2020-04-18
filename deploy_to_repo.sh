#!/usr/bin/env bash

cd /app

if [ ! -d ./venv ]; then
  python3.7 -m venv venv
  source ./venv/bin/activate
  pip install --upgrade pip
  pip install wheel
fi

if [ ! -d dist ]; then
  rm -r ./dist ./build ./build_wheel
fi


mkdir dist

. ./venv/bin/activate
python setup.py build sdist bdist_wheel

# pushing to repo
version=$(cat ./setup.py |grep version |cut -f2 -d "'")

for entry in $(ls dist | grep $version)
do
    curl -F package=@dist/$entry https://$TOKEN@push.fury.io/zerthmonk
done
