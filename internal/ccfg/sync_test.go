package ccfg

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// gitRepoPair makes a bare origin with one commit holding a minimal repo, and
// a clone of it. It returns the clone as a loaded Repo and the origin path.
func gitRepoPair(t *testing.T) (*Repo, string) {
	t.Helper()
	root := t.TempDir()
	origin := filepath.Join(root, "origin.git")
	work := filepath.Join(root, "work")
	clone := filepath.Join(root, "clone")
	run(t, "", "git", "init", "-q", "--bare", origin)
	run(t, "", "git", "init", "-q", "-b", "main", work)
	writeFile(t, filepath.Join(work, "CLAUDE.md"), "# common\n")
	mkSkill(t, filepath.Join(work, "skills", "nasa"), "NASA")
	mustMkdir(t, filepath.Join(work, "profiles"))
	writeFile(t, filepath.Join(work, "profiles", ".keep"), "")
	gitCommit(t, work, "initial")
	run(t, work, "git", "remote", "add", "origin", origin)
	run(t, work, "git", "push", "-q", "-u", "origin", "main")
	run(t, "", "git", "clone", "-q", origin, clone)
	r, err := LoadRepo(clone)
	if err != nil {
		t.Fatal(err)
	}
	return r, work
}

func run(t *testing.T, dir string, name string, args ...string) string {
	t.Helper()
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "GIT_CONFIG_GLOBAL=/dev/null", "GIT_CONFIG_SYSTEM=/dev/null")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("%s %v: %v\n%s", name, args, err, out)
	}
	return strings.TrimSpace(string(out))
}

func gitCommit(t *testing.T, dir, msg string) {
	t.Helper()
	run(t, dir, "git", "add", "-A")
	run(t, dir, "git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", msg)
}

func TestUpdateFastForwardsACleanCloneThatIsBehind(t *testing.T) {
	r, work := gitRepoPair(t)
	mkSkill(t, filepath.Join(work, "skills", "ste"), "STE")
	gitCommit(t, work, "add ste")
	run(t, work, "git", "push", "-q", "origin", "main")

	events, err := r.Update(30 * time.Second)
	if err != nil {
		t.Fatal(err)
	}

	if countVerb(events, "updated") != 1 {
		t.Fatalf("events = %+v, want one updated", events)
	}
	if !isDir(filepath.Join(r.Root, "skills", "ste")) {
		t.Fatalf("the new skill did not arrive in the clone")
	}
	st, _ := r.State()
	if st.Behind != 0 || st.Ahead != 0 || st.Dirty {
		t.Fatalf("state after update = %+v, want in sync", st)
	}
}

func TestUpdateDoesNotPullOverLocalChanges(t *testing.T) {
	r, work := gitRepoPair(t)
	writeFile(t, filepath.Join(work, "CLAUDE.md"), "# common v2\n")
	gitCommit(t, work, "edit")
	run(t, work, "git", "push", "-q", "origin", "main")
	writeFile(t, filepath.Join(r.Root, "CLAUDE.md"), "# local edit\n")

	events, err := r.Update(30 * time.Second)
	if err != nil {
		t.Fatal(err)
	}

	if countVerb(events, "not pulled") != 1 {
		t.Fatalf("events = %+v, want one not pulled", events)
	}
	if readFile(t, filepath.Join(r.Root, "CLAUDE.md")) != "# local edit\n" {
		t.Fatalf("the local change was overwritten")
	}
}

func TestUpdateReportsACurrentClone(t *testing.T) {
	r, _ := gitRepoPair(t)

	events, err := r.Update(30 * time.Second)
	if err != nil {
		t.Fatal(err)
	}

	if countVerb(events, "current") != 1 {
		t.Fatalf("events = %+v, want one current", events)
	}
}

func TestUpdateOnADirectoryThatIsNotACloneReturnsErrNotGit(t *testing.T) {
	r := fakeRepo(t)

	if _, err := r.Update(5 * time.Second); err != ErrNotGit {
		t.Fatalf("err = %v, want ErrNotGit", err)
	}
}
