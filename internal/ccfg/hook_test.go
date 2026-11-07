package ccfg

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func globalScopeAt(t *testing.T) Scope {
	t.Helper()
	dir := t.TempDir()
	return Scope{Kind: Global, Dir: dir, ClaudeMD: filepath.Join(dir, "CLAUDE.md"),
		SkillsDir: filepath.Join(dir, "skills"), BackupDir: filepath.Join(dir, "backups")}
}

func TestInstallHookKeepsTheOtherSettingsAndIsIdempotent(t *testing.T) {
	s := globalScopeAt(t)
	writeFile(t, SettingsPath(s), `{"env": {"A": "1"}, "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}]}}`)

	added, err := InstallHook(s, "/usr/local/bin/ccfg")
	if err != nil || !added {
		t.Fatalf("added=%v err=%v, want true nil", added, err)
	}
	again, err := InstallHook(s, "/usr/local/bin/ccfg")
	if err != nil || again {
		t.Fatalf("second install added=%v err=%v, want false nil", again, err)
	}

	var settings map[string]any
	if err := json.Unmarshal([]byte(readFile(t, SettingsPath(s))), &settings); err != nil {
		t.Fatal(err)
	}
	if settings["env"].(map[string]any)["A"] != "1" {
		t.Fatalf("env was lost: %v", settings)
	}
	hooks := settings["hooks"].(map[string]any)
	if _, ok := hooks["PreToolUse"]; !ok {
		t.Fatalf("PreToolUse hook was lost: %v", hooks)
	}
	if len(hooks["SessionStart"].([]any)) != 1 {
		t.Fatalf("SessionStart = %v, want one entry", hooks["SessionStart"])
	}
	if !strings.Contains(readFile(t, SettingsPath(s)), "/usr/local/bin/ccfg update --quiet") {
		t.Fatalf("hook command missing:\n%s", readFile(t, SettingsPath(s)))
	}
	installed, _ := HookInstalled(s)
	if !installed {
		t.Fatalf("HookInstalled = false after install")
	}
}

func TestRemoveHookLeavesNoEmptyContainers(t *testing.T) {
	s := globalScopeAt(t)
	if _, err := InstallHook(s, "ccfg"); err != nil {
		t.Fatal(err)
	}

	removed, err := RemoveHook(s)
	if err != nil || !removed {
		t.Fatalf("removed=%v err=%v, want true nil", removed, err)
	}

	if got := strings.TrimSpace(readFile(t, SettingsPath(s))); got != "{}" {
		t.Fatalf("settings = %q, want {}", got)
	}
	again, _ := RemoveHook(s)
	if again {
		t.Fatalf("second remove reported a removal")
	}
}

func TestInstallHookCreatesSettingsWhenMissing(t *testing.T) {
	s := globalScopeAt(t)

	if _, err := InstallHook(s, "ccfg"); err != nil {
		t.Fatal(err)
	}

	if _, err := os.Stat(SettingsPath(s)); err != nil {
		t.Fatalf("settings.json not created: %v", err)
	}
}
