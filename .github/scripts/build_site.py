"""
把 README.md 渲染成静态站点，供 GitHub Pages 部署。

本地预览：
    python3 .github/scripts/build_site.py --output _site
    python3 -m http.server --directory _site
"""

import argparse
import re
import shutil
from pathlib import Path

import markdown

PROJECT_URL = 'https://github.com/luskyle/antelope'

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<style>
:root {{
  --fg: #1f2328;
  --bg: #ffffff;
  --muted: #59636e;
  --border: #d1d9e0;
  --code-bg: #f6f8fa;
  --accent: #0969da;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --fg: #e6edf3;
    --bg: #0d1117;
    --muted: #9198a1;
    --border: #3d444d;
    --code-bg: #161b22;
    --accent: #4493f8;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 2.5rem 1.25rem;
  background: var(--bg);
  color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC",
               "Microsoft YaHei", Helvetica, Arial, sans-serif;
  font-size: 16px;
  line-height: 1.7;
}}
.page {{ max-width: 860px; margin: 0 auto; }}
h1, h2, h3 {{ line-height: 1.3; margin: 2rem 0 1rem; }}
h1 {{ font-size: 2rem; border-bottom: 1px solid var(--border); padding-bottom: .5rem; }}
h2 {{ font-size: 1.4rem; border-bottom: 1px solid var(--border); padding-bottom: .3rem; }}
a {{ color: var(--accent); }}
img {{ max-width: 100%; height: auto; }}
code {{
  background: var(--code-bg);
  border-radius: 4px;
  padding: .15em .35em;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, monospace;
  font-size: .9em;
}}
pre {{
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .9rem 1rem;
  overflow-x: auto;
}}
pre code {{ background: none; padding: 0; }}
.table-wrap {{ overflow-x: auto; margin: 1rem 0; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid var(--border); padding: .45rem .7rem; text-align: left; }}
th {{ background: var(--code-bg); }}
footer {{
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: .9rem;
}}
</style>
</head>
<body>
<div class="page">
<main>
{content}
</main>
<footer>
<a href="{project_url}">{project_url}</a>
</footer>
</div>
</body>
</html>
"""


def renderMarkdown(readme_path:Path):
    """把 README 的 markdown 正文渲染成 html 片段"""
    text = readme_path.read_text(encoding='utf-8')
    html = markdown.markdown(text, extensions=['extra', 'sane_lists'])
    return html.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')


def readTitle(readme_path:Path):
    """取 README 首个一级标题作为页面标题"""
    for line in readme_path.read_text(encoding='utf-8').splitlines():
        if line.startswith('# '):
            return line[2:].strip()
    return readme_path.stem


def buildSite(readme_path:Path, output_dir:Path, project_url:str):
    content = renderMarkdown(readme_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'index.html').write_text(
        PAGE_TEMPLATE.format(title=readTitle(readme_path), content=content, project_url=project_url),
        encoding='utf-8')

    images_dir = readme_path.parent / 'images'
    if images_dir.is_dir():
        shutil.copytree(images_dir, output_dir / 'images', dirs_exist_ok=True)

    return output_dir / 'index.html'


def main():
    parser = argparse.ArgumentParser(description='把 README.md 渲染成静态站点')
    parser.add_argument('--readme', default='README.md', type=Path, help='markdown 源文件')
    parser.add_argument('--output', default='_site', type=Path, help='站点输出目录')
    parser.add_argument('--project-url', default=PROJECT_URL, help='页脚展示的仓库地址')
    args = parser.parse_args()

    index = buildSite(args.readme, args.output, args.project_url)
    print(f'已生成 {index}')


if __name__ == '__main__':
    main()