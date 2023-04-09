#!/bin/sh
cd "$(dirname "$0")"

dirbase="$(basename "$(pwd)")"

if [ -n "$M1N1_VERSION_TAG" ]; then
    version="$M1N1_VERSION_TAG"
elif command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
    version="$(git describe --tags --always --dirty)"
elif [ "$(echo "${dirbase}" | cut -c1-5)" = "m1n1-" ]; then
    version=$(echo "${dirbase}" | cut -c6-)
    version="v${version##v}"
else
    version="unknown"
fi

# Check which shell is running
if [ -n "${BASH_VERSION:-}" ]; then
    echo "#define BUILD_TAG \"$version\""
elif [ -n "${ZSH_VERSION:-}" ]; then
    printf '#define BUILD_TAG "%s"\n' "$version"
elif [ -n "${KSH_VERSION:-}" ]; then
    echo "#define BUILD_TAG=\"$version\""
elif [ -n "${POSIXLY_CORRECT:-}" ] || [ "$(basename "$0")" = "sh" ]; then
    echo "#define BUILD_TAG=\"$version\""
else
    echo "Unsupported shell."
    exit 1
fi
