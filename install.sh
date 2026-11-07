#!/bin/sh
# Install ccfg from the latest GitHub release, clone the claude-config
# repository when it is missing, and start `ccfg setup`.
#
#   curl -fsSL https://raw.githubusercontent.com/dreamyang-liu/claude-config/main/install.sh | sh
#
# Environment variables:
#   CLAUDE_CONFIG_REPO  where the repository is, or goes (default: ~/Projects/claude-config)
#   CCFG_BIN_DIR        where the binary goes (default: the first writable directory on PATH
#                       among /opt/homebrew/bin, /usr/local/bin, ~/.local/bin, ~/bin)
#   CCFG_VERSION        release tag to install (default: the latest release)
#   CCFG_NO_SETUP=1     install only; do not start `ccfg setup`
#
# Building from source instead: `make build` in the repository (needs Go).
set -eu

OWNER_REPO=dreamyang-liu/claude-config
REPO_DIR=${CLAUDE_CONFIG_REPO:-$HOME/Projects/claude-config}

say() { printf '%s\n' "$*" >&2; }
die() { say "error: $*"; exit 1; }

need() {
    command -v "$1" >/dev/null 2>&1 || die "$1 is required"
}
need curl
need tar
need git

os=$(uname -s | tr '[:upper:]' '[:lower:]')
case $os in
    darwin|linux) ;;
    *) die "unsupported OS: $os (release binaries exist for darwin and linux)" ;;
esac
case $(uname -m) in
    x86_64|amd64) arch=amd64 ;;
    arm64|aarch64) arch=arm64 ;;
    *) die "unsupported architecture: $(uname -m)" ;;
esac

# The latest release redirects to /releases/tag/<version>.
version=${CCFG_VERSION:-}
if [ -z "$version" ]; then
    url=$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/$OWNER_REPO/releases/latest") \
        || die "cannot reach GitHub to find the latest release"
    version=${url##*/}
    case $version in
        v*) ;;
        *) die "no release found at https://github.com/$OWNER_REPO/releases" ;;
    esac
fi

pick_bin_dir() {
    for d in /opt/homebrew/bin /usr/local/bin "$HOME/.local/bin" "$HOME/bin"; do
        case ":$PATH:" in
            *":$d:"*) [ -d "$d" ] && [ -w "$d" ] && { echo "$d"; return; } ;;
        esac
    done
    mkdir -p "$HOME/.local/bin"
    echo "$HOME/.local/bin"
}
BIN_DIR=${CCFG_BIN_DIR:-$(pick_bin_dir)}
mkdir -p "$BIN_DIR"

asset="ccfg_${version}_${os}_${arch}.tar.gz"
base="https://github.com/$OWNER_REPO/releases/download/$version"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

say "downloading ccfg $version for $os/$arch"
curl -fsSL -o "$tmp/$asset" "$base/$asset" || die "download failed: $base/$asset"
curl -fsSL -o "$tmp/checksums.txt" "$base/checksums.txt" || die "download failed: $base/checksums.txt"

expected=$(grep " ./$asset\$" "$tmp/checksums.txt" | cut -d' ' -f1)
[ -n "$expected" ] || die "no checksum for $asset in checksums.txt"
if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$tmp/$asset" | cut -d' ' -f1)
else
    actual=$(shasum -a 256 "$tmp/$asset" | cut -d' ' -f1)
fi
[ "$expected" = "$actual" ] || die "checksum mismatch for $asset"

tar -C "$tmp" -xzf "$tmp/$asset" ccfg
install -m 755 "$tmp/ccfg" "$BIN_DIR/ccfg"
say "installed $BIN_DIR/ccfg"

if [ ! -d "$REPO_DIR/.git" ]; then
    say "cloning https://github.com/$OWNER_REPO into $REPO_DIR"
    git clone -q "https://github.com/$OWNER_REPO" "$REPO_DIR"
else
    say "repository already at $REPO_DIR"
fi

# Remember a non-default repository location for ccfg.
if [ "$REPO_DIR" != "$HOME/Projects/claude-config" ]; then
    conf=${XDG_CONFIG_HOME:-$HOME/.config}/ccfg
    mkdir -p "$conf"
    printf '%s\n' "$REPO_DIR" > "$conf/repo"
    say "recorded the repository path in $conf/repo"
fi

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) say "note: $BIN_DIR is not on your PATH. Add it, for example:"
       say "  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

if [ -n "${CCFG_NO_SETUP:-}" ]; then
    say "done. Next: ccfg setup"
    exit 0
fi
if [ -t 1 ] && [ -r /dev/tty ]; then
    say ""
    exec "$BIN_DIR/ccfg" setup --repo "$REPO_DIR" </dev/tty
fi
say "done. Next: ccfg setup"
