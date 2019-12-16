#!/usr/bin/env bash

source venv/bin/activate
python setup.py build sdist bdist_wheel
version=$(awk -v FPAT="version" "NF{ print $1 }" setup.py | cut -d"'" -f2)

for entry in $(ls dist | grep $version)
do
    curl -F package=@dist/$entry https://$FURY_TOKEN@push.fury.io/zerthmonk
done
