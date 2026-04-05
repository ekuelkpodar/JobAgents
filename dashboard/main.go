// JobAgent TUI — Bubble Tea + Lipgloss dashboard
// Reads from ../jobs.db via SQLite and calls the Flask API for actions.
// Color theme: Catppuccin Mocha
//
// Usage:
//   cd dashboard && go run .
//   go build -o jobagent-tui && ./jobagent-tui
//
// Requires Go 1.21+ and CGO (for go-sqlite3): brew install go

package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/bubbles/table"
	"github.com/charmbracelet/lipgloss"
	_ "github.com/mattn/go-sqlite3"
)

// ── Catppuccin Mocha palette ──────────────────────────────────────────────────
var (
	crust   = lipgloss.Color("#11111b")
	mantle  = lipgloss.Color("#181825")
	base    = lipgloss.Color("#1e1e2e")
	surface0 = lipgloss.Color("#313244")
	surface1 = lipgloss.Color("#45475a")
	overlay0 = lipgloss.Color("#6c7086")
	text     = lipgloss.Color("#cdd6f4")
	subtext1 = lipgloss.Color("#bac2de")
	subtext0 = lipgloss.Color("#a6adc8")
	lavender = lipgloss.Color("#b4befe")
	blue     = lipgloss.Color("#89b4fa")
	sapphire = lipgloss.Color("#74c7ec")
	sky      = lipgloss.Color("#89dceb")
	teal     = lipgloss.Color("#94e2d5")
	green    = lipgloss.Color("#a6e3a1")
	yellow   = lipgloss.Color("#f9e2af")
	peach    = lipgloss.Color("#fab387")
	red      = lipgloss.Color("#f38ba8")
	mauve    = lipgloss.Color("#cba6f7")
)

// ── Job model ─────────────────────────────────────────────────────────────────
type Job struct {
	ID          int
	Title       string
	Source      string
	Grade       string
	Archetype   string
	Status      string
	PublishedAt string
	URL         string
	Description string
	Score       sql.NullInt64
	Gaps        string
}

// ── Tab definitions ───────────────────────────────────────────────────────────
type Tab int

const (
	TabAll Tab = iota
	TabSaved
	TabApplied
	TabAGrade
	TabByArchetype
)

var tabNames = []string{"All", "Saved", "Applied", "A-Grade", "By Archetype"}

// ── Model ─────────────────────────────────────────────────────────────────────
type model struct {
	jobs        []Job
	filtered    []Job
	table       table.Model
	activeTab   Tab
	detail      *Job
	width       int
	height      int
	statusMsg   string
	db          *sql.DB
	apiBase     string
}

// ── Messages ──────────────────────────────────────────────────────────────────
type jobsLoadedMsg []Job
type statusMsg     string
type errMsg        struct{ err error }

// ── Init ──────────────────────────────────────────────────────────────────────
func initialModel(db *sql.DB) model {
	cols := []table.Column{
		{Title: "Title",     Width: 40},
		{Title: "Company",   Width: 18},
		{Title: "Grade",     Width: 7},
		{Title: "Archetype", Width: 22},
		{Title: "Status",    Width: 14},
		{Title: "Date",      Width: 12},
	}
	t := table.New(
		table.WithColumns(cols),
		table.WithFocused(true),
		table.WithHeight(20),
	)
	t.SetStyles(tableStyles())
	return model{
		table:   t,
		apiBase: "http://localhost:5000",
		db:      db,
	}
}

func (m model) Init() tea.Cmd {
	return loadJobs(m.db)
}

// ── Update ────────────────────────────────────────────────────────────────────
func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width  = msg.Width
		m.height = msg.Height
		m.table.SetHeight(m.height - 12)

	case tea.KeyMsg:
		if m.detail != nil {
			// In detail view
			switch msg.String() {
			case "q", "esc", "backspace":
				m.detail = nil
			case "g":
				return m, genCV(m.apiBase, m.detail.ID)
			case "a":
				return m, markApplied(m.apiBase, m.detail.ID, &m)
			}
			return m, nil
		}
		switch msg.String() {
		case "q", "ctrl+c":
			return m, tea.Quit
		case "tab":
			m.activeTab = Tab((int(m.activeTab) + 1) % len(tabNames))
			m.filtered  = filterJobs(m.jobs, m.activeTab)
			m.table.SetRows(toRows(m.filtered))
			m.table.GotoTop()
		case "shift+tab":
			m.activeTab = Tab((int(m.activeTab) - 1 + len(tabNames)) % len(tabNames))
			m.filtered  = filterJobs(m.jobs, m.activeTab)
			m.table.SetRows(toRows(m.filtered))
			m.table.GotoTop()
		case "enter":
			if len(m.filtered) > 0 {
				idx := m.table.Cursor()
				if idx < len(m.filtered) {
					m.detail = &m.filtered[idx]
				}
			}
		case "g":
			if len(m.filtered) > 0 {
				idx := m.table.Cursor()
				if idx < len(m.filtered) {
					return m, genCV(m.apiBase, m.filtered[idx].ID)
				}
			}
		case "a":
			if len(m.filtered) > 0 {
				idx := m.table.Cursor()
				if idx < len(m.filtered) {
					return m, markApplied(m.apiBase, m.filtered[idx].ID, &m)
				}
			}
		case "r":
			return m, loadJobs(m.db)
		}

	case jobsLoadedMsg:
		m.jobs     = []Job(msg)
		m.filtered = filterJobs(m.jobs, m.activeTab)
		m.table.SetRows(toRows(m.filtered))

	case statusMsg:
		m.statusMsg = string(msg)
		return m, tea.Tick(3*time.Second, func(t time.Time) tea.Msg {
			return statusMsg("")
		})

	case errMsg:
		m.statusMsg = "Error: " + msg.err.Error()
	}

	var cmd tea.Cmd
	m.table, cmd = m.table.Update(msg)
	return m, cmd
}

// ── View ──────────────────────────────────────────────────────────────────────
func (m model) View() string {
	if m.detail != nil {
		return m.detailView()
	}
	return m.listView()
}

func (m model) listView() string {
	// Title bar
	title := lipgloss.NewStyle().
		Foreground(lavender).Bold(true).
		Padding(0, 1).
		Render("JobAgent TUI")

	// Tabs
	tabs := ""
	for i, name := range tabNames {
		style := lipgloss.NewStyle().Padding(0, 2).Foreground(subtext0)
		if Tab(i) == m.activeTab {
			style = style.Background(surface1).Foreground(text).Bold(true)
		}
		tabs += style.Render(name)
	}
	tabBar := lipgloss.NewStyle().Background(mantle).Render(tabs)

	// Stats
	ag := 0; for _, j := range m.jobs { if j.Grade == "A" { ag++ } }
	applied := 0; for _, j := range m.jobs { if j.Status == "applied" { applied++ } }
	stats := lipgloss.NewStyle().Foreground(subtext0).Padding(0,1).
		Render(fmt.Sprintf("Total: %d  |  Grade A: %d  |  Applied: %d  |  Showing: %d",
			len(m.jobs), ag, applied, len(m.filtered)))

	// Table
	tbl := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(surface1).
		Render(m.table.View())

	// Status/help bar
	helpTxt := "↑↓ navigate  ·  Tab switch tab  ·  Enter details  ·  g gen CV  ·  a applied  ·  r refresh  ·  q quit"
	if m.statusMsg != "" {
		helpTxt = m.statusMsg
	}
	help := lipgloss.NewStyle().Foreground(overlay0).Padding(0,1).Render(helpTxt)

	return lipgloss.JoinVertical(lipgloss.Left,
		lipgloss.JoinHorizontal(lipgloss.Top, title, "  ", tabBar),
		stats,
		tbl,
		help,
	)
}

func (m model) detailView() string {
	j := m.detail
	gradeColor := text
	switch j.Grade {
	case "A": gradeColor = green
	case "B": gradeColor = blue
	case "C": gradeColor = yellow
	case "D": gradeColor = peach
	case "F": gradeColor = red
	}

	var gaps []string
	if j.Gaps != "" {
		_ = json.Unmarshal([]byte(j.Gaps), &gaps)
	}

	box := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lavender).
		Padding(1, 2).
		Width(m.width - 4)

	grade := lipgloss.NewStyle().Foreground(gradeColor).Bold(true).Render(
		fmt.Sprintf("Grade: %s  Score: %s", j.Grade, nullIntStr(j.Score)))

	content := lipgloss.JoinVertical(lipgloss.Left,
		lipgloss.NewStyle().Bold(true).Foreground(lavender).Render(j.Title),
		lipgloss.NewStyle().Foreground(sapphire).Render("  "+j.Source+" · "+j.Archetype),
		"",
		grade,
		lipgloss.NewStyle().Foreground(subtext1).Render("Status: "+j.Status),
		lipgloss.NewStyle().Foreground(subtext0).Render("URL: "+j.URL),
		"",
		lipgloss.NewStyle().Foreground(text).Render(truncate(j.Description, 400)),
		"",
	)

	if len(gaps) > 0 {
		content += "\n" + lipgloss.NewStyle().Foreground(yellow).Bold(true).Render("Gaps:") +
			"\n  " + strings.Join(gaps, "\n  ")
	}

	help := lipgloss.NewStyle().Foreground(overlay0).Render(
		"g generate CV  ·  a mark applied  ·  Esc back")

	return box.Render(content) + "\n" + help
}

// ── Commands ──────────────────────────────────────────────────────────────────
func loadJobs(db *sql.DB) tea.Cmd {
	return func() tea.Msg {
		rows, err := db.Query(`
			SELECT id, COALESCE(title,''), COALESCE(source,''), COALESCE(grade,''),
			       COALESCE(archetype,''), COALESCE(status,'new'),
			       COALESCE(published_date,''), COALESCE(url,''),
			       COALESCE(description,''), score, COALESCE(gaps,'')
			FROM jobs ORDER BY published_date DESC LIMIT 500`)
		if err != nil {
			return errMsg{err}
		}
		defer rows.Close()
		var jobs []Job
		for rows.Next() {
			var j Job
			_ = rows.Scan(&j.ID, &j.Title, &j.Source, &j.Grade, &j.Archetype,
				&j.Status, &j.PublishedAt, &j.URL, &j.Description, &j.Score, &j.Gaps)
			jobs = append(jobs, j)
		}
		return jobsLoadedMsg(jobs)
	}
}

func genCV(apiBase string, jobID int) tea.Cmd {
	return func() tea.Msg {
		resp, err := http.Post(fmt.Sprintf("%s/api/generate-cv/%d", apiBase, jobID), "application/json", nil)
		if err != nil {
			return statusMsg("CV generation failed: " + err.Error())
		}
		defer resp.Body.Close()
		return statusMsg(fmt.Sprintf("CV generated for job %d — check output/", jobID))
	}
}

func markApplied(apiBase string, jobID int, _ *model) tea.Cmd {
	return func() tea.Msg {
		body := strings.NewReader(`{"status":"applied"}`)
		req, _ := http.NewRequest("PATCH", fmt.Sprintf("%s/api/jobs/%d/status", apiBase, jobID), body)
		req.Header.Set("Content-Type", "application/json")
		client := &http.Client{Timeout: 5 * time.Second}
		_, err := client.Do(req)
		if err != nil {
			return statusMsg("Status update failed: " + err.Error())
		}
		return statusMsg(fmt.Sprintf("Job %d marked as Applied", jobID))
	}
}

// ── Helpers ───────────────────────────────────────────────────────────────────
func filterJobs(jobs []Job, tab Tab) []Job {
	var out []Job
	for _, j := range jobs {
		switch tab {
		case TabAll:       out = append(out, j)
		case TabSaved:     if j.Status == "saved"   { out = append(out, j) }
		case TabApplied:   if j.Status == "applied"  { out = append(out, j) }
		case TabAGrade:    if j.Grade == "A"          { out = append(out, j) }
		case TabByArchetype: if j.Archetype != ""    { out = append(out, j) }
		}
	}
	return out
}

func toRows(jobs []Job) []table.Row {
	rows := make([]table.Row, len(jobs))
	for i, j := range jobs {
		date := j.PublishedAt
		if len(date) > 10 { date = date[:10] }
		rows[i] = table.Row{
			truncate(j.Title, 38),
			truncate(j.Source, 16),
			gradeStr(j),
			truncate(j.Archetype, 20),
			j.Status,
			date,
		}
	}
	return rows
}

func gradeStr(j Job) string {
	if j.Grade == "" { return "—" }
	if j.Score.Valid { return fmt.Sprintf("%s (%d)", j.Grade, j.Score.Int64) }
	return j.Grade
}

func truncate(s string, n int) string {
	if len(s) <= n { return s }
	return s[:n-1] + "…"
}

func nullIntStr(n sql.NullInt64) string {
	if n.Valid { return fmt.Sprintf("%d", n.Int64) }
	return "—"
}

func tableStyles() table.Styles {
	s := table.DefaultStyles()
	s.Header = s.Header.
		BorderStyle(lipgloss.NormalBorder()).
		BorderForeground(surface0).
		BorderBottom(true).
		Bold(true).
		Foreground(lavender)
	s.Selected = s.Selected.
		Foreground(text).
		Background(surface1).
		Bold(false)
	return s
}

// ── Main ──────────────────────────────────────────────────────────────────────
func main() {
	dbPath := "../jobs.db"
	if _, err := os.Stat(dbPath); os.IsNotExist(err) {
		fmt.Fprintln(os.Stderr, "jobs.db not found at ../jobs.db. Run fetch_jobs.py first.")
		os.Exit(1)
	}
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "DB error:", err)
		os.Exit(1)
	}
	defer db.Close()

	p := tea.NewProgram(initialModel(db), tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintln(os.Stderr, "Error:", err)
		os.Exit(1)
	}
}
