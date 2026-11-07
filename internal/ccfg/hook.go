package ccfg

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// hookMarker identifies the hook that ccfg writes, so that it can find and
// remove its own entry and leave the user's other hooks alone.
const hookMarker = "update --quiet"

// SettingsPath is the Claude Code settings file of the global scope.
func SettingsPath(s Scope) string {
	return filepath.Join(s.Dir, "settings.json")
}

// HookInstalled reports whether settings.json has the ccfg SessionStart hook.
func HookInstalled(s Scope) (bool, error) {
	settings, err := readSettings(SettingsPath(s))
	if err != nil {
		return false, err
	}
	_, found := findHook(settings)
	return found, nil
}

// InstallHook adds a SessionStart hook that runs `<ccfg> update --quiet`, so
// that each Claude Code session starts with a fresh clone. It keeps the other
// content of settings.json. It returns false when the hook was already there.
func InstallHook(s Scope, ccfgPath string) (bool, error) {
	path := SettingsPath(s)
	settings, err := readSettings(path)
	if err != nil {
		return false, err
	}
	if _, found := findHook(settings); found {
		return false, nil
	}
	hooks, _ := settings["hooks"].(map[string]any)
	if hooks == nil {
		hooks = map[string]any{}
	}
	list, _ := hooks["SessionStart"].([]any)
	list = append(list, map[string]any{
		"matcher": "startup|resume",
		"hooks": []any{map[string]any{
			"type":    "command",
			"command": ccfgPath + " " + hookMarker,
			"timeout": 30,
		}},
	})
	hooks["SessionStart"] = list
	settings["hooks"] = hooks
	return true, writeSettings(path, settings)
}

// RemoveHook deletes the ccfg hook. It returns false when there was none.
func RemoveHook(s Scope) (bool, error) {
	path := SettingsPath(s)
	settings, err := readSettings(path)
	if err != nil {
		return false, err
	}
	index, found := findHook(settings)
	if !found {
		return false, nil
	}
	hooks := settings["hooks"].(map[string]any)
	list := hooks["SessionStart"].([]any)
	list = append(list[:index], list[index+1:]...)
	if len(list) == 0 {
		delete(hooks, "SessionStart")
	} else {
		hooks["SessionStart"] = list
	}
	if len(hooks) == 0 {
		delete(settings, "hooks")
	}
	return true, writeSettings(path, settings)
}

// findHook returns the index of the ccfg entry in hooks.SessionStart.
func findHook(settings map[string]any) (int, bool) {
	hooks, _ := settings["hooks"].(map[string]any)
	list, _ := hooks["SessionStart"].([]any)
	for i, entry := range list {
		m, _ := entry.(map[string]any)
		inner, _ := m["hooks"].([]any)
		for _, h := range inner {
			hm, _ := h.(map[string]any)
			if cmd, _ := hm["command"].(string); strings.Contains(cmd, "ccfg") && strings.Contains(cmd, hookMarker) {
				return i, true
			}
		}
	}
	return 0, false
}

func readSettings(path string) (map[string]any, error) {
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return map[string]any{}, nil
	}
	if err != nil {
		return nil, err
	}
	var settings map[string]any
	if err := json.Unmarshal(data, &settings); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	if settings == nil {
		settings = map[string]any{}
	}
	return settings, nil
}

func writeSettings(path string, settings map[string]any) error {
	data, err := json.MarshalIndent(settings, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o600)
}
