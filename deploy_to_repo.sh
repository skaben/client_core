#!/usr/bin/env bash

mkdir dist
python setup.py build sdist

for entry in $(ls dist)
do
    curl -F package=@dist/$entry https://$TOKEN@push.fury.io/zerthmonk
done
