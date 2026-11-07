package ccfg

import (
	"fmt"
	"os"
	"path/filepath"
)

// ScopeKind tells whether a scope is the global ~/.claude or one project.
type ScopeKind string

const (
	Global  ScopeKind = "global"
	Project ScopeKind = "project"
)

// Scope is one place where Claude Code reads a CLAUDE.md and a skills
// directory. BackupDir receives a file that an install moves aside.
type Scope struct {
	Kind      ScopeKind
	Dir       string
	ClaudeMD  string
	SkillsDir string
	BackupDir string
}

// GlobalScope is ~/.claude, or $CLAUDE_DIR when that is set.
func GlobalScope() (Scope, error) {
	dir := os.Getenv("CLAUDE_DIR")
	if dir == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return Scope{}, err
		}
		dir = filepath.Join(home, ".claude")
	}
	return Scope{
		Kind:      Global,
		Dir:       dir,
		ClaudeMD:  filepath.Join(dir, "CLAUDE.md"),
		SkillsDir: filepath.Join(dir, "skills"),
		BackupDir: filepath.Join(dir, "backups"),
	}, nil
}

// ProjectScope is the project rooted at dir. The directory must exist.
func ProjectScope(dir string) (Scope, error) {
	abs, err := filepath.Abs(dir)
	if err != nil {
		return Scope{}, err
	}
	if !isDir(abs) {
		return Scope{}, fmt.Errorf("project directory %s does not exist", abs)
	}
	return Scope{
		Kind:      Project,
		Dir:       abs,
		ClaudeMD:  filepath.Join(abs, "CLAUDE.md"),
		SkillsDir: filepath.Join(abs, ".claude", "skills"),
		BackupDir: filepath.Join(abs, ".claude", "backups"),
	}, nil
}

// String names the scope for a human: "global (~/.claude)" or "project (<dir>)".
func (s Scope) String() string {
	home, _ := os.UserHomeDir()
	return fmt.Sprintf("%s (%s)", s.Kind, tildify(home, s.Dir))
}

// Rel shortens a path for display. In a project scope, a path inside the
// project becomes relative to it. Any other path gets ~ for the home directory.
func (s Scope) Rel(path string) string {
	if s.Kind == Project {
		if rel, ok := cutPathPrefix(path, s.Dir); ok {
			return rel
		}
	}
	home, _ := os.UserHomeDir()
	return tildify(home, path)
}

// tildify replaces the home directory prefix with ~.
func tildify(home, p string) string {
	if home == "" {
		return p
	}
	if p == home {
		return "~"
	}
	if rel, ok := cutPathPrefix(p, home); ok {
		return "~/" + rel
	}
	return p
}

// untildify expands a leading ~/ to the home directory.
func untildify(home, p string) string {
	if home != "" && len(p) >= 2 && p[:2] == "~/" {
		return filepath.Join(home, p[2:])
	}
	return p
}

func cutPathPrefix(p, prefix string) (string, bool) {
	rel, err := filepath.Rel(prefix, p)
	if err != nil || rel == "." || rel == ".." || len(rel) >= 3 && rel[:3] == ".."+string(filepath.Separator) {
		return "", false
	}
	return rel, true
}
