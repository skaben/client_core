#!/usr/bin/env bash

cd /app

if [ ! -d dist ]; then
  rm -r ./dist ./build ./build_wheel
fi

mkdir dist

python setup.py build sdist

# pushing to repo
version=$(cat ./setup.py |grep version |cut -f2 -d "'")

for entry in $(ls dist | grep $version)
do
    curl -F package=@dist/$entry https://$TOKEN@push.fury.io/zerthmonk
done
