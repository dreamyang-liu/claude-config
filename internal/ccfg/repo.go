// Package ccfg installs the skills and CLAUDE.md fragments of a claude-config
// repository into Claude Code scopes: the global ~/.claude directory or one
// project. A scope holds symlinks into the repository and a managed block of
// @import lines in its CLAUDE.md. The package derives all state from those
// files. It keeps no state file of its own.
package ccfg

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// CommonProfile is the implicit profile made of the repository root CLAUDE.md
// and the skills/ directory. Every scope that uses the repository installs it.
const CommonProfile = "common"

// Skill is one skill directory of the repository. Path is the real directory,
// after symlinks are resolved, so two profiles that share one skill through a
// relative link have the same Path.
type Skill struct {
	Name        string
	Path        string
	Profile     string
	Description string
}

// Profile is a CLAUDE.md fragment plus the skills that go with it.
type Profile struct {
	Name     string
	Dir      string
	ClaudeMD string
	Skills   []Skill
}

// Repo is a loaded claude-config repository. Profiles[0] is the common profile.
type Repo struct {
	Root     string
	Profiles []Profile
}

// FindRepo locates the repository. It tries, in order: the explicit path, the
// CLAUDE_CONFIG_REPO environment variable, each parent of the running binary,
// and ~/Projects/claude-config.
func FindRepo(explicit string) (*Repo, error) {
	for _, c := range repoCandidates(explicit) {
		if isRepo(c) {
			return LoadRepo(c)
		}
	}
	return nil, fmt.Errorf("no claude-config repository found; pass --repo or set CLAUDE_CONFIG_REPO")
}

func repoCandidates(explicit string) []string {
	var out []string
	if explicit != "" {
		out = append(out, explicit)
	}
	if env := os.Getenv("CLAUDE_CONFIG_REPO"); env != "" {
		out = append(out, env)
	}
	if exe, err := os.Executable(); err == nil {
		if real, err := filepath.EvalSymlinks(exe); err == nil {
			for d := filepath.Dir(real); ; d = filepath.Dir(d) {
				out = append(out, d)
				if d == filepath.Dir(d) {
					break
				}
			}
		}
	}
	if home, err := os.UserHomeDir(); err == nil {
		out = append(out, filepath.Join(home, "Projects", "claude-config"))
	}
	return out
}

func isRepo(dir string) bool {
	return isDir(filepath.Join(dir, "skills")) &&
		isDir(filepath.Join(dir, "profiles")) &&
		isFile(filepath.Join(dir, "CLAUDE.md"))
}

// LoadRepo reads the profiles and skills under root.
func LoadRepo(root string) (*Repo, error) {
	real, err := filepath.EvalSymlinks(root)
	if err != nil {
		return nil, fmt.Errorf("repository %s: %w", root, err)
	}
	if !isRepo(real) {
		return nil, fmt.Errorf("%s is not a claude-config repository (needs CLAUDE.md, skills/, profiles/)", real)
	}
	r := &Repo{Root: real}
	common, err := loadProfile(CommonProfile, real, filepath.Join(real, "skills"))
	if err != nil {
		return nil, err
	}
	r.Profiles = append(r.Profiles, common)
	entries, err := os.ReadDir(filepath.Join(real, "profiles"))
	if err != nil {
		return nil, err
	}
	for _, e := range entries {
		if !e.IsDir() || strings.HasPrefix(e.Name(), ".") {
			continue
		}
		dir := filepath.Join(real, "profiles", e.Name())
		p, err := loadProfile(e.Name(), dir, filepath.Join(dir, "skills"))
		if err != nil {
			return nil, err
		}
		r.Profiles = append(r.Profiles, p)
	}
	return r, nil
}

func loadProfile(name, dir, skillsDir string) (Profile, error) {
	p := Profile{Name: name, Dir: dir, ClaudeMD: filepath.Join(dir, "CLAUDE.md")}
	entries, err := os.ReadDir(skillsDir)
	if os.IsNotExist(err) {
		return p, nil
	}
	if err != nil {
		return p, err
	}
	for _, e := range entries {
		path := filepath.Join(skillsDir, e.Name())
		real, err := filepath.EvalSymlinks(path)
		if err != nil || !isDir(real) || !isFile(filepath.Join(real, "SKILL.md")) {
			continue
		}
		p.Skills = append(p.Skills, Skill{
			Name:        e.Name(),
			Path:        real,
			Profile:     name,
			Description: readDescription(filepath.Join(real, "SKILL.md")),
		})
	}
	sort.Slice(p.Skills, func(i, j int) bool { return p.Skills[i].Name < p.Skills[j].Name })
	return p, nil
}

// readDescription returns the description field of the SKILL.md front matter,
// or "" when the file has none.
func readDescription(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	lines := strings.Split(string(data), "\n")
	if len(lines) == 0 || strings.TrimSpace(lines[0]) != "---" {
		return ""
	}
	for _, line := range lines[1:] {
		if strings.TrimSpace(line) == "---" {
			return ""
		}
		if rest, ok := strings.CutPrefix(line, "description:"); ok {
			return strings.Trim(strings.TrimSpace(rest), `"'`)
		}
	}
	return ""
}

// Profile returns the profile with that name.
func (r *Repo) Profile(name string) (*Profile, bool) {
	for i := range r.Profiles {
		if r.Profiles[i].Name == name {
			return &r.Profiles[i], true
		}
	}
	return nil, false
}

// Skill returns the first skill with that name, searching the common profile
// first and then each profile in directory order.
func (r *Repo) Skill(name string) (*Skill, bool) {
	for i := range r.Profiles {
		for j := range r.Profiles[i].Skills {
			if r.Profiles[i].Skills[j].Name == name {
				return &r.Profiles[i].Skills[j], true
			}
		}
	}
	return nil, false
}

// Resolve splits names into profiles and skills. A name that is both resolves
// to the profile. An unknown name is an error that lists the valid names.
func (r *Repo) Resolve(names []string) ([]*Profile, []*Skill, error) {
	var profiles []*Profile
	var skills []*Skill
	for _, n := range names {
		if p, ok := r.Profile(n); ok {
			profiles = append(profiles, p)
			continue
		}
		if s, ok := r.Skill(n); ok {
			skills = append(skills, s)
			continue
		}
		return nil, nil, fmt.Errorf("unknown profile or skill %q; profiles: %s; run `ccfg list` for the skills",
			n, strings.Join(r.ProfileNames(), ", "))
	}
	return profiles, skills, nil
}

// ProfileNames returns the profile names, common first.
func (r *Repo) ProfileNames() []string {
	out := make([]string, 0, len(r.Profiles))
	for _, p := range r.Profiles {
		out = append(out, p.Name)
	}
	return out
}

// Inside reports whether the real path is under the repository root.
func (r *Repo) Inside(path string) bool {
	rel, err := filepath.Rel(r.Root, path)
	if err != nil {
		return false
	}
	return rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator))
}

// SkillsByPath indexes every skill of the repository by its real path.
func (r *Repo) SkillsByPath() map[string][]*Skill {
	out := map[string][]*Skill{}
	for i := range r.Profiles {
		for j := range r.Profiles[i].Skills {
			s := &r.Profiles[i].Skills[j]
			out[s.Path] = append(out[s.Path], s)
		}
	}
	return out
}

func isDir(path string) bool {
	fi, err := os.Stat(path)
	return err == nil && fi.IsDir()
}

func isFile(path string) bool {
	fi, err := os.Stat(path)
	return err == nil && fi.Mode().IsRegular()
}
