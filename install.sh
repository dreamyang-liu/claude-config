#!/bin/sh
# Link this repo into Claude Code.
#
#   install.sh                       Link the common layer into ~/.claude:
#                                    CLAUDE.md and every directory in skills/.
#   install.sh <profile> <project>   Link profiles/<profile> into a project:
#                                    each skill into <project>/.claude/skills/,
#                                    and an @import line into <project>/CLAUDE.md.
#
# Safe to run again: an existing link is replaced. An existing real file or
# directory is moved to ~/.claude/backups/claude-config-<time>/ first.
# The backup is outside ~/.claude/skills, so a backed-up skill does not load.
set -eu

REPO=$(cd "$(dirname "$0")" && pwd)
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
BACKUP="$CLAUDE_DIR/backups/claude-config-$(date +%Y%m%d-%H%M%S)"

usage() {
    sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
    echo
    echo "profiles: $(ls "$REPO/profiles" | tr '\n' ' ')"
}

# link <source path> <link path>
link() {
    src=${1%/}
    dst=$2
    mkdir -p "$(dirname "$dst")"
    if [ -L "$dst" ]; then
        rm "$dst"
    elif [ -e "$dst" ]; then
        rel=${dst#"$CLAUDE_DIR"/}
        rel=${rel#/}
        mkdir -p "$BACKUP/$(dirname "$rel")"
        mv "$dst" "$BACKUP/$rel"
        echo "backup: $dst -> $BACKUP/$rel"
    fi
    ln -s "$src" "$dst"
    echo "link:   $dst -> $src"
}

# prune <dir>: remove each link in <dir> that points into this repo and
# whose target no longer exists, for example after a skill moved to a profile.
prune() {
    [ -d "$1" ] || return 0
    for lnk in "$1"/*; do
        [ -L "$lnk" ] || continue
        case $(readlink "$lnk") in
            "$REPO"/*) [ -e "$lnk" ] || { rm "$lnk"; echo "prune:  $lnk"; } ;;
        esac
    done
}

# home_relative <path>: print the path with $HOME replaced by ~ when possible.
home_relative() {
    case $1 in
        "$HOME"/*) echo "~${1#"$HOME"}" ;;
        *) echo "$1" ;;
    esac
}

install_common() {
    prune "$CLAUDE_DIR/skills"
    link "$REPO/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
    for dir in "$REPO"/skills/*/; do
        [ -d "$dir" ] || continue
        link "$dir" "$CLAUDE_DIR/skills/$(basename "$dir")"
    done
}

install_profile() {
    profile=$1
    project=$2
    pdir="$REPO/profiles/$profile"
    if [ ! -d "$pdir" ]; then
        echo "error: no profile '$profile' in $REPO/profiles" >&2
        echo "profiles: $(ls "$REPO/profiles" | tr '\n' ' ')" >&2
        exit 1
    fi
    if [ ! -d "$project" ]; then
        echo "error: no directory '$project'" >&2
        exit 1
    fi
    project=$(cd "$project" && pwd)

    prune "$project/.claude/skills"
    for dir in "$pdir"/skills/*/; do
        [ -d "$dir" ] || continue
        link "$dir" "$project/.claude/skills/$(basename "$dir")"
    done

    import="@$(home_relative "$pdir/CLAUDE.md")"
    md="$project/CLAUDE.md"
    if [ -f "$md" ] && grep -qxF "$import" "$md"; then
        echo "exists: $import in $md"
    else
        if [ -f "$md" ] && [ -n "$(tail -c1 "$md")" ]; then
            printf '\n' >> "$md"
        fi
        printf '%s\n' "$import" >> "$md"
        echo "import: $import -> $md"
    fi

    if [ -d "$project/.git" ] && ! grep -qsE '^/?\.claude(/skills)?/?$' "$project/.gitignore"; then
        echo "note:   add '.claude/skills/' to $project/.gitignore;"
        echo "        the links hold paths that only exist on this machine."
    fi
}

case $# in
    0) install_common ;;
    2) install_profile "$1" "$2" ;;
    *) usage >&2; exit 2 ;;
esac
