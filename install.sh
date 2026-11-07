#!/bin/sh
# Bootstrap on a new machine: build ccfg and run its interactive setup, which
# installs the common layer into ~/.claude, configures one project, and offers
# to put ccfg on your PATH. Needs Go (brew install go).
# Pass arguments to forward them to `ccfg setup`, for example --accessible.
set -eu

REPO=$(cd "$(dirname "$0")" && pwd)
cd "$REPO"

if ! command -v go >/dev/null 2>&1; then
    echo "error: go is not installed. Install it first, for example: brew install go" >&2
    exit 1
fi

go build -o bin/ccfg ./cmd/ccfg
echo "built $REPO/bin/ccfg"
exec bin/ccfg setup "$@"
