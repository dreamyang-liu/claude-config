package ccfg

import (
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// Link is one symlink in a scope's skills directory that points into the
// repository. Target is the resolved real path, or the raw link target when
// the link is broken.
type Link struct {
	Name   string
	Path   string
	Target string
	Broken bool
}

// scanLinks lists the symlinks of the scope that point into the repository.
// A directory or a regular file in the skills directory is not reported.
func (r *Repo) scanLinks(s Scope) ([]Link, error) {
	entries, err := os.ReadDir(s.SkillsDir)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var out []Link
	for _, e := range entries {
		if e.Type()&os.ModeSymlink == 0 {
			continue
		}
		path := filepath.Join(s.SkillsDir, e.Name())
		raw, err := os.Readlink(path)
		if err != nil {
			continue
		}
		if !filepath.IsAbs(raw) {
			raw = filepath.Join(s.SkillsDir, raw)
		}
		real, err := filepath.EvalSymlinks(path)
		if err != nil {
			if r.Inside(filepath.Clean(raw)) {
				out = append(out, Link{Name: e.Name(), Path: path, Target: filepath.Clean(raw), Broken: true})
			}
			continue
		}
		if r.Inside(real) {
			out = append(out, Link{Name: e.Name(), Path: path, Target: real})
		}
	}
	return out, nil
}

// linkSkill creates <SkillsDir>/<name> -> skill.Path. An existing link to the
// same target is kept. An existing link to another target is replaced. A real
// file or directory is moved to the backup directory with opt.Force, left in
// place and skipped with opt.Keep, and an error otherwise.
func linkSkill(s Scope, sk *Skill, opt Options) (Event, error) {
	dst := filepath.Join(s.SkillsDir, sk.Name)
	if err := os.MkdirAll(s.SkillsDir, 0o755); err != nil {
		return Event{}, err
	}
	if fi, err := os.Lstat(dst); err == nil {
		if fi.Mode()&os.ModeSymlink != 0 {
			if cur, err := filepath.EvalSymlinks(dst); err == nil && cur == sk.Path {
				return Event{Level: Info, Verb: "kept", Subject: sk.Name, Detail: s.Rel(dst)}, nil
			}
			if err := os.Remove(dst); err != nil {
				return Event{}, err
			}
		} else {
			switch {
			case opt.Force:
				if _, err := moveToBackup(s, dst); err != nil {
					return Event{}, err
				}
			case opt.Keep:
				return Event{Level: Warn, Verb: "skipped", Subject: sk.Name, Detail: s.Rel(dst) + " is a real directory, not a link; --force replaces it"}, nil
			default:
				return Event{}, fmt.Errorf("%s exists and is not a symlink; use --force to move it to %s, or --keep to skip it", dst, s.BackupDir)
			}
		}
	}
	if err := os.Symlink(sk.Path, dst); err != nil {
		return Event{}, err
	}
	home, _ := os.UserHomeDir()
	return Event{Level: OK, Verb: "linked", Subject: sk.Name, Detail: s.Rel(dst) + " -> " + tildify(home, sk.Path)}, nil
}

// unlinkSkill removes <SkillsDir>/<name> when it is a symlink into the
// repository. Anything else is left in place and reported.
func unlinkSkill(r *Repo, s Scope, name string) (Event, error) {
	dst := filepath.Join(s.SkillsDir, name)
	fi, err := os.Lstat(dst)
	if os.IsNotExist(err) {
		return Event{Level: Info, Verb: "absent", Subject: name, Detail: s.Rel(dst)}, nil
	}
	if err != nil {
		return Event{}, err
	}
	if fi.Mode()&os.ModeSymlink == 0 {
		return Event{Level: Warn, Verb: "skipped", Subject: name, Detail: s.Rel(dst) + " is not a symlink"}, nil
	}
	real, err := filepath.EvalSymlinks(dst)
	if err == nil && !r.Inside(real) {
		return Event{Level: Warn, Verb: "skipped", Subject: name, Detail: s.Rel(dst) + " does not point into the repository"}, nil
	}
	if err := os.Remove(dst); err != nil {
		return Event{}, err
	}
	return Event{Level: OK, Verb: "unlinked", Subject: name, Detail: s.Rel(dst)}, nil
}

// moveToBackup moves path under <BackupDir>/ccfg-<time>/ and returns the new path.
func moveToBackup(s Scope, path string) (string, error) {
	rel, err := filepath.Rel(s.Dir, path)
	if err != nil {
		rel = filepath.Base(path)
	}
	dst := filepath.Join(s.BackupDir, "ccfg-"+time.Now().Format("20060102-150405"), rel)
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return "", err
	}
	if err := os.Rename(path, dst); err != nil {
		return "", err
	}
	return dst, nil
}
