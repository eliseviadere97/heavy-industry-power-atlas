"""Step D of the pipeline: assemble the interactive map into one self-contained HTML file.

  site/index.html        full HTML document for GitHub Pages (deployed by .github/workflows/deploy.yml)
  outputs/artifact.html  the same page as a fragment, ready to republish as a Claude artifact

The page embeds data/processed/data.json, config/model_config.json and src/model/*.js; d3 and
javascript-lp-solver load from public CDNs at pinned versions.

Usage:  python src/site/build_site.py [--repo owner/name]
        (in GitHub Actions the repository is read from $GITHUB_REPOSITORY)
"""
import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="Interactive EU27 map: where a social planner would put Europe's decarbonised heavy industry, each plant with its own least-cost local power mix.">
<style>:root{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
"""


def fill(template, repo):
    t = re.sub(r"^<!--.*?-->\s*", "", template, count=1, flags=re.S)      # drop the developer comment
    data = (ROOT / "data" / "processed" / "data.json").read_text(encoding="utf-8").replace("</", "<\\/")
    cfg = json.loads((ROOT / "config" / "model_config.json").read_text(encoding="utf-8"))
    config = json.dumps({"model": cfg["model"]}, ensure_ascii=False).replace("</", "<\\/")
    mix = (ROOT / "src" / "model" / "mix.js").read_text(encoding="utf-8")
    plan = (ROOT / "src" / "model" / "plan.js").read_text(encoding="utf-8")
    repo_line = (f'<p><b>Code and data.</b> Raw data, sources, data-preparation and optimisation code: '
                 f'<a href="https://github.com/{repo}" target="_blank" rel="noopener">github.com/{repo}</a>.</p>') if repo else ""
    for key, val in [("__REPO_LINE__", repo_line), ("__CONFIG__", config), ("__MIX__", mix), ("__PLAN__", plan), ("__DATA__", data)]:
        assert t.count(key) == 1, f"placeholder {key} must appear exactly once"
        t = t.replace(key, val)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="owner/name of the GitHub repository")
    args = ap.parse_args()
    page = fill((ROOT / "src" / "site" / "template.html").read_text(encoding="utf-8"), args.repo)
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
