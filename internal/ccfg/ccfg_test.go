package ccfg

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fakeRepo builds a repository with a common skill `nasa`, a profile `eng`
// with skills `tdd` and `shared`, and a profile `res` that links `shared`
// from eng through a relative symlink.
func fakeRepo(t *testing.T) *Repo {
	t.Helper()
	root := t.TempDir()
	mkSkill(t, filepath.Join(root, "skills", "nasa"), "NASA writing")
	mkSkill(t, filepath.Join(root, "profiles", "eng", "skills", "tdd"), "Test first")
	mkSkill(t, filepath.Join(root, "profiles", "eng", "skills", "shared"), "Shared by two profiles")
	writeFile(t, filepath.Join(root, "CLAUDE.md"), "# common\n")
	writeFile(t, filepath.Join(root, "profiles", "eng", "CLAUDE.md"), "# eng\n")
	writeFile(t, filepath.Join(root, "profiles", "res", "CLAUDE.md"), "# res\n")
	mustMkdir(t, filepath.Join(root, "profiles", "res", "skills"))
	if err := os.Symlink("../../eng/skills/shared", filepath.Join(root, "profiles", "res", "skills", "shared")); err != nil {
		t.Fatal(err)
	}
	r, err := LoadRepo(root)
	if err != nil {
		t.Fatal(err)
	}
	return r
}

func projectScope(t *testing.T) Scope {
	t.Helper()
	s, err := ProjectScope(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	return s
}

func mkSkill(t *testing.T, dir, desc string) {
	t.Helper()
	mustMkdir(t, dir)
	writeFile(t, filepath.Join(dir, "SKILL.md"), "---\nname: x\ndescription: \""+desc+"\"\n---\n# x\n")
}

func mustMkdir(t *testing.T, dir string) {
	t.Helper()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
}

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	mustMkdir(t, filepath.Dir(path))
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func readFile(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return string(data)
}

func linkTarget(t *testing.T, path string) string {
	t.Helper()
	real, err := filepath.EvalSymlinks(path)
	if err != nil {
		return ""
	}
	return real
}

func state(t *testing.T, r *Repo, s Scope, profile string) string {
	t.Helper()
	st, err := r.Status(s)
	if err != nil {
		t.Fatal(err)
	}
	for _, ps := range st.Profiles {
		if ps.Profile.Name == profile {
			return ps.State()
		}
	}
	t.Fatalf("no profile %s in status", profile)
	return ""
}

func TestLoadRepoListsCommonFirstAndResolvesSharedSkillsToOnePath(t *testing.T) {
	r := fakeRepo(t)

	if got := strings.Join(r.ProfileNames(), ","); got != "common,eng,res" {
		t.Fatalf("profiles = %q, want common,eng,res", got)
	}
	eng, _ := r.Profile("eng")
	res, _ := r.Profile("res")
	if len(eng.Skills) != 2 || len(res.Skills) != 1 {
		t.Fatalf("skills: eng=%d res=%d, want 2 and 1", len(eng.Skills), len(res.Skills))
	}
	if eng.Skills[0].Path != res.Skills[0].Path {
		t.Fatalf("shared skill paths differ: %s vs %s", eng.Skills[0].Path, res.Skills[0].Path)
	}
	if eng.Skills[1].Description != "Test first" {
		t.Fatalf("description = %q, want Test first", eng.Skills[1].Description)
	}
}

func TestInstallLinksEverySkillOfTheProfileAndImportsItsClaudeMD(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)

	events, err := r.Install(s, []string{"eng"}, Options{})
	if err != nil {
		t.Fatal(err)
	}

	tdd, _ := r.Skill("tdd")
	if got := linkTarget(t, filepath.Join(s.SkillsDir, "tdd")); got != tdd.Path {
		t.Fatalf("tdd link -> %q, want %q", got, tdd.Path)
	}
	md := readFile(t, s.ClaudeMD)
	eng, _ := r.Profile("eng")
	if !strings.Contains(md, blockBegin) || !strings.Contains(md, "@"+eng.ClaudeMD) {
		t.Fatalf("CLAUDE.md lacks the block or the import:\n%s", md)
	}
	if got := state(t, r, s, "eng"); got != "installed" {
		t.Fatalf("state = %q, want installed", got)
	}
	if countVerb(events, "linked") != 2 || countVerb(events, "imported") != 1 {
		t.Fatalf("events = %+v", events)
	}
}

func TestInstallTwiceChangesNothingTheSecondTime(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)
	if _, err := r.Install(s, []string{"eng"}, Options{}); err != nil {
		t.Fatal(err)
	}
	before := readFile(t, s.ClaudeMD)

	events, err := r.Install(s, []string{"eng"}, Options{})
	if err != nil {
		t.Fatal(err)
	}

	if countVerb(events, "linked") != 0 || countVerb(events, "imported") != 0 || countVerb(events, "kept") != 3 {
		t.Fatalf("second install events = %+v", events)
	}
	if readFile(t, s.ClaudeMD) != before {
		t.Fatalf("CLAUDE.md changed on the second install")
	}
}

func TestInstallKeepsUserTextAroundTheBlock(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)
	writeFile(t, s.ClaudeMD, "# My project\n\nKeep this line.\n")

	if _, err := r.Install(s, []string{"eng"}, Options{}); err != nil {
		t.Fatal(err)
	}

	md := readFile(t, s.ClaudeMD)
	if !strings.HasPrefix(md, blockBegin) {
		t.Fatalf("block is not at the top:\n%s", md)
	}
	if !strings.Contains(md, "# My project\n\nKeep this line.\n") {
		t.Fatalf("user text lost:\n%s", md)
	}
}

func TestUninstallKeepsASkillThatAnotherInstalledProfileStillUses(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)
	if _, err := r.Install(s, []string{"eng", "res"}, Options{}); err != nil {
		t.Fatal(err)
	}

	events, err := r.Uninstall(s, []string{"eng"}, false)
	if err != nil {
		t.Fatal(err)
	}

	if _, err := os.Lstat(filepath.Join(s.SkillsDir, "tdd")); !os.IsNotExist(err) {
		t.Fatalf("tdd link still exists")
	}
	if _, err := os.Lstat(filepath.Join(s.SkillsDir, "shared")); err != nil {
		t.Fatalf("shared link removed although res uses it")
	}
	if countVerb(events, "kept") != 1 || countVerb(events, "unlinked") != 1 || countVerb(events, "removed") != 1 {
		t.Fatalf("events = %+v", events)
	}
	if got := state(t, r, s, "eng"); got != "" {
		t.Fatalf("eng state = %q, want not installed", got)
	}
	if got := state(t, r, s, "res"); got != "installed" {
		t.Fatalf("res state = %q, want installed", got)
	}
}

func TestUninstallAllRemovesTheBlockAndEveryRepoLinkButKeepsOtherLinks(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)
	writeFile(t, s.ClaudeMD, "Mine.\n")
	if _, err := r.Install(s, []string{"eng", "nasa"}, Options{}); err != nil {
		t.Fatal(err)
	}
	foreign := t.TempDir()
	if err := os.Symlink(foreign, filepath.Join(s.SkillsDir, "foreign")); err != nil {
		t.Fatal(err)
	}

	if _, err := r.Uninstall(s, nil, true); err != nil {
		t.Fatal(err)
	}

	entries, _ := os.ReadDir(s.SkillsDir)
	if len(entries) != 1 || entries[0].Name() != "foreign" {
		t.Fatalf("skills dir = %v, want only foreign", entries)
	}
	if got := readFile(t, s.ClaudeMD); got != "Mine.\n" {
		t.Fatalf("CLAUDE.md = %q, want only the user text", got)
	}
}

func TestSwitchReplacesTheOtherProfilesAndLeavesCommonAlone(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)
	if _, err := r.Install(s, []string{"common", "eng"}, Options{}); err != nil {
		t.Fatal(err)
	}

	if _, err := r.Switch(s, "res", Options{}); err != nil {
		t.Fatal(err)
	}

	if got := state(t, r, s, "eng"); got != "" {
		t.Fatalf("eng state = %q, want not installed", got)
	}
	if got := state(t, r, s, "res"); got != "installed" {
		t.Fatalf("res state = %q, want installed", got)
	}
	if got := state(t, r, s, "common"); got != "installed" {
		t.Fatalf("common state = %q, want installed", got)
	}
}

func TestSwitchToCommonIsRefused(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)

	if _, err := r.Switch(s, "common", Options{}); err == nil {
		t.Fatal("switch to common succeeded, want an error")
	}
}

func TestInstallReplacesALegacyClaudeMDSymlinkWithAFile(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)
	if err := os.Symlink(filepath.Join(r.Root, "CLAUDE.md"), s.ClaudeMD); err != nil {
		t.Fatal(err)
	}

	if _, err := r.Install(s, []string{"common"}, Options{}); err != nil {
		t.Fatal(err)
	}

	fi, err := os.Lstat(s.ClaudeMD)
	if err != nil || fi.Mode()&os.ModeSymlink != 0 {
		t.Fatalf("CLAUDE.md is still a symlink (err=%v)", err)
	}
	if !strings.Contains(readFile(t, s.ClaudeMD), "@"+filepath.Join(r.Root, "CLAUDE.md")) {
		t.Fatalf("CLAUDE.md does not import the common profile:\n%s", readFile(t, s.ClaudeMD))
	}
	if readFile(t, filepath.Join(r.Root, "CLAUDE.md")) != "# common\n" {
		t.Fatalf("the repository CLAUDE.md changed")
	}
}

func TestInstallMovesALooseImportIntoTheBlock(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)
	eng, _ := r.Profile("eng")
	writeFile(t, s.ClaudeMD, "Intro.\n@"+eng.ClaudeMD+"\n")

	if _, err := r.Install(s, []string{"nasa"}, Options{}); err != nil {
		t.Fatal(err)
	}

	md := readFile(t, s.ClaudeMD)
	if strings.Count(md, "@"+eng.ClaudeMD) != 1 {
		t.Fatalf("eng import count != 1:\n%s", md)
	}
	block := md[strings.Index(md, blockBegin):strings.Index(md, blockEnd)]
	if !strings.Contains(block, "@"+eng.ClaudeMD) {
		t.Fatalf("eng import is outside the block:\n%s", md)
	}
	if got := state(t, r, s, "eng"); got != "partial" {
		t.Fatalf("eng state = %q, want partial (imported, no skills linked)", got)
	}
}

func TestInstallRefusesToClobberARealDirectoryWithoutForce(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)
	mustMkdir(t, filepath.Join(s.SkillsDir, "tdd"))

	if _, err := r.Install(s, []string{"tdd"}, Options{}); err == nil {
		t.Fatal("install over a real directory succeeded, want an error")
	}
	if _, err := r.Install(s, []string{"tdd"}, Options{Force: true}); err != nil {
		t.Fatal(err)
	}
	tdd, _ := r.Skill("tdd")
	if got := linkTarget(t, filepath.Join(s.SkillsDir, "tdd")); got != tdd.Path {
		t.Fatalf("tdd link -> %q, want %q", got, tdd.Path)
	}
	backups, _ := filepath.Glob(filepath.Join(s.BackupDir, "ccfg-*", ".claude", "skills", "tdd"))
	if len(backups) != 1 {
		t.Fatalf("backup of the directory missing: %v", backups)
	}
}

func TestDoctorFindsAndFixesABrokenLink(t *testing.T) {
	r := fakeRepo(t)
	s := projectScope(t)
	mustMkdir(t, s.SkillsDir)
	if err := os.Symlink(filepath.Join(r.Root, "skills", "gone"), filepath.Join(s.SkillsDir, "gone")); err != nil {
		t.Fatal(err)
	}

	events, err := r.Doctor(s, false)
	if err != nil {
		t.Fatal(err)
	}
	if countVerb(events, "broken") != 1 {
		t.Fatalf("doctor events = %+v, want one broken", events)
	}

	if _, err := r.Doctor(s, true); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Lstat(filepath.Join(s.SkillsDir, "gone")); !os.IsNotExist(err) {
		t.Fatalf("broken link still present")
	}
	events, _ = r.Doctor(s, false)
	if countVerb(events, "healthy") != 1 {
		t.Fatalf("after fix: %+v, want healthy", events)
	}
}

func TestResolveRejectsAnUnknownName(t *testing.T) {
	r := fakeRepo(t)

	if _, _, err := r.Resolve([]string{"nope"}); err == nil || !strings.Contains(err.Error(), "nope") {
		t.Fatalf("err = %v, want an error that names nope", err)
	}
}

func countVerb(events []Event, verb string) int {
	n := 0
	for _, e := range events {
		if e.Verb == verb {
			n++
		}
	}
	return n
}
