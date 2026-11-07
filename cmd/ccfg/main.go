// ccfg installs, removes and inspects the skills and CLAUDE.md fragments of a
// claude-config repository in the global ~/.claude scope or in one project.
package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"sort"
	"time"

	"github.com/charmbracelet/huh"
	"github.com/spf13/cobra"

	"github.com/dreamyang-liu/claude-config/internal/ccfg"
)

var version = "dev"

type flags struct {
	repo    string
	global  bool
	project string
	force   bool
	keep    bool
	noSync  bool
}

// syncTimeout bounds the fetch that runs before install, switch and setup, so
// that an offline machine waits a few seconds and then continues.
const syncTimeout = 8 * time.Second

// autoSync fast-forwards the clone before an operation, unless --no-sync is
// set. It prints only changes and warnings. When the clone moved, it reloads
// the repository so that new skills and profiles are seen.
func autoSync(f *flags, r *ccfg.Repo, w io.Writer) *ccfg.Repo {
	if f.noSync {
		return r
	}
	events, err := r.Update(syncTimeout)
	if errors.Is(err, ccfg.ErrNotGit) {
		return r
	}
	if err != nil {
		fmt.Fprintf(w, "%s sync: %v\n", icon(ccfg.Warn), err)
		return r
	}
	printEvents(w, withoutInfo(events))
	for _, e := range events {
		if e.Verb == "updated" {
			if fresh, err := ccfg.LoadRepo(r.Root); err == nil {
				return fresh
			}
		}
	}
	return r
}

func withoutInfo(events []ccfg.Event) []ccfg.Event {
	var out []ccfg.Event
	for _, e := range events {
		if e.Level != ccfg.Info {
			out = append(out, e)
		}
	}
	return out
}

func (f *flags) options() ccfg.Options {
	return ccfg.Options{Force: f.force, Keep: f.keep}
}

func addConflictFlags(cmd *cobra.Command, f *flags) {
	cmd.Flags().BoolVar(&f.force, "force", false, "move a real file or directory aside (into the scope's backups) when a link needs its place")
	cmd.Flags().BoolVar(&f.keep, "keep", false, "leave a real file or directory in place and skip that skill")
	cmd.MarkFlagsMutuallyExclusive("force", "keep")
}

func main() {
	f := &flags{}
	root := &cobra.Command{
		Use:   "ccfg",
		Short: "Manage Claude Code skills and CLAUDE.md profiles from a claude-config repository",
		Long: `ccfg links the skills of a claude-config repository into a scope and keeps a
block of @import lines in that scope's CLAUDE.md.

A scope is the global ~/.claude directory (--global) or one project
(--project DIR, default: the current directory).

A profile is a CLAUDE.md fragment plus skills: "common" is the repository
root (always wanted globally), and each directory under profiles/ is one
project type. A skill can also be installed on its own.

New here? Run "ccfg setup" for a guided walk-through.`,
		SilenceUsage:  true,
		SilenceErrors: true,
	}
	root.PersistentFlags().StringVar(&f.repo, "repo", "", "path of the claude-config repository (default: $CLAUDE_CONFIG_REPO, ~/.config/ccfg/repo, the binary's repo, ~/Projects/claude-config)")
	root.PersistentFlags().BoolVarP(&f.global, "global", "g", false, "use the global scope ~/.claude")
	root.PersistentFlags().StringVarP(&f.project, "project", "p", "", "use the project at DIR (default: current directory)")
	root.PersistentFlags().BoolVar(&f.noSync, "no-sync", false, "do not pull the repository before install, switch or setup")

	root.Version = version
	root.AddCommand(setupCmd(f), statusCmd(f), listCmd(f), installCmd(f), uninstallCmd(f), switchCmd(f),
		updateCmd(f), hookCmd(f), doctorCmd(f))
	styleHelp(root)

	if err := root.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "%s %s\n", icon(ccfg.Fail), err)
		os.Exit(1)
	}
}

func (f *flags) load() (*ccfg.Repo, error) {
	return ccfg.FindRepo(f.repo)
}

// scope returns the one scope that the flags select. Without -g or -p it is
// the project at the current directory.
func (f *flags) scope() (ccfg.Scope, error) {
	if f.global && f.project != "" {
		return ccfg.Scope{}, errors.New("use --global or --project, not both")
	}
	if f.global {
		return ccfg.GlobalScope()
	}
	if f.project != "" {
		return ccfg.ProjectScope(f.project)
	}
	return ccfg.ProjectScope(".")
}

// scopes returns the scopes to report on. Without -g or -p it is both the
// global scope and the project at the current directory.
func (f *flags) scopes() ([]ccfg.Scope, error) {
	if f.global || f.project != "" {
		s, err := f.scope()
		return []ccfg.Scope{s}, err
	}
	g, err := ccfg.GlobalScope()
	if err != nil {
		return nil, err
	}
	p, err := ccfg.ProjectScope(".")
	if err != nil {
		return nil, err
	}
	return []ccfg.Scope{g, p}, nil
}

func statusCmd(f *flags) *cobra.Command {
	return &cobra.Command{
		Use:   "status",
		Short: "Show which profiles and skills each scope has",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			r, err := f.load()
			if err != nil {
				return err
			}
			scopes, err := f.scopes()
			if err != nil {
				return err
			}
			printRepoLine(cmd.OutOrStdout(), r, !f.noSync)
			for _, s := range scopes {
				st, err := r.Status(s)
				if err != nil {
					return err
				}
				printStatus(cmd.OutOrStdout(), st)
			}
			return nil
		},
	}
}

func updateCmd(f *flags) *cobra.Command {
	var self, quiet bool
	cmd := &cobra.Command{
		Use:   "update",
		Short: "Pull the repository from origin; with --self, also replace the ccfg binary",
		Long: `Update fetches origin and fast-forwards the clone when the working tree is
clean. Local changes or a diverged branch are reported, never overwritten.
Because the scopes hold links into the clone, a pull updates every scope.

With --self, it downloads the latest release for this platform, verifies the
checksum and replaces the running binary.

--quiet prints only changes and warnings; a SessionStart hook uses it.`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			w := cmd.OutOrStdout()
			r, err := f.load()
			if err != nil {
				return err
			}
			events, err := r.Update(60 * time.Second)
			if errors.Is(err, ccfg.ErrNotGit) {
				events = append(events, ccfg.Event{Level: ccfg.Warn, Verb: "skipped", Subject: "repository", Detail: r.Root + " is not a git clone"})
				err = nil
			}
			if quiet {
				events = withoutInfo(events)
			}
			printEvents(w, events)
			if err != nil {
				return err
			}
			if !self {
				return nil
			}
			got, changed, err := ccfg.SelfUpdate(version, "")
			if err != nil {
				return fmt.Errorf("self-update: %w", err)
			}
			if changed {
				fmt.Fprintf(w, "%s updated  %s  %s\n", icon(ccfg.OK), styAccent.Render("ccfg"), styDim.Render(version+" -> "+got))
			} else if !quiet {
				fmt.Fprintf(w, "%s current  %s  %s\n", icon(ccfg.Info), styAccent.Render("ccfg"), styDim.Render(got))
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&self, "self", false, "also update the ccfg binary to the latest release")
	cmd.Flags().BoolVar(&quiet, "quiet", false, "print only changes and warnings")
	return cmd
}

func hookCmd(f *flags) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "hook",
		Short: "Manage the Claude Code SessionStart hook that syncs the repository",
		Long: `The hook adds "ccfg update --quiet" to hooks.SessionStart in ~/.claude/settings.json.
Each new Claude Code session then starts with the clone fast-forwarded to origin.
Other settings and hooks are kept.`,
	}
	run := func(action string) func(*cobra.Command, []string) error {
		return func(cmd *cobra.Command, _ []string) error {
			g, err := ccfg.GlobalScope()
			if err != nil {
				return err
			}
			w := cmd.OutOrStdout()
			switch action {
			case "install":
				exe, _ := os.Executable()
				added, err := ccfg.InstallHook(g, exe)
				if err != nil {
					return err
				}
				if added {
					fmt.Fprintf(w, "%s added SessionStart hook to %s\n", icon(ccfg.OK), styDim.Render(ccfg.SettingsPath(g)))
				} else {
					fmt.Fprintf(w, "%s hook already present in %s\n", icon(ccfg.Info), styDim.Render(ccfg.SettingsPath(g)))
				}
			case "remove":
				removed, err := ccfg.RemoveHook(g)
				if err != nil {
					return err
				}
				if removed {
					fmt.Fprintf(w, "%s removed the hook from %s\n", icon(ccfg.OK), styDim.Render(ccfg.SettingsPath(g)))
				} else {
					fmt.Fprintf(w, "%s no ccfg hook in %s\n", icon(ccfg.Info), styDim.Render(ccfg.SettingsPath(g)))
				}
			default:
				installed, err := ccfg.HookInstalled(g)
				if err != nil {
					return err
				}
				if installed {
					fmt.Fprintf(w, "%s SessionStart hook installed %s\n", icon(ccfg.OK), styDim.Render(ccfg.SettingsPath(g)))
				} else {
					fmt.Fprintf(w, "%s no hook; run `ccfg hook install`\n", icon(ccfg.Info))
				}
			}
			return nil
		}
	}
	cmd.AddCommand(
		&cobra.Command{Use: "install", Short: "Add the hook", Args: cobra.NoArgs, RunE: run("install")},
		&cobra.Command{Use: "remove", Short: "Remove the hook", Args: cobra.NoArgs, RunE: run("remove")},
		&cobra.Command{Use: "status", Short: "Show whether the hook is present", Args: cobra.NoArgs, RunE: run("status")},
	)
	return cmd
}

func listCmd(f *flags) *cobra.Command {
	var verbose bool
	cmd := &cobra.Command{
		Use:   "list",
		Short: "List the profiles and skills that the repository offers",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			r, err := f.load()
			if err != nil {
				return err
			}
			printList(cmd.OutOrStdout(), r, verbose)
			return nil
		},
	}
	cmd.Flags().BoolVarP(&verbose, "verbose", "v", false, "show full skill descriptions")
	return cmd
}

func installCmd(f *flags) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "install [profile|skill ...]",
		Short: "Install profiles or skills into a scope",
		Long: `Install links each skill into <scope>/skills and adds the profile's CLAUDE.md
to the ccfg block of <scope>/CLAUDE.md. Without names it asks interactively.

Examples:
  ccfg install common --global
  ccfg install engineering
  ccfg install research -p ~/Projects/my-paper
  ccfg install tdd testing`,
		RunE: func(cmd *cobra.Command, names []string) error {
			r, err := f.load()
			if err != nil {
				return err
			}
			s, err := f.scope()
			if err != nil {
				return err
			}
			r = autoSync(f, r, cmd.OutOrStdout())
			if len(names) == 0 {
				names, err = pickNames(r, s)
				if err != nil || len(names) == 0 {
					return err
				}
			}
			title(cmd.OutOrStdout(), "install into "+s.String())
			events, err := r.Install(s, names, f.options())
			printEvents(cmd.OutOrStdout(), events)
			return err
		},
	}
	addConflictFlags(cmd, f)
	return cmd
}

func uninstallCmd(f *flags) *cobra.Command {
	var all bool
	cmd := &cobra.Command{
		Use:   "uninstall [profile|skill ...]",
		Short: "Remove profiles or skills from a scope",
		Long: `Uninstall removes the profile's import line and the links of its skills. A
skill that another installed profile still uses stays. With --all it removes
every link into the repository and the whole ccfg block.`,
		RunE: func(cmd *cobra.Command, names []string) error {
			if !all && len(names) == 0 {
				return errors.New("name a profile or skill, or pass --all")
			}
			r, err := f.load()
			if err != nil {
				return err
			}
			s, err := f.scope()
			if err != nil {
				return err
			}
			title(cmd.OutOrStdout(), "uninstall from "+s.String())
			events, err := r.Uninstall(s, names, all)
			printEvents(cmd.OutOrStdout(), events)
			return err
		},
	}
	cmd.Flags().BoolVar(&all, "all", false, "remove everything that points into the repository")
	return cmd
}

func switchCmd(f *flags) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "switch [profile]",
		Short: "Make one profile the only profile of a scope (common stays)",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			r, err := f.load()
			if err != nil {
				return err
			}
			s, err := f.scope()
			if err != nil {
				return err
			}
			r = autoSync(f, r, cmd.OutOrStdout())
			name := ""
			if len(args) == 1 {
				name = args[0]
			} else {
				name, err = pickProfile(r)
				if err != nil || name == "" {
					return err
				}
			}
			title(cmd.OutOrStdout(), "switch "+s.String()+" to "+name)
			events, err := r.Switch(s, name, f.options())
			printEvents(cmd.OutOrStdout(), events)
			return err
		},
	}
	addConflictFlags(cmd, f)
	return cmd
}

func doctorCmd(f *flags) *cobra.Command {
	var fix bool
	cmd := &cobra.Command{
		Use:   "doctor",
		Short: "Find broken links, loose imports and a legacy CLAUDE.md symlink",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			r, err := f.load()
			if err != nil {
				return err
			}
			scopes, err := f.scopes()
			if err != nil {
				return err
			}
			for _, s := range scopes {
				title(cmd.OutOrStdout(), s.String())
				events, err := r.Doctor(s, fix)
				printEvents(cmd.OutOrStdout(), events)
				if err != nil {
					return err
				}
				fmt.Fprintln(cmd.OutOrStdout())
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&fix, "fix", false, "repair what doctor finds")
	return cmd
}

// pickNames asks the user which profiles and skills to install.
func pickNames(r *ccfg.Repo, s ccfg.Scope) ([]string, error) {
	st, err := r.Status(s)
	if err != nil {
		return nil, err
	}
	var opts []huh.Option[string]
	for _, ps := range st.Profiles {
		label := fmt.Sprintf("profile  %-14s %d skills", ps.Profile.Name, ps.Total)
		if ps.State() != "" {
			label += "  (" + ps.State() + ")"
		}
		opts = append(opts, huh.NewOption(label, ps.Profile.Name))
	}
	seen := map[string]bool{}
	var skills []*ccfg.Skill
	for _, group := range r.SkillsByPath() {
		sk := group[0]
		if !seen[sk.Name] {
			seen[sk.Name] = true
			skills = append(skills, sk)
		}
	}
	sort.Slice(skills, func(i, j int) bool { return skills[i].Name < skills[j].Name })
	for _, sk := range skills {
		opts = append(opts, huh.NewOption(fmt.Sprintf("skill    %-14s from %s", sk.Name, sk.Profile), sk.Name))
	}
	var picked []string
	err = huh.NewMultiSelect[string]().
		Title("Install into " + s.String()).
		Description("space selects, enter confirms").
		Options(opts...).
		Filterable(true).
		Height(16).
		Value(&picked).
		Run()
	return picked, err
}

// pickProfile asks the user for one non-common profile.
func pickProfile(r *ccfg.Repo) (string, error) {
	var opts []huh.Option[string]
	for _, p := range r.Profiles {
		if p.Name == ccfg.CommonProfile {
			continue
		}
		opts = append(opts, huh.NewOption(fmt.Sprintf("%-14s %d skills", p.Name, len(p.Skills)), p.Name))
	}
	var picked string
	err := huh.NewSelect[string]().Title("Switch to profile").Options(opts...).Value(&picked).Run()
	return picked, err
}
