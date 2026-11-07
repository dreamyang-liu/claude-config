package ccfg

import (
	"os"
	"path/filepath"
	"strings"
)

const (
	blockBegin = "<!-- ccfg:begin -->"
	blockEnd   = "<!-- ccfg:end -->"
)

// claudeMD is a CLAUDE.md split around the managed block. The block holds one
// @import line per installed profile. Text before and after the block belongs
// to the user and is written back unchanged. A CLAUDE.md that is a symlink is
// treated as empty: writing it replaces the link with a regular file.
type claudeMD struct {
	path    string
	before  []string
	imports []string
	after   []string
	exists  bool
	isLink  bool
}

func readClaudeMD(path string) (*claudeMD, error) {
	c := &claudeMD{path: path}
	fi, err := os.Lstat(path)
	if os.IsNotExist(err) {
		return c, nil
	}
	if err != nil {
		return nil, err
	}
	c.exists = true
	if fi.Mode()&os.ModeSymlink != 0 {
		c.isLink = true
		return c, nil
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	lines := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
	if len(lines) == 1 && lines[0] == "" {
		lines = nil
	}
	begin, end := -1, -1
	for i, l := range lines {
		switch strings.TrimSpace(l) {
		case blockBegin:
			if begin < 0 {
				begin = i
			}
		case blockEnd:
			if begin >= 0 && end < 0 {
				end = i
			}
		}
	}
	if begin < 0 || end < 0 {
		// No block yet. It goes at the top, so the imports load first.
		c.after = lines
		return c, nil
	}
	c.before = lines[:begin]
	c.imports = lines[begin+1 : end]
	c.after = lines[end+1:]
	return c, nil
}

func (c *claudeMD) has(line string) bool {
	for _, l := range c.imports {
		if strings.TrimSpace(l) == line {
			return true
		}
	}
	return false
}

// add appends an import line. It reports whether the line was new.
func (c *claudeMD) add(line string) bool {
	if c.has(line) {
		return false
	}
	c.imports = append(c.imports, line)
	return true
}

// remove drops an import line. It reports whether the line was present.
func (c *claudeMD) remove(line string) bool {
	kept := c.imports[:0]
	found := false
	for _, l := range c.imports {
		if strings.TrimSpace(l) == line {
			found = true
			continue
		}
		kept = append(kept, l)
	}
	c.imports = kept
	return found
}

// write stores the file. With no imports, the block is omitted. A file that
// would be empty and did not exist before is not created.
func (c *claudeMD) write() error {
	var out []string
	before, after := c.before, c.after
	if len(c.imports) == 0 {
		before = trimBlankEnd(before)
		after = trimBlankStart(after)
		if len(before) > 0 && len(after) > 0 {
			before = append(before, "")
		}
	}
	out = append(out, before...)
	if len(c.imports) > 0 {
		if len(out) > 0 && strings.TrimSpace(out[len(out)-1]) != "" {
			out = append(out, "")
		}
		out = append(out, blockBegin)
		out = append(out, c.imports...)
		out = append(out, blockEnd)
		if len(c.after) > 0 && strings.TrimSpace(c.after[0]) != "" {
			out = append(out, "")
		}
	}
	out = append(out, after...)
	content := strings.TrimRight(strings.Join(out, "\n"), "\n")
	if content == "" {
		if c.exists && !c.isLink {
			return os.Remove(c.path)
		}
		if c.isLink {
			return os.Remove(c.path)
		}
		return nil
	}
	if c.isLink {
		if err := os.Remove(c.path); err != nil {
			return err
		}
		c.isLink = false
	}
	if err := os.MkdirAll(filepath.Dir(c.path), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(c.path, []byte(content+"\n"), 0o644); err != nil {
		return err
	}
	c.exists = true
	return nil
}

func trimBlankStart(lines []string) []string {
	for len(lines) > 0 && strings.TrimSpace(lines[0]) == "" {
		lines = lines[1:]
	}
	return lines
}

func trimBlankEnd(lines []string) []string {
	for len(lines) > 0 && strings.TrimSpace(lines[len(lines)-1]) == "" {
		lines = lines[:len(lines)-1]
	}
	return lines
}

// importLine is the @import line for a profile's CLAUDE.md, with ~ for home.
func importLine(home, claudeMD string) string {
	return "@" + tildify(home, claudeMD)
}

// looseImports returns the @import lines outside the block that point into
// the repository, for example lines that the old install.sh appended.
func (r *Repo) looseImports(c *claudeMD, home string) []string {
	var out []string
	for _, l := range append(append([]string{}, c.before...), c.after...) {
		if r.isRepoImport(strings.TrimSpace(l), home) {
			out = append(out, strings.TrimSpace(l))
		}
	}
	return out
}

func (r *Repo) isRepoImport(line, home string) bool {
	if !strings.HasPrefix(line, "@") || strings.ContainsAny(line, " \t") {
		return false
	}
	path := untildify(home, line[1:])
	real, err := filepath.EvalSymlinks(path)
	if err != nil {
		real = filepath.Clean(path)
	}
	return r.Inside(real)
}

// migrateLoose moves loose repository imports into the block. It returns the
// lines that it moved.
func (r *Repo) migrateLoose(c *claudeMD, home string) []string {
	var moved []string
	filter := func(lines []string) []string {
		kept := lines[:0]
		for _, l := range lines {
			t := strings.TrimSpace(l)
			if r.isRepoImport(t, home) {
				moved = append(moved, t)
				c.add(t)
				continue
			}
			kept = append(kept, l)
		}
		return kept
	}
	c.before = filter(c.before)
	c.after = filter(c.after)
	return moved
}
