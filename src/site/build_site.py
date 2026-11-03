"""Step D of the pipeline: assemble the interactive map into one self-contained HTML file.

  site/index.html        full HTML document for GitHub Pages (deployed by .github/workflows/deploy.yml)
  outputs/artifact.html  the same page as a fragment, ready to republish as a Claude artifact

The page embeds data/processed/data.json, config/model_config.json and src/model/*.js; d3 and
javascript-lp-solver load from public CDNs at pinned versions.

Usage:  python src/site/build_site.py [--repo owner/name]
        (in GitHub Actions the repository is read from $GITHUB_REPOSITORY)
"""
import argparse
import base64
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="Interactive map of the EU27, Norway, Switzerland and the UK: where a social planner would put Europe's decarbonised heavy industry, each plant with its own least-cost local power mix.">
<style>:root{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
"""


def fill(template, repo):
    t = re.sub(r"^<!--.*?-->\s*", "", template, count=1, flags=re.S)      # drop the developer comment
    data = (ROOT / "data" / "processed" / "data.json").read_text(encoding="utf-8").replace("</", "<\\/")
    cfg = json.loads((ROOT / "config" / "model_config.json").read_text(encoding="utf-8"))
    config = json.dumps({"model": cfg["model"]}, ensure_ascii=False).replace("</", "<\\/")
    mix = (ROOT / "src" / "model" / "mix.js").read_text(encoding="utf-8")
    plan = (ROOT / "src" / "model" / "plan.js").read_text(encoding="utf-8")
    mark = ('<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>')
    repo_button = (f'<a class="ghlink" href="https://github.com/{repo}" target="_blank" rel="noopener">{mark}Code and data on GitHub</a>') if repo else ""
    logo = "data:image/png;base64," + base64.b64encode((ROOT / "src" / "site" / "cer-logo.png").read_bytes()).decode()
    for key, val in [("__CER_LOGO__", logo), ("__REPO_BUTTON__", repo_button), ("__CONFIG__", config), ("__MIX__", mix), ("__PLAN__", plan), ("__DATA__", data)]:
        assert t.count(key) == 1, f"placeholder {key} must appear exactly once"
        t = t.replace(key, val)
    return t


def git_remote_repo():
    """owner/name of the GitHub 'origin' remote, or "" if there is none."""
    try:
        url = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="owner/name of the GitHub repository")
    args = ap.parse_args()
    page = fill((ROOT / "src" / "site" / "template.html").read_text(encoding="utf-8"), args.repo or git_remote_repo())
    split = page.index('<div class="app">')
    site = ROOT / "site"
    site.mkdir(exist_ok=True)
    (site / "index.html").write_text(HEAD + page[:split] + "</head>\n<body>\n" + page[split:] + "\n</body>\n</html>\n", encoding="utf-8")
    (site / ".nojekyll").write_text("")
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "artifact.html").write_text(page, encoding="utf-8")
    print(f"Site built: site/index.html ({(site / 'index.html').stat().st_size / 1e3:,.0f} kB); outputs/artifact.html")


if __name__ == "__main__":
    main()
