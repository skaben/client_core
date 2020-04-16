#!/usr/bin/env bash

cd /app
mkdir dist

python setup.py build sdist bdist_wheel

# pushing to repo
version=$(cat ./setup.py |grep version |cut -f2 -d "'")

for entry in $(ls dist | grep $version)
do
    curl -F package=@dist/$entry https://$TOKEN@push.fury.io/zerthmonk
done
