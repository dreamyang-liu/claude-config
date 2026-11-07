package ccfg

import (
	"os"
)

// ProfileStatus is how much of one profile a scope has.
type ProfileStatus struct {
	Profile  *Profile
	Imported bool
	Linked   int
	Total    int
}

// State is "installed" (imported, every skill linked), "partial" (imported,
// some skill missing) or "" (not imported). A skill that is linked without
// its profile's import counts as an individual skill, not as profile state.
func (ps ProfileStatus) State() string {
	switch {
	case !ps.Imported:
		return ""
	case ps.Linked == ps.Total:
		return "installed"
	default:
		return "partial"
	}
}

// ScopeStatus is everything the tool can see in one scope.
type ScopeStatus struct {
	Scope          Scope
	Profiles       []ProfileStatus
	Links          []Link
	Broken         []Link
	Loose          []string
	ClaudeMDIsLink bool
	ClaudeMDExists bool
}

// Installed lists the profiles whose State is "installed" or "partial".
func (st *ScopeStatus) Installed() []ProfileStatus {
	var out []ProfileStatus
	for _, ps := range st.Profiles {
		if ps.State() != "" {
			out = append(out, ps)
		}
	}
	return out
}

// Status reads the scope and compares it with the repository.
func (r *Repo) Status(s Scope) (*ScopeStatus, error) {
	home, _ := os.UserHomeDir()
	links, err := r.scanLinks(s)
	if err != nil {
		return nil, err
	}
	md, err := readClaudeMD(s.ClaudeMD)
	if err != nil {
		return nil, err
	}
	st := &ScopeStatus{Scope: s, ClaudeMDIsLink: md.isLink, ClaudeMDExists: md.exists}
	linked := map[string]bool{}
	for _, l := range links {
		if l.Broken {
			st.Broken = append(st.Broken, l)
			continue
		}
		st.Links = append(st.Links, l)
		linked[l.Target] = true
	}
	for i := range r.Profiles {
		p := &r.Profiles[i]
		ps := ProfileStatus{Profile: p, Imported: md.has(importLine(home, p.ClaudeMD)), Total: len(p.Skills)}
		for _, sk := range p.Skills {
			if linked[sk.Path] {
				ps.Linked++
			}
		}
		st.Profiles = append(st.Profiles, ps)
	}
	st.Loose = r.looseImports(md, home)
	return st, nil
}
