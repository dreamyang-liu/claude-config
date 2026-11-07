// ccfg installs, removes and inspects the skills and CLAUDE.md fragments of a
// claude-config repository in the global ~/.claude scope or in one project.
package main

import (
	"errors"
	"fmt"
	"os"
	"sort"

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

	root.Version = version
	root.AddCommand(setupCmd(f), statusCmd(f), listCmd(f), installCmd(f), uninstallCmd(f), switchCmd(f), doctorCmd(f))
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
			if len(names) == 0 {
				names, err = pickNames(r, s)
				if err != nil || len(names) == 0 {
					return err
				}
			}
			title(cmd.OutOrStdout(), "install into "+s.String())
			events, err := r.Install(s, names, ccfg.Options{Force: f.force})
			printEvents(cmd.OutOrStdout(), events)
			return err
		},
	}
	cmd.Flags().BoolVar(&f.force, "force", false, "move a real file or directory aside when a link needs its place")
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
			events, err := r.Switch(s, name, ccfg.Options{Force: f.force})
			printEvents(cmd.OutOrStdout(), events)
			return err
		},
	}
	cmd.Flags().BoolVar(&f.force, "force", false, "move a real file or directory aside when a link needs its place")
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
