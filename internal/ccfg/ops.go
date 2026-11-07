package ccfg

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Level is the weight of an Event.
type Level int

const (
	Info Level = iota
	OK
	Warn
	Fail
)

// Event is one thing an operation did or found. Verb is a short past-tense
// word such as "linked"; Subject is the skill, profile or file; Detail adds
// the path or the reason.
type Event struct {
	Level   Level
	Verb    string
	Subject string
	Detail  string
}

// Options tunes an operation.
type Options struct {
	// Force moves a real file or directory aside when a link needs its place.
	Force bool
	// Keep leaves a real file or directory in place and skips that skill.
	Keep bool
}

// Conflicts lists the skills among names whose place in the scope is taken by
// a real file or directory, not a symlink. Install refuses to run while such
// a conflict exists, unless Options.Force or Options.Keep says what to do.
func (r *Repo) Conflicts(s Scope, names []string) ([]string, error) {
	profiles, skills, err := r.Resolve(names)
	if err != nil {
		return nil, err
	}
	for _, p := range profiles {
		for i := range p.Skills {
			skills = append(skills, &p.Skills[i])
		}
	}
	var out []string
	seen := map[string]bool{}
	for _, sk := range skills {
		if seen[sk.Name] {
			continue
		}
		seen[sk.Name] = true
		fi, err := os.Lstat(filepath.Join(s.SkillsDir, sk.Name))
		if err == nil && fi.Mode()&os.ModeSymlink == 0 {
			out = append(out, sk.Name)
		}
	}
	return out, nil
}

// Install links the skills of each named profile and skill into the scope and
// imports each profile's CLAUDE.md. Names are profiles or skills. It changes
// nothing when a real file or directory is in the way and Options says
// neither Force nor Keep.
func (r *Repo) Install(s Scope, names []string, opt Options) ([]Event, error) {
	profiles, skills, err := r.Resolve(names)
	if err != nil {
		return nil, err
	}
	if !opt.Force && !opt.Keep {
		conflicts, err := r.Conflicts(s, names)
		if err != nil {
			return nil, err
		}
		if len(conflicts) > 0 {
			return nil, fmt.Errorf("%s already holds a real directory for: %s\n  --force moves them to %s and links the skills\n  --keep  leaves them alone and links only the others",
				s.Rel(s.SkillsDir), strings.Join(conflicts, ", "), s.Rel(s.BackupDir))
		}
	}
	home, _ := os.UserHomeDir()
	md, err := readClaudeMD(s.ClaudeMD)
	if err != nil {
		return nil, err
	}
	var events []Event
	for _, moved := range r.migrateLoose(md, home) {
		events = append(events, Event{Level: OK, Verb: "moved", Subject: moved, Detail: "into the ccfg block of " + s.Rel(s.ClaudeMD)})
	}
	for _, p := range profiles {
		for i := range p.Skills {
			ev, err := linkSkill(s, &p.Skills[i], opt)
			if err != nil {
				return events, err
			}
			events = append(events, ev)
		}
		line := importLine(home, p.ClaudeMD)
		if md.add(line) {
			events = append(events, Event{Level: OK, Verb: "imported", Subject: p.Name, Detail: line + " in " + s.Rel(s.ClaudeMD)})
		} else {
			events = append(events, Event{Level: Info, Verb: "kept", Subject: p.Name, Detail: line})
		}
	}
	for _, sk := range skills {
		ev, err := linkSkill(s, sk, opt)
		if err != nil {
			return events, err
		}
		events = append(events, ev)
	}
	if err := md.write(); err != nil {
		return events, err
	}
	events = append(events, gitignoreHint(s)...)
	return events, nil
}

// Uninstall removes the imports of the named profiles and the links of their
// skills, and the links of the named skills. A skill that another installed
// profile still needs is kept. With all set, it removes every link into the
// repository and the whole import block.
func (r *Repo) Uninstall(s Scope, names []string, all bool) ([]Event, error) {
	home, _ := os.UserHomeDir()
	md, err := readClaudeMD(s.ClaudeMD)
	if err != nil {
		return nil, err
	}
	if all {
		return r.uninstallAll(s, md, home)
	}
	profiles, skills, err := r.Resolve(names)
	if err != nil {
		return nil, err
	}
	var events []Event
	for _, p := range profiles {
		line := importLine(home, p.ClaudeMD)
		if md.remove(line) {
			events = append(events, Event{Level: OK, Verb: "removed", Subject: p.Name, Detail: line})
		}
	}
	keep := r.skillsStillNeeded(md, home)
	for _, p := range profiles {
		for _, sk := range p.Skills {
			if keep[sk.Path] != "" {
				events = append(events, Event{Level: Info, Verb: "kept", Subject: sk.Name, Detail: "profile " + keep[sk.Path] + " still uses it"})
				continue
			}
			ev, err := unlinkSkill(r, s, sk.Name)
			if err != nil {
				return events, err
			}
			events = append(events, ev)
		}
	}
	for _, sk := range skills {
		ev, err := unlinkSkill(r, s, sk.Name)
		if err != nil {
			return events, err
		}
		events = append(events, ev)
	}
	if err := md.write(); err != nil {
		return events, err
	}
	return events, nil
}

func (r *Repo) uninstallAll(s Scope, md *claudeMD, home string) ([]Event, error) {
	var events []Event
	links, err := r.scanLinks(s)
	if err != nil {
		return nil, err
	}
	for _, l := range links {
		ev, err := unlinkSkill(r, s, l.Name)
		if err != nil {
			return events, err
		}
		events = append(events, ev)
	}
	for _, line := range append(append([]string{}, md.imports...), r.looseImports(md, home)...) {
		md.remove(line)
		events = append(events, Event{Level: OK, Verb: "removed", Subject: line, Detail: s.Rel(s.ClaudeMD)})
	}
	r.migrateLoose(md, home)
	md.imports = nil
	if err := md.write(); err != nil {
		return events, err
	}
	return events, nil
}

// skillsStillNeeded maps the real path of each skill that an imported profile
// uses to that profile's name.
func (r *Repo) skillsStillNeeded(md *claudeMD, home string) map[string]string {
	out := map[string]string{}
	for i := range r.Profiles {
		p := &r.Profiles[i]
		if !md.has(importLine(home, p.ClaudeMD)) {
			continue
		}
		for _, sk := range p.Skills {
			out[sk.Path] = p.Name
		}
	}
	return out
}

// Switch makes name the only non-common profile of the scope.
func (r *Repo) Switch(s Scope, name string, opt Options) ([]Event, error) {
	if name == CommonProfile {
		return nil, fmt.Errorf("%s is the base layer, not a profile to switch to; use `ccfg install common`", CommonProfile)
	}
	if _, ok := r.Profile(name); !ok {
		return nil, fmt.Errorf("unknown profile %q; profiles: %s", name, strings.Join(r.ProfileNames(), ", "))
	}
	st, err := r.Status(s)
	if err != nil {
		return nil, err
	}
	var events []Event
	for _, ps := range st.Installed() {
		if ps.Profile.Name == CommonProfile || ps.Profile.Name == name {
			continue
		}
		evs, err := r.Uninstall(s, []string{ps.Profile.Name}, false)
		events = append(events, evs...)
		if err != nil {
			return events, err
		}
	}
	evs, err := r.Install(s, []string{name}, opt)
	events = append(events, evs...)
	return events, err
}

// Doctor reports broken links, loose imports and a legacy CLAUDE.md symlink.
// With fix set, it removes the broken links, moves the loose imports into the
// block, and replaces the symlink with a file that imports the common profile.
func (r *Repo) Doctor(s Scope, fix bool) ([]Event, error) {
	home, _ := os.UserHomeDir()
	st, err := r.Status(s)
	if err != nil {
		return nil, err
	}
	var events []Event
	for _, l := range st.Broken {
		if fix {
			if err := os.Remove(l.Path); err != nil {
				return events, err
			}
			events = append(events, Event{Level: OK, Verb: "removed", Subject: l.Name, Detail: "broken link to " + l.Target})
		} else {
			events = append(events, Event{Level: Warn, Verb: "broken", Subject: l.Name, Detail: l.Path + " -> " + l.Target + " (missing)"})
		}
	}
	md, err := readClaudeMD(s.ClaudeMD)
	if err != nil {
		return events, err
	}
	if st.ClaudeMDIsLink {
		if fix {
			if common, ok := r.Profile(CommonProfile); ok {
				md.add(importLine(home, common.ClaudeMD))
			}
			events = append(events, Event{Level: OK, Verb: "replaced", Subject: s.Rel(s.ClaudeMD), Detail: "symlink became a file that imports the common profile"})
		} else {
			events = append(events, Event{Level: Warn, Verb: "legacy", Subject: s.Rel(s.ClaudeMD), Detail: "is a symlink; ccfg manages an import block in a regular file (run `ccfg doctor --fix`)"})
		}
	}
	for _, line := range st.Loose {
		if fix {
			events = append(events, Event{Level: OK, Verb: "moved", Subject: line, Detail: "into the ccfg block"})
		} else {
			events = append(events, Event{Level: Warn, Verb: "loose", Subject: line, Detail: "import outside the ccfg block (run `ccfg doctor --fix`)"})
		}
	}
	if fix {
		r.migrateLoose(md, home)
		if err := md.write(); err != nil {
			return events, err
		}
	}
	for _, ps := range st.Profiles {
		if ps.State() == "partial" {
			events = append(events, Event{Level: Info, Verb: "partial", Subject: ps.Profile.Name,
				Detail: fmt.Sprintf("%d of %d skills linked, import %s (run `ccfg install %s`)", ps.Linked, ps.Total, yesNo(ps.Imported), ps.Profile.Name)})
		}
	}
	if len(events) == 0 {
		events = append(events, Event{Level: OK, Verb: "healthy", Subject: s.String()})
	}
	return events, nil
}

func yesNo(b bool) string {
	if b {
		return "present"
	}
	return "missing"
}

// gitignoreHint warns when a project under git does not ignore .claude/skills,
// because the links hold paths of this machine.
func gitignoreHint(s Scope) []Event {
	if s.Kind != Project || !isDir(filepath.Join(s.Dir, ".git")) {
		return nil
	}
	data, _ := os.ReadFile(filepath.Join(s.Dir, ".gitignore"))
	for _, l := range strings.Split(string(data), "\n") {
		t := strings.Trim(strings.TrimSpace(l), "/")
		if t == ".claude/skills" || t == ".claude" {
			return nil
		}
	}
	return []Event{{Level: Warn, Verb: "hint", Subject: ".gitignore", Detail: "add `.claude/skills/`; the links hold paths that exist only on this machine"}}
}
