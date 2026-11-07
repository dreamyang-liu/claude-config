#!/bin/sh
# Bootstrap on a new machine: build ccfg and install the common layer into
# ~/.claude. Needs Go (brew install go). After this, use bin/ccfg directly:
#   bin/ccfg install engineering -p <project>
#   bin/ccfg status
set -eu

REPO=$(cd "$(dirname "$0")" && pwd)
cd "$REPO"

if ! command -v go >/dev/null 2>&1; then
    echo "error: go is not installed. Install it first, for example: brew install go" >&2
    exit 1
fi

go build -o bin/ccfg ./cmd/ccfg
echo "built $REPO/bin/ccfg"
bin/ccfg install common --global "$@"
echo
echo "Put ccfg on your PATH, for example:"
echo "  ln -s $REPO/bin/ccfg /usr/local/bin/ccfg"
