"""
Generate: Harnessing AI Agents — Profiles, Rules & Skills
PDF guide based on the quality project architecture.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

OUTPUT = "harnessing-ai-agents.pdf"

# ── Palette ──────────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#0D1B2A")
BLUE   = colors.HexColor("#0A9CD8")
TEAL   = colors.HexColor("#05B8A0")
AMBER  = colors.HexColor("#F59E0B")
RED    = colors.HexColor("#EF4444")
LIGHT  = colors.HexColor("#F0F7FC")
BORDER = colors.HexColor("#CBD5E1")
CODE_BG= colors.HexColor("#1E293B")
CODE_FG= colors.HexColor("#E2E8F0")
WHITE  = colors.white
DARK   = colors.HexColor("#1E293B")

# ── Styles ────────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

TITLE   = S("Title2", fontName="Helvetica-Bold", fontSize=28, textColor=WHITE,
             spaceAfter=6, leading=34)
SUBTITLE= S("Subtitle2", fontName="Helvetica", fontSize=13, textColor=colors.HexColor("#93C5FD"),
             spaceAfter=0, leading=18)
H1      = S("H1", fontName="Helvetica-Bold", fontSize=17, textColor=BLUE,
             spaceBefore=18, spaceAfter=6, leading=22, borderPadding=(0,0,4,0))
H2      = S("H2", fontName="Helvetica-Bold", fontSize=13, textColor=DARK,
             spaceBefore=12, spaceAfter=4, leading=17)
H3      = S("H3", fontName="Helvetica-Bold", fontSize=11, textColor=TEAL,
             spaceBefore=8, spaceAfter=3, leading=15)
BODY    = S("Body2", fontName="Helvetica", fontSize=10, textColor=DARK,
             spaceAfter=6, leading=15, alignment=TA_JUSTIFY)
BULLET  = S("Bullet2", fontName="Helvetica", fontSize=10, textColor=DARK,
             spaceAfter=4, leading=14, leftIndent=16, bulletIndent=6)
CODE    = S("Code2", fontName="Courier", fontSize=8.5, textColor=CODE_FG,
             spaceAfter=2, leading=13, leftIndent=10, rightIndent=10,
             backColor=CODE_BG, borderPadding=6)
CAPTION = S("Caption2", fontName="Helvetica-Oblique", fontSize=8.5,
             textColor=colors.HexColor("#64748B"), spaceAfter=6, leading=12, alignment=TA_CENTER)
LABEL   = S("Label2", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE,
             leading=12, alignment=TA_CENTER)
RULE_NUM= S("RuleNum", fontName="Helvetica-Bold", fontSize=10, textColor=BLUE,
             leading=14, spaceAfter=2)
RULE_TXT= S("RuleTxt", fontName="Helvetica", fontSize=10, textColor=DARK,
             leading=14, spaceAfter=2, leftIndent=10)
CALLOUT = S("Callout", fontName="Helvetica-Oblique", fontSize=10,
             textColor=DARK, leading=14, leftIndent=12, rightIndent=12,
             spaceAfter=4)

# ── Helpers ───────────────────────────────────────────────────────────────────
def hr(color=BORDER, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=8, spaceBefore=4)

def section_label(text, bg=BLUE):
    data = [[Paragraph(text, LABEL)]]
    return Table(data, colWidths=[4*cm],
                 style=TableStyle([
                     ("BACKGROUND", (0,0), (-1,-1), bg),
                     ("ROUNDEDCORNERS", [4]),
                     ("TOPPADDING",  (0,0), (-1,-1), 4),
                     ("BOTTOMPADDING",(0,0),(-1,-1), 4),
                     ("LEFTPADDING", (0,0), (-1,-1), 10),
                     ("RIGHTPADDING",(0,0), (-1,-1), 10),
                 ]))

def callout_box(text, bg=LIGHT, border_color=BLUE):
    data = [[Paragraph(text, CALLOUT)]]
    return Table(data, colWidths=["100%"],
                 style=TableStyle([
                     ("BACKGROUND",   (0,0), (-1,-1), bg),
                     ("LEFTPADDING",  (0,0), (-1,-1), 14),
                     ("RIGHTPADDING", (0,0), (-1,-1), 14),
                     ("TOPPADDING",   (0,0), (-1,-1), 10),
                     ("BOTTOMPADDING",(0,0), (-1,-1), 10),
                     ("LINEAFTER",    (0,0), (0,-1), 3, border_color),
                     ("ROUNDEDCORNERS", [3]),
                 ]))

def code_block(lines):
    return Table([[Paragraph(l.replace(" ", "&nbsp;").replace("<", "&lt;").replace(">", "&gt;"), CODE)]
                  for l in lines],
                 colWidths=["100%"],
                 style=TableStyle([
                     ("BACKGROUND",   (0,0), (-1,-1), CODE_BG),
                     ("TOPPADDING",   (0,0), (-1,-1), 2),
                     ("BOTTOMPADDING",(0,0), (-1,-1), 2),
                     ("LEFTPADDING",  (0,0), (-1,-1), 12),
                     ("RIGHTPADDING", (0,0), (-1,-1), 12),
                     ("ROUNDEDCORNERS", [4]),
                 ]))

def badge(text, bg=TEAL):
    data = [[Paragraph(f"<b>{text}</b>", S("b", fontName="Helvetica-Bold", fontSize=8,
                        textColor=WHITE, leading=11, alignment=TA_CENTER))]]
    return Table(data, colWidths=[2.6*cm],
                 style=TableStyle([
                     ("BACKGROUND",   (0,0), (-1,-1), bg),
                     ("TOPPADDING",   (0,0), (-1,-1), 3),
                     ("BOTTOMPADDING",(0,0), (-1,-1), 3),
                     ("LEFTPADDING",  (0,0), (-1,-1), 8),
                     ("RIGHTPADDING", (0,0), (-1,-1), 8),
                     ("ROUNDEDCORNERS", [10]),
                 ]))

def rule_row(num, title, body):
    return KeepTogether([
        Paragraph(f"{num} &nbsp; {title}", RULE_NUM),
        Paragraph(body, RULE_TXT),
        Spacer(1, 4),
    ])

def two_col(left_content, right_content, widths=(9*cm, 9*cm)):
    return Table([[left_content, right_content]], colWidths=widths,
                 style=TableStyle([
                     ("VALIGN",        (0,0), (-1,-1), "TOP"),
                     ("LEFTPADDING",   (0,0), (-1,-1), 0),
                     ("RIGHTPADDING",  (0,0), (-1,-1), 8),
                     ("TOPPADDING",    (0,0), (-1,-1), 0),
                     ("BOTTOMPADDING", (0,0), (-1,-1), 0),
                 ]))

# ── Cover page ────────────────────────────────────────────────────────────────
def cover():
    cover_bg = Table(
        [[Paragraph("Harnessing AI Agents", TITLE)],
         [Paragraph("Profiles · Rules · Skills", SUBTITLE)],
         [Spacer(1, 0.5*cm)],
         [Paragraph("A practical guide to designing multi-agent pipelines<br/>"
                    "that react to GitLab events and generate tests automatically.", SUBTITLE)],
         [Spacer(1, 1.2*cm)],
         [Paragraph("Based on the <b>quality</b> project — a production GitLab webhook app<br/>"
                    "that uses Claude to analyse MRs and generate BDD + Playwright tests.",
                    S("cv", fontName="Helvetica", fontSize=11, textColor=colors.HexColor("#BAE6FD"),
                       leading=17, alignment=TA_CENTER))],
        ],
        colWidths=["100%"],
        style=TableStyle([
            ("BACKGROUND",   (0,0), (-1,-1), NAVY),
            ("TOPPADDING",   (0,0), (-1,-1), 40),
            ("BOTTOMPADDING",(0,0), (-1,-1), 16),
            ("LEFTPADDING",  (0,0), (-1,-1), 30),
            ("RIGHTPADDING", (0,0), (-1,-1), 30),
            ("ROUNDEDCORNERS", [8]),
        ]),
    )
    return [cover_bg, Spacer(1, 0.8*cm)]

# ── Section 1 — Architecture ──────────────────────────────────────────────────
def section_architecture():
    items = [
        Paragraph("1. System Architecture", H1),
        hr(BLUE, 1),
        Paragraph(
            "The quality project is a FastAPI application deployed as a Docker container. "
            "GitLab sends webhook payloads to its single endpoint. The app dispatches work to "
            "two specialised AI agents running in background tasks — no blocking, no polling.",
            BODY),
        Spacer(1, 0.3*cm),
    ]

    # Pipeline diagram as a table
    pipeline_data = [
        [Paragraph("GitLab Webhook", S("pw", fontName="Helvetica-Bold", fontSize=9,
                    textColor=WHITE, leading=12, alignment=TA_CENTER))],
        [Paragraph("↓ MR open / update / reopen", S("arr", fontName="Helvetica", fontSize=8.5,
                    textColor=colors.HexColor("#94A3B8"), leading=12, alignment=TA_CENTER))],
        [Paragraph("POST /webhook/gitlab", S("ep", fontName="Courier", fontSize=9,
                    textColor=TEAL, leading=12, alignment=TA_CENTER))],
        [Paragraph("↓ pipeline success event", S("arr", fontName="Helvetica", fontSize=8.5,
                    textColor=colors.HexColor("#94A3B8"), leading=12, alignment=TA_CENTER))],
        [Paragraph("DEVELOPER AGENT\n(CodeAnalyzer)", S("ag", fontName="Helvetica-Bold", fontSize=9,
                    textColor=WHITE, leading=13, alignment=TA_CENTER))],
        [Paragraph("↓ structured brief", S("arr", fontName="Helvetica", fontSize=8.5,
                    textColor=colors.HexColor("#94A3B8"), leading=12, alignment=TA_CENTER))],
        [Paragraph("MR TEST GENERATOR\n(TestGenerator)", S("ag", fontName="Helvetica-Bold", fontSize=9,
                    textColor=WHITE, leading=13, alignment=TA_CENTER))],
        [Paragraph("↓ Gherkin + Playwright + MR comment", S("arr", fontName="Helvetica", fontSize=8.5,
                    textColor=colors.HexColor("#94A3B8"), leading=12, alignment=TA_CENTER))],
        [Paragraph("GitLab MR Comment + Commit Status", S("pw", fontName="Helvetica-Bold", fontSize=9,
                    textColor=WHITE, leading=12, alignment=TA_CENTER))],
    ]
    row_styles = [
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("BACKGROUND", (0,2), (-1,2), colors.HexColor("#0F2942")),
        ("BACKGROUND", (0,4), (-1,4), BLUE),
        ("BACKGROUND", (0,6), (-1,6), TEAL),
        ("BACKGROUND", (0,8), (-1,8), NAVY),
        ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#0A1628")),
        ("BACKGROUND", (0,3), (-1,3), colors.HexColor("#0A1628")),
        ("BACKGROUND", (0,5), (-1,5), colors.HexColor("#0A1628")),
        ("BACKGROUND", (0,7), (-1,7), colors.HexColor("#0A1628")),
        ("TOPPADDING",   (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ("LEFTPADDING",  (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("ROUNDEDCORNERS", [6]),
    ]
    pipeline_table = Table(pipeline_data, colWidths=[8*cm],
                           style=TableStyle(row_styles))

    key_data = [
        [Paragraph("<b>Key design decisions</b>", H3)],
        [Paragraph("• Two agents, clear separation of concerns: one analyses, one generates.", BULLET)],
        [Paragraph("• MR webhook fires immediately → sets <i>pending</i> commit status → visible in the MR.", BULLET)],
        [Paragraph("• Pipeline success event triggers generation — agents never run on broken code.", BULLET)],
        [Paragraph("• All generation runs in BackgroundTasks — webhook always returns instantly.", BULLET)],
        [Paragraph("• Dedup via <code>_done</code> + <code>_processing</code> sets prevents double-runs on retries.", BULLET)],
        [Paragraph("• Progressive MR comment: posted immediately, edited in-place at each step.", BULLET)],
    ]
    key_table = Table(key_data, colWidths=[9.5*cm],
                      style=TableStyle([
                          ("BACKGROUND",   (0,0), (-1,-1), LIGHT),
                          ("TOPPADDING",   (0,0), (-1,-1), 4),
                          ("BOTTOMPADDING",(0,0), (-1,-1), 4),
                          ("LEFTPADDING",  (0,0), (-1,-1), 12),
                          ("RIGHTPADDING", (0,0), (-1,-1), 12),
                          ("ROUNDEDCORNERS", [6]),
                          ("LINEAFTER", (0,0), (0,-1), 3, BLUE),
                      ]))

    items.append(two_col(pipeline_table, key_table, widths=[8*cm, 10*cm]))
    items.append(Spacer(1, 0.4*cm))
    return items

# ── Section 2 — Webhooks vs GitLab Apps ──────────────────────────────────────
def section_webhooks_vs_apps():
    GREEN  = colors.HexColor("#16A34A")
    GREEN_L= colors.HexColor("#F0FDF4")
    RED_L  = colors.HexColor("#FEF2F2")

    items = [
        PageBreak(),
        Paragraph("2. Webhooks vs GitLab Apps — Why Webhooks Win", H1),
        hr(BLUE, 1),
        Paragraph(
            "GitLab offers two ways to integrate external tooling: "
            "<b>webhook payloads</b> (GitLab pushes events to your server) and "
            "<b>GitLab Apps / OAuth integrations</b> (your app pulls data using OAuth tokens). "
            "The quality project is built on webhooks. This section explains why — and when "
            "that choice matters most for AI agent pipelines.", BODY),
        Spacer(1, 0.3*cm),
    ]

    # Side-by-side comparison header
    cmp_header = [
        [Paragraph("<b>Webhooks</b>", S("wh", fontName="Helvetica-Bold", fontSize=11,
                    textColor=WHITE, leading=14, alignment=TA_CENTER)),
         Paragraph("<b>GitLab Apps / OAuth</b>", S("ah", fontName="Helvetica-Bold", fontSize=11,
                    textColor=WHITE, leading=14, alignment=TA_CENTER))],
    ]
    cmp_rows = [
        ("Authentication",
         "Single shared secret in the X-Gitlab-Token header.\nSet once, never rotates unless you choose to.",
         "OAuth 2.0: client_id, client_secret, authorization code,\naccess token, refresh token — all managed by you."),
        ("Token lifecycle",
         "No tokens. The secret never expires.",
         "Access tokens expire (typically 2h). Refresh tokens\nmust be stored, rotated, and reissued automatically."),
        ("Local development",
         "ngrok tunnel or any HTTP forwarder.\nOne command: ngrok http 8000",
         "Requires a registered redirect URI. Local dev needs\na registered app with gitlab.com or your instance."),
        ("Deployment",
         "Any server that can receive HTTP POST requests.\nDocker, Render, Azure Container Apps, even a VPS.",
         "Must be reachable by GitLab for the OAuth callback.\nAdditional infra for token storage (DB or secrets manager)."),
        ("Scope of access",
         "Scoped by what GitLab sends in the payload.\nYou request only what you need via the API key.",
         "Scopes negotiated at install time and stored in the token.\nMismatched scopes break the integration silently."),
        ("Multi-repo support",
         "One webhook endpoint, configured per project in GitLab.\nEach project sends to the same URL.",
         "App must be installed per group or per project.\nInstallation state must be tracked."),
        ("Debugging",
         "GitLab shows every webhook delivery in the UI with the\nfull payload, response code, and retry history.",
         "OAuth errors surface as 401s at call time — no central\ndelivery log, harder to trace which call failed."),
        ("Portability",
         "Identical pattern on GitHub, Bitbucket, Azure DevOps.\nMigrating CI provider = update one URL.",
         "Each platform has its own OAuth implementation.\nMigration requires rewriting the auth layer."),
        ("Security surface",
         "One secret to protect. Rotate it in GitLab settings\nand update one env var.",
         "client_secret + per-installation tokens.\nCompromise of any token may expose all projects."),
        ("GitLab instance support",
         "Works on gitlab.com and any self-hosted instance\nwithout configuration changes.",
         "Self-hosted instances may have OAuth disabled\nor require admin-level app registration."),
    ]

    table_data = cmp_header[:]
    for dimension, webhook_text, app_text in cmp_rows:
        table_data.append([
            Paragraph(f"<b>{dimension}</b>", S("dim", fontName="Helvetica-Bold", fontSize=8.5,
                        textColor=DARK, leading=12)),
            Paragraph("", S("e", fontSize=4)),
        ])
        table_data.append([
            Paragraph(webhook_text.replace("\n", "<br/>"),
                      S("wt", fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#14532D"),
                         leading=13)),
            Paragraph(app_text.replace("\n", "<br/>"),
                      S("at", fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#7F1D1D"),
                         leading=13)),
        ])

    # Build a cleaner two-column comparison table
    clean_rows = [
        [Paragraph("Dimension", S("ch", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE,
                    leading=12, alignment=TA_CENTER)),
         Paragraph("Webhooks", S("ch2", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE,
                    leading=12, alignment=TA_CENTER)),
         Paragraph("GitLab Apps / OAuth", S("ch3", fontName="Helvetica-Bold", fontSize=9,
                    textColor=WHITE, leading=12, alignment=TA_CENTER))],
    ]
    for dimension, webhook_text, app_text in cmp_rows:
        clean_rows.append([
            Paragraph(f"<b>{dimension}</b>", S("dim2", fontName="Helvetica-Bold", fontSize=8.5,
                        textColor=DARK, leading=12)),
            Paragraph(webhook_text.replace("\n", "<br/>"),
                      S("wt2", fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#14532D"),
                         leading=13)),
            Paragraph(app_text.replace("\n", "<br/>"),
                      S("at2", fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#991B1B"),
                         leading=13)),
        ])

    row_styles = [
        ("BACKGROUND",    (0,0), (-1,0), NAVY),
        ("BACKGROUND",    (1,1), (1,-1), GREEN_L),
        ("BACKGROUND",    (2,1), (2,-1), RED_L),
        ("BACKGROUND",    (0,1), (0,-1), colors.HexColor("#F8FAFC")),
        ("GRID",          (0,0), (-1,-1), 0.3, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS",(0,1), (0,-1), [colors.HexColor("#F8FAFC"), colors.HexColor("#F1F5F9")]),
    ]
    cmp_table = Table(clean_rows, colWidths=[3.5*cm, 8*cm, 6*cm],
                      style=TableStyle(row_styles))
    items.append(cmp_table)
    items.append(Spacer(1, 0.4*cm))

    items.append(Paragraph("2.1 The operational reality for AI agent pipelines", H2))
    items.append(Paragraph(
        "AI agents add a new dimension to the webhook vs. app decision: "
        "<b>latency and reliability matter more than feature richness</b>. "
        "Here is what that means in practice for the quality project:", BODY))

    operational_points = [
        ("Token expiry kills long-running agents",
         "The quality app's process_mr() function can take 20-40 seconds. "
         "An OAuth access token that expires mid-run causes a 401 with no retry — "
         "the agent silently fails and leaves the MR in 'running' status forever. "
         "Webhooks have no tokens to expire."),
        ("Webhook delivery logs are your best debugging tool",
         "GitLab records every webhook delivery: timestamp, payload, HTTP response, "
         "and whether it was retried. When an agent fails you can replay the exact payload "
         "from the GitLab UI. OAuth integrations have no equivalent."),
        ("The secret is your only attack surface",
         "The quality app validates X-Gitlab-Token on every request (middleware.py). "
         "That is one secret to rotate, audit, and protect. "
         "An OAuth integration has a client_secret plus N installation tokens — "
         "each one a credential that can be leaked or expire."),
        ("Portability matters when your team grows",
         "Today the quality project runs on GitLab. Tomorrow it might need to run on "
         "GitHub for a partner project. Webhooks are identical across providers — "
         "only the payload schema changes. OAuth is entirely provider-specific."),
        ("Fewer moving parts = fewer incidents",
         "The quality app has zero background jobs managing token refresh, "
         "zero database tables storing OAuth state, and zero scheduled tasks "
         "rotating credentials. That is not a small thing at 2 AM when something breaks."),
    ]

    for title, body in operational_points:
        items.append(KeepTogether([
            Paragraph(f"<b>{title}</b>",
                      S("opt", fontName="Helvetica-Bold", fontSize=10, textColor=BLUE,
                         leading=14, spaceBefore=8, spaceAfter=2)),
            Paragraph(body, S("opb", fontName="Helvetica", fontSize=9.5, textColor=DARK,
                               leading=14, leftIndent=12, spaceAfter=4)),
        ]))

    items.append(Spacer(1, 0.3*cm))
    items.append(Paragraph("2.2 When to use GitLab Apps instead", H2))
    items.append(Paragraph(
        "Webhooks are not always the right choice. "
        "There are specific scenarios where the OAuth app model is the correct tool:", BODY))

    when_app = [
        ["Use a GitLab App when...", "Why webhooks fall short here"],
        ["You need to act on user-level behalf\n(e.g. assign MRs, impersonate a user)",
         "Webhooks authenticate as a project token — no user identity.\nOAuth gives you a token scoped to a real user."],
        ["You are building a GitLab Marketplace listing\n(public SaaS product)",
         "Marketplace requires OAuth install flow and GitLab's\napp registration process."],
        ["You need fine-grained per-installation permissions\n(different scopes per group)",
         "Webhooks use a single project token.\nOAuth scopes can be negotiated per installation."],
        ["Your integration is pull-based\n(you poll GitLab, not the other way)",
         "Webhooks are push-only.\nFor polling you need an API token anyway — OAuth is cleaner."],
    ]
    when_table = Table(when_app, colWidths=[8.5*cm, 9*cm],
                       style=TableStyle([
                           ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#7C3AED")),
                           ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
                           ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
                           ("FONTSIZE",     (0,0), (-1,-1), 8.5),
                           ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, colors.HexColor("#F5F3FF")]),
                           ("GRID",         (0,0), (-1,-1), 0.3, BORDER),
                           ("TOPPADDING",   (0,0), (-1,-1), 7),
                           ("BOTTOMPADDING",(0,0), (-1,-1), 7),
                           ("LEFTPADDING",  (0,0), (-1,-1), 10),
                           ("RIGHTPADDING", (0,0), (-1,-1), 10),
                           ("VALIGN",       (0,0), (-1,-1), "TOP"),
                       ]))
    items.append(when_table)
    items.append(Spacer(1, 0.35*cm))

    items.append(callout_box(
        "<b>Bottom line:</b> For an internal AI agent pipeline triggered by CI events — "
        "where you own the server, the team is small, and reliability matters more than "
        "user-level delegation — webhooks are strictly simpler, more debuggable, "
        "and easier to operate than OAuth apps. "
        "The quality project's entire auth layer is 12 lines of middleware.",
        bg=colors.HexColor("#F0FDF4"), border_color=GREEN))

    items.append(Spacer(1, 0.25*cm))
    items.append(Paragraph("2.3 The quality project's webhook auth (12 lines)", H2))
    items.append(Paragraph(
        "The entire authentication layer for the quality project is a single FastAPI middleware "
        "that checks one header. Compare this to the ~200 lines of OAuth plumbing a GitLab App would require:", BODY))
    items.append(code_block([
        "# app/middleware.py — the complete auth layer",
        "from starlette.middleware.base import BaseHTTPMiddleware",
        "from starlette.requests import Request",
        "from starlette.responses import JSONResponse",
        "import os",
        "",
        "GITLAB_TOKEN = os.environ['GITLAB_WEBHOOK_SECRET']",
        "",
        "class GitlabTokenMiddleware(BaseHTTPMiddleware):",
        "    async def dispatch(self, request: Request, call_next):",
        "        if request.url.path.startswith('/webhook'):",
        "            token = request.headers.get('X-Gitlab-Token', '')",
        "            if token != GITLAB_TOKEN:",
        "                return JSONResponse({'error': 'Unauthorized'}, status_code=401)",
        "        return await call_next(request)",
    ]))
    items.append(Paragraph(
        "One environment variable. One header check. No token storage, no refresh jobs, "
        "no installation state. This is the entire security model.",
        S("note", fontName="Helvetica-Oblique", fontSize=9, textColor=colors.HexColor("#475569"),
           leading=13, spaceAfter=8)))

    items.append(Spacer(1, 0.2*cm))
    return items


# ── Section 3 — Profiles (was 2) ─────────────────────────────────────────────
def section_profiles():
    items = [
        PageBreak(),
        Paragraph("3. Agent Profiles", H1),
        hr(BLUE, 1),
        Paragraph(
            "A <b>profile</b> is the identity contract for an agent. It answers four questions: "
            "<i>Who is it? What is it for? What does it receive? What does it produce?</i> "
            "Profiles live in <code>agents/&lt;agent-name&gt;/profile.md</code> and are human-readable "
            "documentation — they are NOT injected into the model prompt. They are the contract "
            "that rules and skills implement.", BODY),
        Spacer(1, 0.3*cm),
        callout_box(
            "Rule of thumb: if two people on the team disagree about what an agent should do, "
            "the profile is what you update — not the code. A clear profile prevents scope creep.",
            bg=LIGHT, border_color=AMBER),
        Spacer(1, 0.3*cm),
        Paragraph("2.1 DEVELOPER AGENT profile", H2),
        Paragraph(
            "This agent acts as a senior engineer who reads code before any tests are written. "
            "Its output is a structured brief — never test code.", BODY),
    ]

    dev_profile = [
        ["Field", "Value"],
        ["Identity", "Senior software engineer reading MR diffs"],
        ["Purpose", "Fill the context gap — diffs alone don't show intent"],
        ["Inputs", "MR title + description, unified diff, up to 10 file contents"],
        ["Output", "Structured brief: Change Tree, Business logic, Data flows,\nIntegration points, Error paths, Test priorities"],
        ["Constraints", "Analysis only — never generates test code\nCaps output at ~800 words\nFlags uncertainty explicitly"],
    ]
    profile_table = Table(dev_profile, colWidths=[3.5*cm, 14*cm],
                          style=TableStyle([
                              ("BACKGROUND",   (0,0), (-1,0), NAVY),
                              ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
                              ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
                              ("FONTSIZE",     (0,0), (-1,-1), 9),
                              ("FONTNAME",     (0,1), (0,-1), "Helvetica-Bold"),
                              ("TEXTCOLOR",    (0,1), (0,-1), BLUE),
                              ("BACKGROUND",   (0,1), (-1,-1), WHITE),
                              ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT]),
                              ("GRID",         (0,0), (-1,-1), 0.3, BORDER),
                              ("TOPPADDING",   (0,0), (-1,-1), 6),
                              ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                              ("LEFTPADDING",  (0,0), (-1,-1), 10),
                              ("RIGHTPADDING", (0,0), (-1,-1), 10),
                              ("VALIGN",       (0,0), (-1,-1), "TOP"),
                          ]))
    items.append(profile_table)
    items.append(Spacer(1, 0.35*cm))

    items.append(Paragraph("2.2 MR TEST GENERATOR profile", H2))
    items.append(Paragraph(
        "This agent consumes the DEVELOPER AGENT's brief and generates test artifacts. "
        "It never analyses code directly — it trusts the brief.", BODY))

    gen_profile = [
        ["Field", "Value"],
        ["Identity", "AI code quality agent monitoring GitLab MRs"],
        ["Trigger", "GitLab webhook: MR open / update / reopen"],
        ["Inputs", "MR title + description, diff, file contents (max 10),\nexisting test examples, DEVELOPER AGENT brief (optional)"],
        ["Outputs", "1. Gherkin .feature file\n2. Playwright TypeScript test file\n3. Formatted MR comment (live, edited in-place)\n4. Commit status: pending → running → success/failed"],
        ["Constraints", "Max 10 files per MR, max 8 000 tokens of diff\nAlways returns 202 immediately — never blocks the MR\nPosts error comment on failure — never silent"],
    ]
    gen_table = Table(gen_profile, colWidths=[3.5*cm, 14*cm],
                      style=TableStyle([
                          ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#0A3347")),
                          ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
                          ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
                          ("FONTSIZE",     (0,0), (-1,-1), 9),
                          ("FONTNAME",     (0,1), (0,-1), "Helvetica-Bold"),
                          ("TEXTCOLOR",    (0,1), (0,-1), TEAL),
                          ("BACKGROUND",   (0,1), (-1,-1), WHITE),
                          ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT]),
                          ("GRID",         (0,0), (-1,-1), 0.3, BORDER),
                          ("TOPPADDING",   (0,0), (-1,-1), 6),
                          ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                          ("LEFTPADDING",  (0,0), (-1,-1), 10),
                          ("RIGHTPADDING", (0,0), (-1,-1), 10),
                          ("VALIGN",       (0,0), (-1,-1), "TOP"),
                      ]))
    items.append(gen_table)
    items.append(Spacer(1, 0.35*cm))

    items.append(Paragraph("2.3 Profile template", H2))
    items.append(Paragraph("Use this template when creating a new agent:", BODY))
    items.append(code_block([
        "# Agent: <Name>",
        "",
        "## Identity",
        "One sentence: who this agent is and what perspective it brings.",
        "",
        "## Purpose",
        "Why does this agent exist? What problem does it solve that no existing agent covers?",
        "",
        "## Trigger",
        "What event or call activates this agent?",
        "",
        "## Inputs",
        "- Item 1 (type, source, size limit)",
        "- Item 2 ...",
        "",
        "## Outputs",
        "- Output 1 (format, destination)",
        "- Output 2 ...",
        "",
        "## Operating Constraints",
        "- Hard limits (token caps, file counts, timeouts)",
        "- What this agent NEVER does (role separation)",
    ]))
    items.append(Spacer(1, 0.2*cm))
    return items

# ── Section 3 — Rules ─────────────────────────────────────────────────────────
def section_rules():
    items = [
        PageBreak(),
        Paragraph("4. Agent Rules", H1),
        hr(BLUE, 1),
        Paragraph(
            "Rules are <b>enforceable behavioural constraints</b> — things the agent must or must not do "
            "regardless of what the LLM might otherwise produce. They live in "
            "<code>agents/&lt;agent-name&gt;/rules.md</code> and are a mix of: "
            "prompt instructions (injected into the system prompt), "
            "code-level guards (checked in Python before/after calling the model), "
            "and operational policies (enforced by the pipeline, not the model).", BODY),
        Spacer(1, 0.3*cm),
        callout_box(
            "A rule without a <b>Why</b> is a rule that gets removed the moment someone "
            "doesn't understand it. Always document the reason — often a past incident or a "
            "hard-learned constraint that isn't obvious from the code.",
            bg=colors.HexColor("#FFF7ED"), border_color=AMBER),
        Spacer(1, 0.3*cm),
        Paragraph("3.1 DEVELOPER AGENT rules", H2),
    ]

    dev_rules = [
        ("R1 — Analyse before generating",
         "Always runs before the MR TEST GENERATOR. If it fails, the test generator "
         "continues without the brief — never blocks the pipeline. (code guard in main.py)"),
        ("R2 — Stay in analysis mode",
         "Never produces test code, Gherkin, or Playwright. Sole output is the structured brief. "
         "Mixing roles degrades both outputs. (prompt instruction)"),
        ("R3 — Name names",
         "Must reference actual identifiers from the code — function names, variable names, "
         "endpoints. Generic descriptions are not acceptable. (prompt instruction)"),
        ("R4 — Prioritise by risk, not by size",
         "A one-line auth check outweighs a 200-line UI refactor. Test priorities must reflect "
         "business impact. (prompt instruction)"),
        ("R5 — Pass the brief as structured context",
         "Brief injected into the test generator's system prompt under '## Code Analysis', "
         "after style examples and before the diff. (code — _build_system in test_generator.py)"),
        ("R6 — Cap analysis length",
         "Output must stay under 800 words. If the MR is too large, analyse highest-risk files "
         "only and note which were skipped. (max_tokens=1024 in code_analyzer.py)"),
        ("R7 — Learn from the test generator's output",
         "If generated scenarios miss a flagged edge case, that gap is noted in the agent's rules "
         "as a standing instruction. Closes the feedback loop. (operational policy)"),
    ]

    for num_title, body in dev_rules:
        items.append(rule_row(num_title[:2], num_title[5:], body))
    items.append(hr())

    items.append(Paragraph("3.2 MR TEST GENERATOR rules", H2))

    gen_rules = [
        ("R1 — Learn from existing tests",
         "Fetch up to 3 existing test files before every generation. "
         "Prepend under '## Existing test style — match this'. Missing files are not an error. (code guard)"),
        ("R2 — Match existing test style",
         "Inject the fetched test files as '## Existing test style — match this'. "
         "Style consistency matters more than theoretical correctness. (code — gitlab_client.py)"),
        ("R3 — Surface learning signals in the comment",
         "Every MR comment ends with a feedback line. Reactions logged to feedback-log.jsonl. "
         "Without feedback the agent cannot distinguish good from bad generations. (template)"),
        ("R4 — Honour explicit overrides in MR description",
         "A fenced agent-instructions block in the MR description adds per-MR instructions to the prompt. "
         "Gives developers an escape hatch without touching any config; builds trust. (code — parse before prompt build)"),
        ("R5 — Never block the MR",
         "Generation always runs in BackgroundTasks. Webhook always returns 202 immediately. "
         "On failure: post error comment, log, exit cleanly. (code — FastAPI BackgroundTasks)"),
        ("R6 — Respect file caps",
         "Max 10 files, max 8 000 tokens of diff. Prefer most-changed files when truncating. "
         "Large MRs produce noisy, low-quality output. (code — _filter_relevant_files)"),
        ("R7 — Refine rules when patterns stabilise",
         "After 10 positive reactions, propose an update to the agent's rules.md via a new MR. "
         "Learning should live in the repo, owned by the team. (operational policy)"),
        ("R8 — Version the prompt",
         "Log system prompt hash to the HTML report footer. When rules/skills change, "
         "the hash changes — correlates output quality with prompt versions. (code — report builder)"),
    ]

    for num_title, body in gen_rules:
        items.append(rule_row(num_title[:2], num_title[5:], body))
    items.append(Spacer(1, 0.3*cm))

    items.append(Paragraph("3.3 Rule anatomy — the three-part structure", H2))
    items.append(Paragraph(
        "Every rule in this project follows the same structure, which makes them "
        "maintainable and actionable:", BODY))
    items.append(code_block([
        "## R<N> — <Short imperative title>",
        "<What the agent must do or must not do — one or two sentences.>",
        "",
        "**Why:** <The reason — often a past incident or a hard constraint>",
        "(Where enforced: prompt instruction | code guard | operational policy)",
    ]))
    items.append(Spacer(1, 0.2*cm))
    return items

# ── Section 4 — Skills ────────────────────────────────────────────────────────
def section_skills():
    items = [
        PageBreak(),
        Paragraph("5. Agent Skills", H1),
        hr(BLUE, 1),
        Paragraph(
            "Skills serve two purposes. The <b>prose section</b> (readable headings) documents "
            "what the agent is capable of — useful for humans reviewing the agent design. "
            "The <b>SKILL blocks</b> (HTML comments) contain the actual system prompt text that "
            "gets extracted by code and sent to the model. This dual-use design keeps prompt "
            "engineering version-controlled and auditable alongside the rest of the codebase.",
            BODY),
        Spacer(1, 0.3*cm),
        callout_box(
            "Skills are the only place where raw prompt text lives. "
            "Keeping them in Markdown files (not in Python strings) means prompt changes "
            "are visible in git diffs — they go through code review like any other change.",
            bg=LIGHT, border_color=TEAL),
        Spacer(1, 0.3*cm),
        Paragraph("4.1 File structure", H2),
        Paragraph(
            "A skills file mixes two things: human-readable capability documentation and "
            "machine-readable SKILL blocks. The extraction mechanism uses HTML comments as delimiters:", BODY),
        code_block([
            "## 2. Gherkin Generation",
            "- Writes valid BDD .feature files from code changes and MR intent",
            "- Covers happy path, edge cases, and error/boundary conditions",
            "  ...",
            "",
            "<!-- SKILL:GHERKIN_SYSTEM -->",
            "You are an expert QA engineer specializing in BDD.",
            "Given a GitLab MR title, description, and diff, generate Gherkin content.",
            "",
            "Rules:",
            "- Write realistic, concrete scenarios based on actual code changes",
            "- Cover happy path, edge cases, and error states",
            "  ...",
            "<!-- END:GHERKIN_SYSTEM -->",
        ]),
        Spacer(1, 0.3*cm),
        Paragraph("4.2 How skills are extracted (the mechanism)", H2),
        Paragraph(
            "Both <code>code_analyzer.py</code> and <code>test_generator.py</code> use the same "
            "extraction pattern. The skill block is loaded once at module import time — not on "
            "every API call — so it is fast and fails loudly at startup if a skill is missing:", BODY),
        code_block([
            "import re",
            "from pathlib import Path",
            "",
            "_SKILLS_FILE = Path(__file__).parent.parent / 'agents' / 'developer-agent' / 'skills.md'",
            "",
            "def _extract_skill(name: str) -> str:",
            "    text = _SKILLS_FILE.read_text()",
            "    match = re.search(",
            "        rf'<!-- SKILL:{name} -->\\n(.*?)<!-- END:{name} -->',",
            "        text, re.DOTALL",
            "    )",
            "    if not match:",
            "        raise ValueError(f\"Skill block '{name}' not found\")",
            "    return match.group(1).strip()",
            "",
            "# Loaded once at module import — fails fast at startup",
            "DEVELOPER_SYSTEM = _extract_skill('DEVELOPER_SYSTEM')",
        ]),
        Spacer(1, 0.3*cm),
        Paragraph("4.3 DEVELOPER AGENT skills", H2),
    ]

    dev_skills = [
        ("Code Intent Recognition",
         "Reads function/variable names, comments, and structure to infer purpose. "
         "Distinguishes bug fixes from new features from refactors."),
        ("Business Logic Extraction",
         "Detects conditional branches, guard clauses, and validation rules. "
         "Surfaces implicit business constraints easy to miss in a diff view."),
        ("Data Flow Mapping",
         "Traces how inputs move through functions: transformations, aggregations, filtering. "
         "Identifies state reads vs. writes, and side effects."),
        ("Integration Point Detection",
         "Recognises HTTP calls, database queries, message queue interactions, file I/O. "
         "Flags integration points that are high-risk for regressions."),
        ("Edge Case & Error Path Analysis",
         "Identifies null/undefined handling, empty collections, zero values. "
         "Spots try/catch blocks and boundary conditions."),
        ("Test Priority Ranking",
         "Scores each identified behaviour by risk (likelihood x impact). "
         "Calls out the single most important thing to test first."),
    ]

    skill_rows = [[Paragraph(f"<b>{s}</b>", S("sh", fontName="Helvetica-Bold", fontSize=9,
                              textColor=DARK, leading=13)),
                   Paragraph(d, S("sd", fontName="Helvetica", fontSize=9, textColor=DARK,
                              leading=13))]
                  for s, d in dev_skills]
    skill_rows.insert(0, [Paragraph("Skill", LABEL), Paragraph("What it does", LABEL)])

    skills_table = Table(skill_rows, colWidths=[5*cm, 12.5*cm],
                         style=TableStyle([
                             ("BACKGROUND",   (0,0), (-1,0), BLUE),
                             ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT]),
                             ("GRID",         (0,0), (-1,-1), 0.3, BORDER),
                             ("TOPPADDING",   (0,0), (-1,-1), 6),
                             ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                             ("LEFTPADDING",  (0,0), (-1,-1), 10),
                             ("RIGHTPADDING", (0,0), (-1,-1), 10),
                             ("VALIGN",       (0,0), (-1,-1), "TOP"),
                         ]))
    items.append(skills_table)
    items.append(Spacer(1, 0.35*cm))

    items.append(Paragraph("4.4 MR TEST GENERATOR skills", H2))

    gen_skills = [
        ("Diff Analysis", "Parses unified diffs, filters to relevant extensions (.ts .tsx .py .go ...), "
         "excludes test files, deleted files, and generated code."),
        ("Gherkin Generation", "Writes valid BDD .feature files. Covers happy path, edge cases, "
         "error states. Uses Feature, Rule, Scenario, Scenario Outline, Examples correctly."),
        ("Playwright Generation", "Maps each Gherkin scenario 1:1 to a test() block. "
         "Applies Page Object Model. Uses getByRole, getByLabel, getByTestId selectors."),
        ("GitLab Operations", "Fetches MR diff and file contents via GitLab REST API. "
         "Posts/edits MR comments. Sets commit statuses (pending/running/success/failed)."),
        ("Report Generation", "Builds self-contained HTML report with sidebar, tabbed code view, "
         "and copy buttons. Committed to MR branch — no external hosting."),
        ("Context Awareness", "Fetches up to 3 existing test files from the target repo as few-shot "
         "style examples. Injects them into the system prompt before generation."),
    ]

    gen_skill_rows = [[Paragraph(f"<b>{s}</b>", S("sh", fontName="Helvetica-Bold", fontSize=9,
                                  textColor=DARK, leading=13)),
                       Paragraph(d, S("sd", fontName="Helvetica", fontSize=9, textColor=DARK,
                                  leading=13))]
                      for s, d in gen_skills]
    gen_skill_rows.insert(0, [Paragraph("Skill", LABEL), Paragraph("What it does", LABEL)])

    gen_skills_table = Table(gen_skill_rows, colWidths=[5*cm, 12.5*cm],
                             style=TableStyle([
                                 ("BACKGROUND",   (0,0), (-1,0), TEAL),
                                 ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT]),
                                 ("GRID",         (0,0), (-1,-1), 0.3, BORDER),
                                 ("TOPPADDING",   (0,0), (-1,-1), 6),
                                 ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                                 ("LEFTPADDING",  (0,0), (-1,-1), 10),
                                 ("RIGHTPADDING", (0,0), (-1,-1), 10),
                                 ("VALIGN",       (0,0), (-1,-1), "TOP"),
                             ]))
    items.append(gen_skills_table)
    items.append(Spacer(1, 0.2*cm))
    return items

# ── Section 5 — Prompt assembly ───────────────────────────────────────────────
def section_prompt_assembly():
    items = [
        PageBreak(),
        Paragraph("6. How It All Connects — Prompt Assembly", H1),
        hr(BLUE, 1),
        Paragraph(
            "Understanding how profiles, rules, skills, and runtime context combine into "
            "the final API call is the key to debugging and improving agent output.", BODY),
        Spacer(1, 0.3*cm),
        Paragraph("5.1 DEVELOPER AGENT prompt assembly", H2),
        Paragraph(
            "The DEVELOPER AGENT has a single system prompt — the DEVELOPER_SYSTEM skill block. "
            "The user message is assembled from the MR context:", BODY),
        code_block([
            "# system prompt = DEVELOPER_SYSTEM skill block (extracted at import time)",
            "",
            "# user message = assembled from MR context",
            "parts = [",
            "    f'## MR Title\\n{mr_title}',",
            "    f'## Description\\n{mr_description[:1000]}',   # R6: cap length",
            "    f'## Changed Files\\n{files_section}',          # up to 5 files, 2000 chars each",
            "    f'## Diff\\n```diff\\n{diff_text[:6000]}\\n```', # R6: cap diff",
            "    'Produce the structured analysis brief:',",
            "]",
            "",
            "message = await client.messages.create(",
            "    model='claude-sonnet-4-6',",
            "    max_tokens=1024,      # R6: enforces 800-word cap",
            "    system=DEVELOPER_SYSTEM,",
            "    messages=[{'role': 'user', 'content': '\\n\\n'.join(parts)}],",
            ")",
        ]),
        Spacer(1, 0.3*cm),
        Paragraph("5.2 MR TEST GENERATOR prompt assembly", H2),
        Paragraph(
            "The test generator builds a richer system prompt by layering multiple context sources "
            "in a defined order. The order matters — later sections override or refine earlier ones:", BODY),
        code_block([
            "def _build_system(base, example_tests, code_analysis):",
            "    parts = [",
            "        base,                          # 1. GHERKIN_SYSTEM or PLAYWRIGHT_SYSTEM skill",
            "    ]",
            "    if example_tests:                  # 2. R2: few-shot style examples",
            "        parts.append('## Existing test style — match this\\n...')",
            "    if code_analysis:                  # 3. R5: DEVELOPER AGENT brief (highest priority)",
            "        parts.append(f'## Code Analysis\\n{code_analysis}')",
            "    return '\\n\\n'.join(parts)",
            "",
            "# Per-MR agent-instructions block (R4) appends per-MR instructions to base",
        ]),
        Spacer(1, 0.3*cm),

        Paragraph("5.3 Context injection order (priority)", H2),
        Paragraph(
            "When multiple context sources are present, the model reads them in this order. "
            "Later items override earlier ones when they conflict:", BODY),
    ]

    order_data = [
        ["Priority", "Source", "When present", "Enforced by"],
        ["1 — base",   "GHERKIN_SYSTEM or PLAYWRIGHT_SYSTEM skill block",
         "Always",           "Extracted at import time"],
        ["2",          "Existing test files from target repo (up to 3)",
         "If files exist",   "R1 — fetched before every call"],
        ["3 — highest","DEVELOPER AGENT brief",
         "If DA succeeded",  "R5 — injected last, read last"],
        ["Override",   "agent-instructions block in MR description",
         "If block present", "R4 — per-MR instructions appended to base"],
    ]
    order_table = Table(order_data, colWidths=[2.5*cm, 6.5*cm, 4*cm, 4.5*cm],
                        style=TableStyle([
                            ("BACKGROUND",   (0,0), (-1,0), NAVY),
                            ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
                            ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
                            ("FONTSIZE",     (0,0), (-1,-1), 8.5),
                            ("FONTNAME",     (0,1), (0,-1), "Helvetica-Bold"),
                            ("TEXTCOLOR",    (0,5), (-1,5), colors.HexColor("#7C3AED")),
                            ("BACKGROUND",   (0,5), (-1,5), colors.HexColor("#F5F3FF")),
                            ("ROWBACKGROUNDS",(0,1), (-1,4), [WHITE, LIGHT]),
                            ("GRID",         (0,0), (-1,-1), 0.3, BORDER),
                            ("TOPPADDING",   (0,0), (-1,-1), 6),
                            ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                            ("LEFTPADDING",  (0,0), (-1,-1), 8),
                            ("RIGHTPADDING", (0,0), (-1,-1), 8),
                            ("VALIGN",       (0,0), (-1,-1), "TOP"),
                        ]))
    items.append(order_table)
    items.append(Spacer(1, 0.2*cm))
    return items

# ── Section 6 — Adding a new agent ────────────────────────────────────────────
def section_new_agent():
    items = [
        PageBreak(),
        Paragraph("7. Adding a New Agent — Step by Step", H1),
        hr(BLUE, 1),
        Paragraph(
            "Use this checklist when you want to extend the pipeline with a new agent — "
            "for example, a Security Reviewer or a Documentation Writer that runs after "
            "the test generator.", BODY),
        Spacer(1, 0.3*cm),
    ]

    steps = [
        ("Step 1", "Create the agent directory",
         "mkdir agents/my-new-agent\ntouch agents/my-new-agent/profile.md\n"
         "touch agents/my-new-agent/rules.md\ntouch agents/my-new-agent/skills.md"),
        ("Step 2", "Write the profile",
         "Fill profile.md with Identity, Purpose, Trigger, Inputs, Outputs, Constraints.\n"
         "Keep it under one page. If you need more, the agent is doing too much."),
        ("Step 3", "Write the rules",
         "Write at least: one rule for what it NEVER does (role separation),\n"
         "one rule for failure behaviour (never block the pipeline),\n"
         "one rule for output caps (token/file limits)."),
        ("Step 4", "Write the skills",
         "Prose documentation first, then add a SKILL block with the system prompt:\n"
         "<!-- SKILL:MY_AGENT_SYSTEM -->\nYou are...\n<!-- END:MY_AGENT_SYSTEM -->"),
        ("Step 5", "Add the extractor module",
         "Create app/my_agent.py. Copy the _extract_skill pattern from code_analyzer.py.\n"
         "Load the skill at module import time — not inside the async function."),
        ("Step 6", "Wire it into main.py",
         "Decide where in process_mr() it runs. Add a _update() call after it completes\n"
         "so the live MR comment reflects its progress."),
        ("Step 7", "Write a test",
         "Add tests/test_my_agent.py with at least one happy-path test and one failure test.\n"
         "Use pytest-asyncio. Mock the Anthropic client — don't call the real API in tests."),
    ]

    for step, title, body in steps:
        step_data = [
            [Paragraph(step, S("sn", fontName="Helvetica-Bold", fontSize=9,
                                textColor=WHITE, leading=12, alignment=TA_CENTER)),
             Paragraph(f"<b>{title}</b>", S("st", fontName="Helvetica-Bold", fontSize=10,
                                             textColor=DARK, leading=14))],
            [Paragraph("", S("e", fontSize=8)),
             Paragraph(body.replace("\n", "<br/>"), S("sb", fontName="Courier", fontSize=8.5,
                                    textColor=colors.HexColor("#334155"), leading=13))],
        ]
        step_table = Table(step_data, colWidths=[2*cm, 15.5*cm],
                           style=TableStyle([
                               ("BACKGROUND",   (0,0), (0,0), BLUE),
                               ("BACKGROUND",   (0,0), (-1,-1), LIGHT),
                               ("BACKGROUND",   (0,0), (0,0), BLUE),
                               ("TOPPADDING",   (0,0), (-1,-1), 6),
                               ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                               ("LEFTPADDING",  (0,0), (-1,-1), 10),
                               ("RIGHTPADDING", (0,0), (-1,-1), 10),
                               ("VALIGN",       (0,0), (-1,-1), "TOP"),
                               ("ROUNDEDCORNERS", [4]),
                               ("LINEBELOW",    (0,-1), (-1,-1), 0.5, BORDER),
                           ]))
        items.append(step_table)
        items.append(Spacer(1, 0.15*cm))

    items.append(Spacer(1, 0.2*cm))
    return items

# ── Section 7 — Lessons / quick ref ──────────────────────────────────────────
def section_reference():
    items = [
        PageBreak(),
        Paragraph("8. Lessons & Quick Reference", H1),
        hr(BLUE, 1),
        Paragraph("Patterns that emerged from building and operating the quality project:", BODY),
        Spacer(1, 0.2*cm),
    ]

    lessons = [
        ("Separate who analyses from who generates",
         "The DEVELOPER AGENT / Test Generator split means each prompt is focused. "
         "One agent doing both produces worse output at double the latency."),
        ("Never block the pipeline",
         "The webhook must return immediately. All work in BackgroundTasks. "
         "On any failure: post an error comment, log, exit. The team must never be "
         "silently blocked by a quality tool."),
        ("Prompt text belongs in version control",
         "SKILL blocks in skills.md means every prompt change is a git diff. "
         "It goes through code review. The hash in the report footer ties output "
         "quality to the exact prompt version that produced it."),
        ("Existing tests are the best style guide",
         "Fetching real test files from the target repo and injecting them as few-shot examples "
         "produces output that fits the codebase. A generic prompt produces generic tests "
         "that get deleted; tests that look familiar get kept and extended."),
        ("The escape hatch builds trust",
         "R4 (agent-instructions block in the MR description) lets developers add per-MR instructions "
         "without touching any configuration or file. Teams that trust they can steer "
         "a tool are more likely to keep using it."),
        ("Dedup is mandatory at any scale",
         "GitLab retries webhook delivery. Without the _done set, every retry re-runs the "
         "generation and posts a duplicate comment. The fix is one set checked before "
         "any work begins."),
        ("Progressive comments feel responsive",
         "Posting one comment and editing it in-place (rather than posting multiple comments) "
         "keeps the MR thread clean and gives developers live progress without notification noise."),
    ]

    for title, body in lessons:
        items.append(KeepTogether([
            Paragraph(f"&#10003; &nbsp; <b>{title}</b>",
                      S("lt", fontName="Helvetica-Bold", fontSize=10,
                         textColor=TEAL, leading=14, spaceBefore=4)),
            Paragraph(body, S("lb", fontName="Helvetica", fontSize=9.5, textColor=DARK,
                               leading=14, leftIndent=18, spaceAfter=6)),
        ]))

    items.append(hr())
    items.append(Paragraph("Quick reference — file map", H2))

    files_data = [
        ["File", "Purpose", "Who reads it"],
        ["agents/<name>/profile.md", "Identity contract — who, purpose, inputs, outputs",
         "Humans (design review)"],
        ["agents/<name>/rules.md",   "Behavioural constraints — must/must not, with Why",
         "Humans + code (enforced as guards or prompt instructions)"],
        ["agents/<name>/skills.md",  "Capability docs + SKILL blocks (extracted system prompts)",
         "Code (_extract_skill) + Humans"],
        ["app/code_analyzer.py",     "DEVELOPER AGENT — extracts DEVELOPER_SYSTEM, calls Claude",
         "Python runtime"],
        ["app/test_generator.py",    "Test Generator — extracts GHERKIN_SYSTEM + PLAYWRIGHT_SYSTEM",
         "Python runtime"],
        ["app/main.py",              "Pipeline orchestration — webhook routing, dedup, progress updates",
         "Python runtime"],
        ["agents/<name>/feedback-log.jsonl", "Reaction log — thumbs up/down from MR comments",
         "Scheduled job reads it to track generation quality over time"],
    ]
    files_table = Table(files_data, colWidths=[5*cm, 8*cm, 4.5*cm],
                        style=TableStyle([
                            ("BACKGROUND",   (0,0), (-1,0), NAVY),
                            ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
                            ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
                            ("FONTSIZE",     (0,0), (-1,-1), 8.5),
                            ("FONTNAME",     (0,1), (0,-1), "Courier"),
                            ("TEXTCOLOR",    (0,1), (0,-1), BLUE),
                            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT]),
                            ("GRID",         (0,0), (-1,-1), 0.3, BORDER),
                            ("TOPPADDING",   (0,0), (-1,-1), 6),
                            ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                            ("LEFTPADDING",  (0,0), (-1,-1), 8),
                            ("RIGHTPADDING", (0,0), (-1,-1), 8),
                            ("VALIGN",       (0,0), (-1,-1), "TOP"),
                        ]))
    items.append(files_table)
    items.append(Spacer(1, 0.4*cm))

    items.append(callout_box(
        "Every agent directory follows the same three-file convention: "
        "<b>profile.md</b> (contract), <b>rules.md</b> (constraints), <b>skills.md</b> (capability + prompts). "
        "This is what makes agents reviewable, maintainable, and replaceable.",
        bg=colors.HexColor("#F0FDF4"), border_color=TEAL))

    items.append(Spacer(1, 0.3*cm))
    items.append(Paragraph(
        "Built from the quality project — version 1.0.x &nbsp;|&nbsp; "
        "Model: claude-sonnet-4-6 &nbsp;|&nbsp; Framework: FastAPI + GitLab Webhooks",
        S("foot", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#94A3B8"),
           leading=12, alignment=TA_CENTER)))

    return items

# ── Build ─────────────────────────────────────────────────────────────────────
def build():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
        title="Harnessing AI Agents — Profiles, Rules & Skills",
        author="quality project",
        subject="AI Agent Design Patterns",
    )

    story = []
    story.extend(cover())
    story.extend(section_architecture())
    story.extend(section_webhooks_vs_apps())
    story.extend(section_profiles())
    story.extend(section_rules())
    story.extend(section_skills())
    story.extend(section_prompt_assembly())
    story.extend(section_new_agent())
    story.extend(section_reference())

    doc.build(story)
    print(f"Generated: {OUTPUT}")

if __name__ == "__main__":
    build()
