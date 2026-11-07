package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"github.com/charmbracelet/huh"
	"github.com/spf13/cobra"

	"github.com/dreamyang-liu/claude-config/internal/ccfg"
)

// setupPlan is what the wizard collected. apply turns it into operations.
type setupPlan struct {
	repo          *ccfg.Repo
	installCommon bool
	project       *ccfg.Scope
	profiles      []string // non-common profiles the project should have
	skills        []string // extra skills for the project
	conflicts     []string // skills whose place a real directory takes
	options       ccfg.Options
	gitignore     bool
	pathLink      string // where to link the binary, "" for none
}

func setupCmd(f *flags) *cobra.Command {
	var accessible bool
	cmd := &cobra.Command{
		Use:   "setup",
		Short: "Configure the global scope and one project interactively",
		Long: `Setup walks through the choices in order: the repository, the common layer
in ~/.claude, a project directory and its profiles and extra skills, the
project's .gitignore, and a link that puts ccfg on your PATH. Nothing changes
until you confirm the summary at the end.`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			err := runSetup(f, cmd.OutOrStdout(), accessible)
			if errors.Is(err, huh.ErrUserAborted) {
				fmt.Fprintln(cmd.OutOrStdout(), styDim.Render("setup cancelled; nothing changed"))
				return nil
			}
			return err
		},
	}
	cmd.Flags().BoolVar(&accessible, "accessible", false, "plain prompts that work in any terminal or with a screen reader")
	return cmd
}

func runSetup(f *flags, w io.Writer, accessible bool) error {
	form := func(fields ...huh.Field) error {
		return huh.NewForm(huh.NewGroup(fields...)).WithAccessible(accessible).Run()
	}
	plan := &setupPlan{}

	repo, err := askRepo(f, form)
	if err != nil {
		return err
	}
	plan.repo = repo

	if err := askGlobal(plan, form); err != nil {
		return err
	}
	if err := askProject(plan, f, form); err != nil {
		return err
	}
	if err := askPath(plan, form); err != nil {
		return err
	}

	printPlan(w, plan)
	apply := true
	if err := form(huh.NewConfirm().Title("Apply these changes?").Affirmative("Apply").Negative("Cancel").Value(&apply)); err != nil {
		return err
	}
	if !apply {
		fmt.Fprintln(w, styDim.Render("nothing changed"))
		return nil
	}
	return applyPlan(w, plan)
}

type formFunc func(fields ...huh.Field) error

func askRepo(f *flags, form formFunc) (*ccfg.Repo, error) {
	repo, err := f.load()
	if err == nil {
		return repo, nil
	}
	path := ""
	validate := func(s string) error {
		_, err := ccfg.LoadRepo(expandHome(s))
		return err
	}
	if err := form(huh.NewInput().
		Title("Where is the claude-config repository?").
		Description("No repository was found automatically. Enter the path of the clone.").
		Placeholder("~/Projects/claude-config").
		Validate(validate).
		Value(&path)); err != nil {
		return nil, err
	}
	return ccfg.LoadRepo(expandHome(path))
}

func askGlobal(plan *setupPlan, form formFunc) error {
	g, err := ccfg.GlobalScope()
	if err != nil {
		return err
	}
	st, err := plan.repo.Status(g)
	if err != nil {
		return err
	}
	desc := "Links the common skills into ~/.claude/skills and imports the repository CLAUDE.md."
	for _, ps := range st.Profiles {
		if ps.Profile.Name == ccfg.CommonProfile && ps.State() == "installed" {
			desc = "Already installed. Yes keeps it and repairs anything missing."
		}
	}
	if st.ClaudeMDIsLink {
		desc += " The current ~/.claude/CLAUDE.md symlink becomes a regular file with an import block."
	}
	plan.installCommon = true
	return form(huh.NewConfirm().
		Title("Install the common layer globally (" + g.String() + ")?").
		Description(desc).
		Value(&plan.installCommon))
}

func askProject(plan *setupPlan, f *flags, form formFunc) error {
	want := true
	dir := f.project
	if dir == "" {
		dir, _ = os.Getwd()
	}
	home, _ := os.UserHomeDir()
	dirText := tildify(home, dir)
	if err := form(
		huh.NewConfirm().Title("Configure a project too?").Value(&want),
		huh.NewInput().Title("Project directory").Value(&dirText).
			Validate(func(s string) error {
				if _, err := os.Stat(expandHome(s)); err != nil {
					return fmt.Errorf("%s does not exist", s)
				}
				return nil
			}),
	); err != nil {
		return err
	}
	if !want {
		return nil
	}
	s, err := ccfg.ProjectScope(expandHome(dirText))
	if err != nil {
		return err
	}
	plan.project = &s
	st, err := plan.repo.Status(s)
	if err != nil {
		return err
	}

	var profileOpts []huh.Option[string]
	for _, ps := range st.Profiles {
		if ps.Profile.Name == ccfg.CommonProfile {
			continue
		}
		label := fmt.Sprintf("%-14s %d skills", ps.Profile.Name, ps.Total)
		if ps.State() != "" {
			label += "  (" + ps.State() + ")"
		}
		profileOpts = append(profileOpts, huh.NewOption(label, ps.Profile.Name).Selected(ps.State() != ""))
	}
	if err := form(huh.NewMultiSelect[string]().
		Title("Profiles for " + s.String()).
		Description("Space toggles. Profiles you unselect are removed from the project.").
		Options(profileOpts...).
		Value(&plan.profiles)); err != nil {
		return err
	}

	if skillOpts := extraSkillOptions(plan, st); len(skillOpts) > 0 {
		if err := form(huh.NewMultiSelect[string]().
			Title("Extra skills for the project").
			Description("Skills outside the selected profiles. Already linked ones are preselected.").
			Options(skillOpts...).
			Filterable(true).
			Height(12).
			Value(&plan.skills)); err != nil {
			return err
		}
	}
	return askConflicts(plan, form)
}

// askConflicts asks what to do with a real directory that sits where a link
// must go, for example a skill that was copied into the project by hand.
func askConflicts(plan *setupPlan, form formFunc) error {
	names := append(append([]string{}, plan.profiles...), plan.skills...)
	conflicts, err := plan.repo.Conflicts(*plan.project, names)
	if err != nil {
		return err
	}
	plan.conflicts = conflicts
	if len(conflicts) == 0 {
		return nil
	}
	choice := "force"
	if err := form(huh.NewSelect[string]().
		Title("Real directories already exist for: "+strings.Join(conflicts, ", ")).
		Description("They are copies, not links. ccfg can replace them with links or leave them alone.").
		Options(
			huh.NewOption("Replace with links; move the originals to "+plan.project.Rel(plan.project.BackupDir), "force"),
			huh.NewOption("Keep the directories; link only the other skills", "keep"),
		).
		Value(&choice)); err != nil {
		return err
	}
	plan.options = ccfg.Options{Force: choice == "force", Keep: choice == "keep"}
	return nil
}

// extraSkillOptions lists the skills that the selected profiles do not cover.
func extraSkillOptions(plan *setupPlan, st *ccfg.ScopeStatus) []huh.Option[string] {
	covered := map[string]bool{}
	for _, name := range plan.profiles {
		if p, ok := plan.repo.Profile(name); ok {
			for _, sk := range p.Skills {
				covered[sk.Path] = true
			}
		}
	}
	linked := map[string]bool{}
	for _, l := range st.Links {
		linked[l.Target] = true
	}
	var opts []huh.Option[string]
	seen := map[string]bool{}
	for path, group := range plan.repo.SkillsByPath() {
		sk := group[0]
		if covered[path] || seen[sk.Name] {
			continue
		}
		seen[sk.Name] = true
		opts = append(opts, huh.NewOption(fmt.Sprintf("%-26s from %s", sk.Name, sk.Profile), sk.Name).Selected(linked[path]))
	}
	sort.Slice(opts, func(i, j int) bool { return opts[i].Key < opts[j].Key })
	return opts
}

func askPath(plan *setupPlan, form formFunc) error {
	if plan.project != nil && isDir(filepath.Join(plan.project.Dir, ".git")) && !gitignoreHasSkills(plan.project.Dir) {
		plan.gitignore = true
		if err := form(huh.NewConfirm().
			Title("Add .claude/skills/ to the project's .gitignore?").
			Description("The links hold paths that exist only on this machine.").
			Value(&plan.gitignore)); err != nil {
			return err
		}
	}
	if _, err := exec.LookPath("ccfg"); err == nil {
		return nil
	}
	target := pathLinkTarget()
	if target == "" {
		return nil
	}
	want := true
	if err := form(huh.NewConfirm().
		Title("Link ccfg into " + target + " so it is on your PATH?").
		Value(&want)); err != nil {
		return err
	}
	if want {
		plan.pathLink = target
	}
	return nil
}

// pathLinkTarget picks a writable directory on PATH for the ccfg link.
func pathLinkTarget() string {
	home, _ := os.UserHomeDir()
	candidates := []string{"/opt/homebrew/bin", "/usr/local/bin", filepath.Join(home, ".local", "bin"), filepath.Join(home, "bin")}
	onPath := map[string]bool{}
	for _, d := range filepath.SplitList(os.Getenv("PATH")) {
		onPath[filepath.Clean(d)] = true
	}
	for _, c := range candidates {
		if onPath[c] && writable(c) {
			return filepath.Join(c, "ccfg")
		}
	}
	return ""
}

func writable(dir string) bool {
	probe, err := os.CreateTemp(dir, ".ccfg-*")
	if err != nil {
		return false
	}
	probe.Close()
	os.Remove(probe.Name())
	return true
}

func printPlan(w io.Writer, plan *setupPlan) {
	fmt.Fprintln(w)
	title(w, "Plan")
	home, _ := os.UserHomeDir()
	fmt.Fprintf(w, "  repository   %s\n", styDim.Render(tildify(home, plan.repo.Root)))
	if plan.installCommon {
		fmt.Fprintf(w, "  global       install %s\n", styAccent.Render(ccfg.CommonProfile))
	} else {
		fmt.Fprintf(w, "  global       %s\n", styDim.Render("unchanged"))
	}
	if plan.project != nil {
		names := "none"
		if len(plan.profiles) > 0 {
			names = strings.Join(plan.profiles, ", ")
		}
		fmt.Fprintf(w, "  project      %s\n", styDim.Render(plan.project.String()))
		fmt.Fprintf(w, "    profiles   %s %s\n", styAccent.Render(names), styDim.Render("(others are removed)"))
		if len(plan.skills) > 0 {
			fmt.Fprintf(w, "    skills     %s\n", styAccent.Render(strings.Join(plan.skills, ", ")))
		}
		if len(plan.conflicts) > 0 {
			what := "keep the existing directories, link the rest"
			if plan.options.Force {
				what = "move the existing directories to " + plan.project.Rel(plan.project.BackupDir) + ", then link"
			}
			fmt.Fprintf(w, "    existing   %s %s\n", styWarn.Render(strings.Join(plan.conflicts, ", ")), styDim.Render(what))
		}
		if plan.gitignore {
			fmt.Fprintf(w, "    .gitignore add .claude/skills/\n")
		}
	}
	if plan.pathLink != "" {
		fmt.Fprintf(w, "  PATH         link %s\n", styDim.Render(plan.pathLink))
	}
	fmt.Fprintln(w)
}

func applyPlan(w io.Writer, plan *setupPlan) error {
	if plan.installCommon {
		g, err := ccfg.GlobalScope()
		if err != nil {
			return err
		}
		title(w, "global")
		events, err := plan.repo.Install(g, []string{ccfg.CommonProfile}, ccfg.Options{})
		printEvents(w, events)
		if err != nil {
			return err
		}
	}
	if plan.project != nil {
		if err := applyProject(w, plan); err != nil {
			return err
		}
	}
	if plan.pathLink != "" {
		if err := linkBinary(plan.pathLink); err != nil {
			fmt.Fprintf(w, "%s PATH link failed: %v\n", icon(ccfg.Warn), err)
		} else {
			fmt.Fprintf(w, "%s linked %s\n", icon(ccfg.OK), styAccent.Render(plan.pathLink))
		}
	}
	fmt.Fprintln(w)
	fmt.Fprintln(w, styDim.Render("done. `ccfg status` shows the result; a new Claude Code session reads the new CLAUDE.md."))
	return nil
}

func applyProject(w io.Writer, plan *setupPlan) error {
	s := *plan.project
	title(w, s.String())
	st, err := plan.repo.Status(s)
	if err != nil {
		return err
	}
	selected := map[string]bool{}
	for _, n := range plan.profiles {
		selected[n] = true
	}
	for _, ps := range st.Installed() {
		name := ps.Profile.Name
		if name == ccfg.CommonProfile || selected[name] {
			continue
		}
		events, err := plan.repo.Uninstall(s, []string{name}, false)
		printEvents(w, events)
		if err != nil {
			return err
		}
	}
	// The .gitignore line goes first, so that Install does not print its hint.
	if plan.gitignore {
		if err := appendGitignore(s.Dir); err != nil {
			return err
		}
		fmt.Fprintf(w, "%s added %s\n", icon(ccfg.OK), styAccent.Render(".claude/skills/ to .gitignore"))
	}
	names := append(append([]string{}, plan.profiles...), plan.skills...)
	if len(names) > 0 {
		events, err := plan.repo.Install(s, names, plan.options)
		printEvents(w, events)
		if err != nil {
			return err
		}
	}
	return nil
}

func gitignoreHasSkills(dir string) bool {
	data, _ := os.ReadFile(filepath.Join(dir, ".gitignore"))
	for _, l := range strings.Split(string(data), "\n") {
		t := strings.Trim(strings.TrimSpace(l), "/")
		if t == ".claude/skills" || t == ".claude" {
			return true
		}
	}
	return false
}

func appendGitignore(dir string) error {
	path := filepath.Join(dir, ".gitignore")
	data, _ := os.ReadFile(path)
	content := string(data)
	if content != "" && !strings.HasSuffix(content, "\n") {
		content += "\n"
	}
	content += ".claude/skills/\n"
	return os.WriteFile(path, []byte(content), 0o644)
}

func linkBinary(target string) error {
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	real, err := filepath.EvalSymlinks(exe)
	if err != nil {
		return err
	}
	if fi, err := os.Lstat(target); err == nil {
		if fi.Mode()&os.ModeSymlink == 0 {
			return fmt.Errorf("%s exists and is not a symlink", target)
		}
		if err := os.Remove(target); err != nil {
			return err
		}
	}
	return os.Symlink(real, target)
}

func expandHome(p string) string {
	home, _ := os.UserHomeDir()
	if p == "~" {
		return home
	}
	if strings.HasPrefix(p, "~/") {
		return filepath.Join(home, p[2:])
	}
	return p
}

func isDir(path string) bool {
	fi, err := os.Stat(path)
	return err == nil && fi.IsDir()
}
