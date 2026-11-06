#!/bin/sh
# Link the files in this repo into ~/.claude.
# Safe to run again: an existing link is replaced. An existing real file or
# directory is moved to ~/.claude/backups/claude-config-<time>/ first.
# The backup is outside ~/.claude/skills, so a backed-up skill does not load.
set -eu

REPO=$(cd "$(dirname "$0")" && pwd)
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
BACKUP="$CLAUDE_DIR/backups/claude-config-$(date +%Y%m%d-%H%M%S)"

link() {
    src="$REPO/$1"
    dst="$CLAUDE_DIR/$2"
    mkdir -p "$(dirname "$dst")"
    if [ -L "$dst" ]; then
        rm "$dst"
    elif [ -e "$dst" ]; then
        mkdir -p "$BACKUP/$(dirname "$2")"
        mv "$dst" "$BACKUP/$2"
        echo "backup: $dst -> $BACKUP/$2"
    fi
    ln -s "$src" "$dst"
    echo "link:   $dst -> $src"
}

link CLAUDE.md CLAUDE.md
for dir in "$REPO"/skills/*/; do
    name=$(basename "$dir")
    link "skills/$name" "skills/$name"
done
