from __future__ import annotations

import re
from datetime import datetime, timezone
import html as html_lib


def _render_analysis_tab(analysis: str) -> str:
    """Convert the software-engineer markdown analysis to a styled HTML tab."""
    escaped = html_lib.escape(analysis)

    # Highlight the change tree block (lines starting with 📁 📄 ↳)
    lines = escaped.split("\n")
    rendered = []
    in_tree = False
    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(p) for p in ("📁", "📄", "↳")):
            in_tree = True
            indent = len(line) - len(line.lstrip())
            pad = "&nbsp;" * indent
            if stripped.startswith("📁"):
                rendered.append(f'<div class="tree-line tree-folder">{pad}{stripped}</div>')
            elif stripped.startswith("📄"):
                rendered.append(f'<div class="tree-line tree-file">{pad}{stripped}</div>')
            elif stripped.startswith("↳"):
                key, _, val = stripped[1:].partition(":")
                rendered.append(
                    f'<div class="tree-line tree-detail">{pad}'
                    f'<span class="tree-key">↳{key}:</span>'
                    f'<span class="tree-val">{val}</span></div>'
                )
        else:
            if in_tree and stripped == "":
                in_tree = False
            # Bold **text**
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            # Section headings (### ...)
            if stripped.startswith("###"):
                rendered.append(f'<h3 class="analysis-heading">{stripped[3:].strip()}</h3>')
            elif stripped.startswith("##"):
                rendered.append(f'<h2 class="analysis-heading">{stripped[2:].strip()}</h2>')
            else:
                rendered.append(f"<p>{line}</p>" if line.strip() else "<br>")

    body = "\n".join(rendered)
    return f"""
      <!-- Analysis tab -->
      <div id="tab-analysis" class="tab-content">
        <style>
          .tree-line {{ font-family: var(--font-mono); font-size: 12px; line-height: 1.8; white-space: pre; }}
          .tree-folder {{ color: var(--blue); font-weight: 600; }}
          .tree-file {{ color: var(--text); }}
          .tree-detail {{ color: var(--muted); }}
          .tree-key {{ color: var(--accent); margin-right: 4px; }}
          .tree-val {{ color: var(--text); }}
          .tree-block {{ background: #0d1117; border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; margin-bottom: 20px; }}
          .analysis-heading {{ color: var(--blue); font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin: 20px 0 8px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }}
          #tab-analysis p {{ font-size: 13px; color: var(--text); margin: 4px 0; line-height: 1.6; }}
        </style>
        <div class="tree-block">{body}</div>
      </div>"""


class ReportBuilder:
    @staticmethod
    def build(
        mr_iid: int,
        mr_title: str,
        mr_url: str,
        author: str,
        source_branch: str,
        target_branch: str,
        changed_files: list[dict],
        gherkin: str,
        playwright: str,
        code_analysis: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        scenario_count = gherkin.count("Scenario")
        test_count = playwright.count("test(")
        file_count = len(changed_files)

        file_rows = ""
        for f in changed_files:
            status = "modified" if not f.get("new_file") else "added"
            badge_color = "#3fb950" if status == "added" else "#58a6ff"
            path = html_lib.escape(f.get("new_path", ""))
            file_rows += f"""
            <div class="file-row">
              <span class="file-badge" style="background:{badge_color}20;color:{badge_color}">{status}</span>
              <span class="file-path">{path}</span>
            </div>"""

        gherkin_escaped = html_lib.escape(gherkin)
        playwright_escaped = html_lib.escape(playwright)
        mr_title_escaped = html_lib.escape(mr_title)
        mr_url_escaped = html_lib.escape(mr_url)
        author_escaped = html_lib.escape(author)
        source_escaped = html_lib.escape(source_branch)
        target_escaped = html_lib.escape(target_branch)
        analysis_tab_html = _render_analysis_tab(code_analysis) if code_analysis else ""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI Test Report · MR !{mr_iid}</title>
  <style>
    :root {{
      --bg: #0d1117;
      --surface: #161b22;
      --border: #30363d;
      --text: #e6edf3;
      --muted: #8b949e;
      --accent: #f78166;
      --green: #3fb950;
      --blue: #58a6ff;
      --yellow: #d29922;
      --font-mono: "Cascadia Code", "Fira Code", "JetBrains Mono", monospace;
      --font-ui: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-ui);
      font-size: 14px;
      line-height: 1.6;
      min-height: 100vh;
    }}

    /* ── Header ── */
    .header {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 16px 24px;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .header-logo {{
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: var(--accent);
    }}
    .header-divider {{ color: var(--border); font-size: 20px; }}
    .header-title {{ color: var(--text); font-weight: 500; }}
    .mr-link {{
      color: var(--blue);
      text-decoration: none;
      font-family: var(--font-mono);
      font-size: 13px;
      padding: 2px 8px;
      background: rgba(88, 166, 255, 0.1);
      border-radius: 4px;
      border: 1px solid rgba(88, 166, 255, 0.2);
    }}
    .mr-link:hover {{ background: rgba(88, 166, 255, 0.2); }}

    /* ── Layout ── */
    .layout {{
      display: grid;
      grid-template-columns: 280px 1fr;
      height: calc(100vh - 57px);
    }}

    /* ── Sidebar ── */
    .sidebar {{
      background: var(--surface);
      border-right: 1px solid var(--border);
      overflow-y: auto;
      padding: 20px 16px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }}
    .sidebar-section-label {{
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .meta-grid {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .meta-item {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}
    .meta-label {{ font-size: 11px; color: var(--muted); }}
    .meta-value {{ font-size: 13px; color: var(--text); }}
    .meta-value.mono {{ font-family: var(--font-mono); font-size: 12px; }}

    .stat-row {{
      display: flex;
      gap: 8px;
    }}
    .stat-card {{
      flex: 1;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 10px 12px;
      text-align: center;
    }}
    .stat-number {{
      font-size: 22px;
      font-weight: 700;
      font-family: var(--font-mono);
      color: var(--accent);
    }}
    .stat-label {{ font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}

    .file-list {{ display: flex; flex-direction: column; gap: 4px; }}
    .file-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 5px 0;
      border-bottom: 1px solid var(--border);
    }}
    .file-badge {{
      font-size: 10px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 3px;
      white-space: nowrap;
      flex-shrink: 0;
    }}
    .file-path {{
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--muted);
      word-break: break-all;
    }}

    .ai-badge {{
      display: flex;
      align-items: center;
      gap: 6px;
      background: rgba(247, 129, 102, 0.1);
      border: 1px solid rgba(247, 129, 102, 0.3);
      border-radius: 6px;
      padding: 8px 12px;
      font-size: 12px;
      color: var(--accent);
    }}

    /* ── Main panel ── */
    .main {{
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}

    /* ── Tabs ── */
    .tabs {{
      display: flex;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
      gap: 0;
    }}
    .tab {{
      padding: 14px 20px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      color: var(--muted);
      border-bottom: 2px solid transparent;
      transition: color 0.15s, border-color 0.15s;
      user-select: none;
    }}
    .tab:hover {{ color: var(--text); }}
    .tab.active {{ color: var(--text); border-bottom-color: var(--accent); }}
    .tab-icon {{ margin-right: 6px; }}

    .tab-content {{
      display: none;
      flex: 1;
      overflow-y: auto;
      padding: 20px 24px;
    }}
    .tab-content.active {{ display: block; }}

    /* ── Code block ── */
    .code-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #1c2128;
      border: 1px solid var(--border);
      border-radius: 8px 8px 0 0;
      padding: 10px 16px;
    }}
    .code-lang {{
      font-size: 12px;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .copy-btn {{
      background: transparent;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.15s;
      font-family: var(--font-ui);
    }}
    .copy-btn:hover {{ background: var(--border); color: var(--text); }}
    .copy-btn.copied {{ border-color: var(--green); color: var(--green); }}

    pre {{
      background: #0d1117;
      border: 1px solid var(--border);
      border-top: none;
      border-radius: 0 0 8px 8px;
      padding: 20px;
      overflow-x: auto;
      margin-bottom: 24px;
    }}
    code {{
      font-family: var(--font-mono);
      font-size: 13px;
      line-height: 1.7;
      color: var(--text);
    }}

    /* ── Gherkin syntax highlighting ── */
    .gh-keyword {{ color: #ff7b72; font-weight: 600; }}
    .gh-scenario {{ color: #79c0ff; font-weight: 600; }}
    .gh-step {{ color: #e6edf3; }}
    .gh-comment {{ color: #8b949e; font-style: italic; }}
    .gh-tag {{ color: #d2a8ff; }}
    .gh-table {{ color: #a5d6ff; }}

    /* ── Warning banner ── */
    .warning {{
      display: flex;
      align-items: center;
      gap: 10px;
      background: rgba(210, 153, 34, 0.1);
      border: 1px solid rgba(210, 153, 34, 0.3);
      border-radius: 6px;
      padding: 10px 14px;
      margin-bottom: 16px;
      font-size: 13px;
      color: var(--yellow);
    }}

    /* ── Footer ── */
    .footer {{
      border-top: 1px solid var(--border);
      padding: 10px 24px;
      font-size: 12px;
      color: var(--muted);
      background: var(--surface);
    }}

    @media (max-width: 768px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ display: none; }}
    }}
  </style>
</head>
<body>

  <header class="header">
    <span class="header-logo">⚗️ TestGen</span>
    <span class="header-divider">|</span>
    <span class="header-title">{mr_title_escaped}</span>
    <a class="mr-link" href="{mr_url_escaped}" target="_blank">!{mr_iid} ↗</a>
  </header>

  <div class="layout">

    <!-- Sidebar -->
    <aside class="sidebar">

      <div>
        <div class="sidebar-section-label">Stats</div>
        <div class="stat-row">
          <div class="stat-card">
            <div class="stat-number">{scenario_count}</div>
            <div class="stat-label">Scenarios</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{test_count}</div>
            <div class="stat-label">Tests</div>
          </div>
          <div class="stat-card">
            <div class="stat-number">{file_count}</div>
            <div class="stat-label">Files</div>
          </div>
        </div>
      </div>

      <div>
        <div class="sidebar-section-label">MR Info</div>
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">Author</span>
            <span class="meta-value">{author_escaped}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Source → Target</span>
            <span class="meta-value mono">{source_escaped} → {target_escaped}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Generated</span>
            <span class="meta-value">{now}</span>
          </div>
        </div>
      </div>

      <div>
        <div class="sidebar-section-label">Changed Files ({file_count})</div>
        <div class="file-list">{file_rows}
        </div>
      </div>

      <div class="ai-badge">
        🤖 Generated by Claude (claude-sonnet-4-6)
      </div>

    </aside>

    <!-- Main panel -->
    <main class="main">
      <div class="tabs">
        <div class="tab active" onclick="switchTab('gherkin', this)">
          <span class="tab-icon">🥒</span>Gherkin
        </div>
        <div class="tab" onclick="switchTab('playwright', this)">
          <span class="tab-icon">🎭</span>Playwright
        </div>
        {'<div class="tab" onclick="switchTab(\'analysis\', this)"><span class="tab-icon">🔍</span>Analysis</div>' if code_analysis else ""}
      </div>

      <!-- Gherkin tab -->
      <div id="tab-gherkin" class="tab-content active">
        <div class="warning">
          ⚠️ Always review AI-generated scenarios before adding them to your test suite.
        </div>
        <div class="code-header">
          <span class="code-lang">🥒 Gherkin · .feature</span>
          <button class="copy-btn" onclick="copyCode('gherkin-code', this)">Copy</button>
        </div>
        <pre><code id="gherkin-code">{gherkin_escaped}</code></pre>
      </div>

      <!-- Playwright tab -->
      <div id="tab-playwright" class="tab-content">
        <div class="warning">
          ⚠️ Verify selectors and assertions match your actual application before running.
        </div>
        <div class="code-header">
          <span class="code-lang">🎭 Playwright · TypeScript</span>
          <button class="copy-btn" onclick="copyCode('playwright-code', this)">Copy</button>
        </div>
        <pre><code id="playwright-code">{playwright_escaped}</code></pre>
      </div>

      {analysis_tab_html}

      <footer class="footer">
        AI Test Generator · MR !{mr_iid} · {now}
      </footer>
    </main>

  </div>

  <script>
    function switchTab(name, el) {{
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
      el.classList.add('active');
      document.getElementById('tab-' + name).classList.add('active');
    }}

    function copyCode(id, btn) {{
      const code = document.getElementById(id).textContent;
      navigator.clipboard.writeText(code).then(() => {{
        btn.textContent = '✓ Copied';
        btn.classList.add('copied');
        setTimeout(() => {{
          btn.textContent = 'Copy';
          btn.classList.remove('copied');
        }}, 2000);
      }});
    }}
  </script>

</body>
</html>"""
