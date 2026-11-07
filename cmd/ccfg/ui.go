package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/lipgloss/table"
	"github.com/spf13/cobra"

	"github.com/dreamyang-liu/claude-config/internal/ccfg"
)

var (
	styTitle  = lipgloss.NewStyle().Bold(true)
	styDim    = lipgloss.NewStyle().Faint(true)
	styOK     = lipgloss.NewStyle().Foreground(lipgloss.Color("2"))
	styWarn   = lipgloss.NewStyle().Foreground(lipgloss.Color("3"))
	styFail   = lipgloss.NewStyle().Foreground(lipgloss.Color("1"))
	styAccent = lipgloss.NewStyle().Foreground(lipgloss.Color("6"))
	styHeader = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("6"))
	styCell   = lipgloss.NewStyle().PaddingRight(2)
	styBorder = lipgloss.NewStyle().Foreground(lipgloss.Color("8"))
)

func icon(l ccfg.Level) string {
	switch l {
	case ccfg.OK:
		return styOK.Render("✓")
	case ccfg.Warn:
		return styWarn.Render("!")
	case ccfg.Fail:
		return styFail.Render("✗")
	default:
		return styDim.Render("·")
	}
}

func title(w io.Writer, s string) {
	fmt.Fprintln(w, styTitle.Render(s))
}

// printEvents writes one line per event: icon, verb, subject, dim detail.
func printEvents(w io.Writer, events []ccfg.Event) {
	verbWidth, subjectWidth := 0, 0
	for _, e := range events {
		verbWidth = max(verbWidth, len(e.Verb))
		if e.Detail != "" {
			subjectWidth = max(subjectWidth, min(len([]rune(e.Subject)), 40))
		}
	}
	for _, e := range events {
		line := fmt.Sprintf("%s %-*s %s", icon(e.Level), verbWidth, e.Verb, styAccent.Render(e.Subject))
		if e.Detail != "" {
			pad := subjectWidth - len([]rune(e.Subject))
			if pad < 1 {
				pad = 1
			}
			line += strings.Repeat(" ", pad) + " " + styDim.Render(e.Detail)
		}
		fmt.Fprintln(w, line)
	}
}

func newTable(headers ...string) *table.Table {
	return table.New().
		Border(lipgloss.NormalBorder()).
		BorderStyle(styBorder).
		BorderTop(false).BorderBottom(false).BorderLeft(false).BorderRight(false).
		BorderColumn(false).BorderHeader(true).
		StyleFunc(func(row, _ int) lipgloss.Style {
			if row == table.HeaderRow {
				return styHeader.PaddingRight(2)
			}
			return styCell
		}).
		Headers(headers...)
}

// printRepoLine writes one line about the clone: branch, head, and whether it
// matches origin. With fetch set, it fetches first with a short timeout.
func printRepoLine(w io.Writer, r *ccfg.Repo, fetch bool) {
	home, _ := os.UserHomeDir()
	fmt.Fprintf(w, "%s %s", styTitle.Render("repository"), styDim.Render(tildify(home, r.Root)))
	fetched := false
	if fetch {
		fetched = r.Fetch(3*time.Second) == nil
	}
	st, err := r.State()
	switch {
	case errors.Is(err, ccfg.ErrNotGit):
		fmt.Fprintf(w, "  %s\n\n", styDim.Render("(not a git clone)"))
		return
	case err != nil:
		fmt.Fprintf(w, "  %s %v\n\n", icon(ccfg.Warn), err)
		return
	}
	fmt.Fprintf(w, "  %s", styDim.Render(st.Branch+" "+st.Head))
	switch {
	case st.Behind > 0 && st.Ahead > 0:
		fmt.Fprintf(w, "  %s diverged: %d local, %d remote", icon(ccfg.Warn), st.Ahead, st.Behind)
	case st.Behind > 0:
		fmt.Fprintf(w, "  %s behind origin by %d %s", icon(ccfg.Warn), st.Behind, styDim.Render("(ccfg update)"))
	case st.Ahead > 0:
		fmt.Fprintf(w, "  %s ahead of origin by %d", icon(ccfg.Info), st.Ahead)
	case fetched:
		fmt.Fprintf(w, "  %s matches origin", icon(ccfg.OK))
	default:
		fmt.Fprintf(w, "  %s", styDim.Render("matches last fetch (offline)"))
	}
	if st.Dirty {
		fmt.Fprintf(w, "  %s local changes", icon(ccfg.Warn))
	}
	fmt.Fprintln(w)
	fmt.Fprintln(w)
}

// printStatus writes the profile table of one scope and its warnings.
func printStatus(w io.Writer, st *ccfg.ScopeStatus) {
	title(w, st.Scope.String())
	t := newTable("PROFILE", "STATE", "SKILLS", "CLAUDE.md")
	for _, ps := range st.Profiles {
		t.Row(ps.Profile.Name, renderState(ps.State()),
			fmt.Sprintf("%d/%d", ps.Linked, ps.Total), renderBool(ps.Imported))
	}
	fmt.Fprintln(w, t.Render())
	if len(st.Links) > 0 {
		names := make([]string, 0, len(st.Links))
		for _, l := range st.Links {
			names = append(names, l.Name)
		}
		fmt.Fprintf(w, "%s %s\n", styDim.Render("linked skills:"), strings.Join(names, " "))
	}
	for _, l := range st.Broken {
		fmt.Fprintf(w, "%s broken link %s -> %s\n", icon(ccfg.Warn), styAccent.Render(l.Name), styDim.Render(l.Target))
	}
	for _, line := range st.Loose {
		fmt.Fprintf(w, "%s loose import %s %s\n", icon(ccfg.Warn), styAccent.Render(line), styDim.Render("(outside the ccfg block; run `ccfg doctor --fix`)"))
	}
	if st.ClaudeMDIsLink {
		fmt.Fprintf(w, "%s %s is a symlink %s\n", icon(ccfg.Warn), styAccent.Render("CLAUDE.md"), styDim.Render("(legacy install.sh layout; run `ccfg doctor --fix`)"))
	}
	fmt.Fprintln(w)
}

func renderState(s string) string {
	switch s {
	case "installed":
		return styOK.Render("● installed")
	case "partial":
		return styWarn.Render("◐ partial")
	default:
		return styDim.Render("○ -")
	}
}

func renderBool(b bool) string {
	if b {
		return styOK.Render("✓ imported")
	}
	return styDim.Render("-")
}

// printList writes each profile with its skills and their descriptions.
func printList(w io.Writer, r *ccfg.Repo, verbose bool) {
	home, _ := os.UserHomeDir()
	fmt.Fprintf(w, "%s %s\n\n", styTitle.Render("repository"), styDim.Render(tildify(home, r.Root)))
	for _, p := range r.Profiles {
		fmt.Fprintf(w, "%s %s\n", styHeader.Render(p.Name), styDim.Render(fmt.Sprintf("%d skills  %s", len(p.Skills), tildify(home, p.ClaudeMD))))
		if len(p.Skills) == 0 {
			fmt.Fprintf(w, "  %s\n", styDim.Render("(no skills yet)"))
		}
		for _, sk := range p.Skills {
			desc := sk.Description
			if !verbose {
				desc = truncate(desc, 72)
			}
			fmt.Fprintf(w, "  %-28s %s\n", styAccent.Render(sk.Name), styDim.Render(desc))
		}
		fmt.Fprintln(w)
	}
}

// styleHelp colors the section headings and command names of cobra's help.
func styleHelp(root *cobra.Command) {
	cobra.AddTemplateFunc("heading", func(s string) string { return styHeader.Render(s) })
	cobra.AddTemplateFunc("accent", func(s string) string { return styAccent.Render(s) })
	cobra.AddTemplateFunc("dim", func(s string) string { return styDim.Render(s) })
	root.SetUsageTemplate(usageTemplate)
	root.SetErrPrefix(icon(ccfg.Fail))
}

const usageTemplate = `{{heading "Usage:"}}{{if .Runnable}}
  {{accent .UseLine}}{{end}}{{if .HasAvailableSubCommands}}
  {{accent .CommandPath}} {{dim "[command]"}}{{end}}{{if gt (len .Aliases) 0}}

{{heading "Aliases:"}}
  {{.NameAndAliases}}{{end}}{{if .HasExample}}

{{heading "Examples:"}}
{{.Example}}{{end}}{{if .HasAvailableSubCommands}}{{$cmds := .Commands}}{{if eq (len .Groups) 0}}

{{heading "Commands:"}}{{range $cmds}}{{if (or .IsAvailableCommand (eq .Name "help"))}}
  {{accent (rpad .Name .NamePadding)}} {{.Short}}{{end}}{{end}}{{else}}{{range $group := .Groups}}

{{heading $group.Title}}{{range $cmds}}{{if (and (eq .GroupID $group.ID) (or .IsAvailableCommand (eq .Name "help")))}}
  {{accent (rpad .Name .NamePadding)}} {{.Short}}{{end}}{{end}}{{end}}{{if not .AllChildCommandsHaveGroup}}

{{heading "Additional Commands:"}}{{range $cmds}}{{if (and (eq .GroupID "") (or .IsAvailableCommand (eq .Name "help")))}}
  {{accent (rpad .Name .NamePadding)}} {{.Short}}{{end}}{{end}}{{end}}{{end}}{{end}}{{if .HasAvailableLocalFlags}}

{{heading "Flags:"}}
{{.LocalFlags.FlagUsages | trimTrailingWhitespaces}}{{end}}{{if .HasAvailableInheritedFlags}}

{{heading "Global Flags:"}}
{{.InheritedFlags.FlagUsages | trimTrailingWhitespaces}}{{end}}{{if .HasHelpSubCommands}}

{{heading "Additional help topics:"}}{{range .Commands}}{{if .IsAdditionalHelpTopicCommand}}
  {{rpad .CommandPath .CommandPathPadding}} {{.Short}}{{end}}{{end}}{{end}}{{if .HasAvailableSubCommands}}

{{dim (printf "Use \"%s [command] --help\" for more information about a command." .CommandPath)}}{{end}}
`

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n-1]) + "…"
}

func tildify(home, p string) string {
	if home != "" && strings.HasPrefix(p, home+string(os.PathSeparator)) {
		return "~" + p[len(home):]
	}
	return p
}
