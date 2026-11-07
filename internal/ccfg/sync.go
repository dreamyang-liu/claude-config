package ccfg

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

// SyncState compares the local clone with its upstream branch.
type SyncState struct {
	Branch  string
	Ahead   int
	Behind  int
	Dirty   bool
	Fetched bool   // the fetch before the comparison succeeded
	Head    string // short hash
}

// ErrNotGit is returned when the repository directory is not a git clone.
var ErrNotGit = errors.New("the repository is not a git clone")

func (r *Repo) git(ctx context.Context, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, "git", append([]string{"-C", r.Root}, args...)...)
	var out, errb bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errb
	if err := cmd.Run(); err != nil {
		msg := strings.TrimSpace(errb.String())
		if msg == "" {
			msg = err.Error()
		}
		return "", fmt.Errorf("git %s: %s", args[0], msg)
	}
	return strings.TrimSpace(out.String()), nil
}

// Fetch runs `git fetch` with a deadline, so that an offline machine does not
// hang. It returns nil when the fetch succeeded.
func (r *Repo) Fetch(timeout time.Duration) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	if _, err := r.git(ctx, "rev-parse", "--git-dir"); err != nil {
		return ErrNotGit
	}
	_, err := r.git(ctx, "fetch", "--quiet")
	return err
}

// State reads the branch, the ahead and behind counts against the upstream,
// and whether the working tree has changes. It does not touch the network.
func (r *Repo) State() (SyncState, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	var st SyncState
	if _, err := r.git(ctx, "rev-parse", "--git-dir"); err != nil {
		return st, ErrNotGit
	}
	branch, err := r.git(ctx, "rev-parse", "--abbrev-ref", "HEAD")
	if err != nil {
		return st, err
	}
	st.Branch = branch
	st.Head, _ = r.git(ctx, "rev-parse", "--short", "HEAD")
	porcelain, err := r.git(ctx, "status", "--porcelain")
	if err != nil {
		return st, err
	}
	st.Dirty = porcelain != ""
	counts, err := r.git(ctx, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
	if err != nil {
		return st, fmt.Errorf("branch %s has no upstream: %w", branch, err)
	}
	parts := strings.Fields(counts)
	if len(parts) == 2 {
		st.Ahead, _ = strconv.Atoi(parts[0])
		st.Behind, _ = strconv.Atoi(parts[1])
	}
	return st, nil
}

// Update fetches, then fast-forwards the clone when that is safe: the tree is
// clean and the branch is only behind. Anything else is reported, not forced.
// A failed fetch (for example offline) is a warning, and the state is still
// reported from the last fetch.
func (r *Repo) Update(timeout time.Duration) ([]Event, error) {
	var events []Event
	fetchErr := r.Fetch(timeout)
	if errors.Is(fetchErr, ErrNotGit) {
		return nil, ErrNotGit
	}
	if fetchErr != nil {
		events = append(events, Event{Level: Warn, Verb: "offline", Subject: "repository", Detail: "fetch failed; using the local copy as it is"})
	}
	st, err := r.State()
	if err != nil {
		return events, err
	}
	st.Fetched = fetchErr == nil
	switch {
	case st.Dirty && st.Behind > 0:
		events = append(events, Event{Level: Warn, Verb: "not pulled", Subject: "repository",
			Detail: fmt.Sprintf("%d new commits on origin, but the clone has local changes; commit or stash them, then run `ccfg update`", st.Behind)})
	case st.Ahead > 0 && st.Behind > 0:
		events = append(events, Event{Level: Warn, Verb: "diverged", Subject: "repository",
			Detail: fmt.Sprintf("%d local and %d remote commits; merge or rebase by hand in %s", st.Ahead, st.Behind, r.Root)})
	case st.Behind > 0:
		ctx, cancel := context.WithTimeout(context.Background(), timeout)
		defer cancel()
		if _, err := r.git(ctx, "pull", "--ff-only", "--quiet"); err != nil {
			return events, err
		}
		head, _ := r.git(ctx, "rev-parse", "--short", "HEAD")
		events = append(events, Event{Level: OK, Verb: "updated", Subject: "repository",
			Detail: fmt.Sprintf("%s -> %s, %d commits", st.Head, head, st.Behind)})
	case st.Ahead > 0:
		events = append(events, Event{Level: Info, Verb: "ahead", Subject: "repository",
			Detail: fmt.Sprintf("%d local commits not pushed", st.Ahead)})
	default:
		if st.Fetched {
			events = append(events, Event{Level: Info, Verb: "current", Subject: "repository", Detail: st.Branch + " " + st.Head + " matches origin"})
		}
	}
	if st.Dirty && st.Behind == 0 {
		events = append(events, Event{Level: Info, Verb: "modified", Subject: "repository", Detail: "the clone has uncommitted changes"})
	}
	return events, nil
}
