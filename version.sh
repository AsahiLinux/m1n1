#!/bin/sh
cd "$(dirname "$0")"

dirbase="$(basename "$(pwd)")"

if [ -n "$M1N1_VERSION_TAG" ]; then
    version="$M1N1_VERSION_TAG"
elif [ -e ".git" ]; then
    version="$(git describe --tags --always --dirty)"
elif [ "$(echo "${dirbase}" | cut -c1-5)" = "m1n1-" ]; then
    version=$(echo "${dirbase}" | cut -c6-)
    version="v${version##v}"
else
    version="unknown"
fi

echo "#define BUILD_TAG \"$version\""
