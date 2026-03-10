"""
GitHub の最新オープン Issue を取得し、context_issue.md を生成する。
Cursor が Issue を元に修正する際のコンテキストとして利用する。
"""
import os
import sys

try:
    import requests
except ImportError:
    print("requests が必要です: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

# リポジトリ: 環境変数 GITHUB_REPOSITORY (owner/repo) またはデフォルト
REPO = os.getenv("GITHUB_REPOSITORY", "kamereonnoir/gadget_auto_ai")
GITHUB_API = "https://api.github.com"


def fetch_latest_issue() -> dict | None:
    """オープンな Issue のうち、最新1件を取得する。"""
    url = f"{GITHUB_API}/repos/{REPO}/issues"
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {"state": "open", "sort": "created", "direction": "desc", "per_page": 1}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    issue = data[0]
    if "pull_request" in issue:
        return None
    return issue


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    out_path = os.path.join(project_root, "context_issue.md")

    issue = fetch_latest_issue()
    if not issue:
        content = "# Current Issue\n\n(オープンな Issue はありません)\n"
    else:
        title = issue.get("title", "")
        body = issue.get("body") or ""
        content = f"""# Current Issue

Title:
{title}

Description:
{body}
"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
