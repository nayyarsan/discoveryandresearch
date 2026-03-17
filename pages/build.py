from datetime import datetime, timezone
from schemas.repo import Repo


def build_index_html(repos: list[Repo]) -> str:
    generated = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = ""
    for r in repos:
        rows += f"""
        <tr>
          <td><a href="{r.url}" target="_blank">{r.name}</a></td>
          <td>{r.description}</td>
          <td>{r.language}</td>
          <td>{r.stars:,}</td>
          <td>{r.license}</td>
          <td>{r.why_notable}</td>
          <td>{r.source}</td>
        </tr>"""

    empty_msg = "" if repos else "<p>No repos discovered yet.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Repo Discovery</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }}
    h1 {{ font-size: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ text-align: left; padding: 0.5rem; border-bottom: 1px solid #eee; }}
    th {{ background: #f5f5f5; font-weight: 600; }}
    a {{ color: #0366d6; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .meta {{ color: #666; font-size: 0.85rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <h1>AI Repo Discovery</h1>
  <p class="meta">Last updated: {generated} — {len(repos)} repos discovered</p>
  {empty_msg}
  {"<table><thead><tr><th>Repo</th><th>Description</th><th>Language</th><th>Stars</th><th>License</th><th>Why Notable</th><th>Source</th></tr></thead><tbody>" + rows + "</tbody></table>" if repos else ""}
</body>
</html>"""
