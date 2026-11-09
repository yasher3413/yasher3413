"""Turn recent public GitHub activity into sports play-by-play and splice it into README.md."""

import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime

USER = os.environ.get("GH_USER", "yasher3413")
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
MAX_PLAYS = 6

COLOR = [
    "crowd goes mild.",
    "you cannot teach that.",
    "he's been doing this all season, folks.",
    "the booth is speechless.",
    "somebody check on his sleep schedule.",
    "that one's going on the highlight reel.",
    "textbook. absolutely textbook.",
    "the bench is on its feet.",
    "refs are reviewing it. it stands.",
    "and he didn't even close a tab.",
]


def fetch_events():
    req = urllib.request.Request(
        f"https://api.github.com/users/{USER}/events/public?per_page=50",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "play-by-play"},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def describe(e):
    """Return (emoji, play text) or None to skip."""
    repo = e["repo"]["name"]
    short = repo.split("/", 1)[-1]
    link = f"[{short}](https://github.com/{repo})"
    p = e.get("payload") or {}
    t = e["type"]

    if t == "PushEvent":
        n = p.get("size") or len(p.get("commits") or []) or 0
        if n > 1:
            return "🏈", f"**{n}-commit drive** into {link}"
        return "🏈", f"**quick push** into {link}"
    if t == "CreateEvent":
        if p.get("ref_type") == "repository":
            return "📝", f"**signs a rookie:** {link} joins the roster"
        if p.get("ref_type") == "branch":
            return "🔀", f"**trick play:** new branch `{p.get('ref')}` on {link}"
        if p.get("ref_type") == "tag":
            return "🏷️", f"**tags `{p.get('ref')}`** on {link}"
    if t == "PullRequestEvent":
        pr = p.get("pull_request") or {}
        num = pr.get("number", "")
        if p.get("action") == "closed" and pr.get("merged"):
            return "🙌", f"**touchdown!** PR #{num} merged in {link}"
        if p.get("action") == "opened":
            return "🎯", f"**throws deep:** opens PR #{num} on {link}"
    if t == "IssuesEvent" and p.get("action") in ("opened", "closed"):
        verb = "flags a foul" if p["action"] == "opened" else "clears the penalty"
        return "🚩", f"**{verb}:** issue #{(p.get('issue') or {}).get('number', '')} on {link}"
    if t == "WatchEvent":
        return "👀", f"**scouting the competition:** stars {link}"
    if t == "ForkEvent":
        return "🔁", f"**trade!** forks {link}"
    if t == "ReleaseEvent" and p.get("action") == "published":
        tag = (p.get("release") or {}).get("tag_name", "")
        return "🏆", f"**ships it:** release `{tag}` of {link}"
    if t == "PublicEvent":
        return "📣", f"**press conference:** {link} goes public"
    return None


def main():
    try:
        events = fetch_events()
    except Exception as exc:  # network hiccup: leave the README alone
        print(f"could not fetch events: {exc}", file=sys.stderr)
        return

    plays, seen = [], set()
    for e in events:
        d = describe(e)
        if not d:
            continue
        emoji, text = d
        key = (e["type"], e["repo"]["name"], text)
        if key in seen:  # collapse back-to-back identical plays
            continue
        seen.add(key)
        when = datetime.strptime(e["created_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%b %d").upper()
        quip = COLOR[int(hashlib.md5(e["id"].encode()).hexdigest(), 16) % len(COLOR)]
        plays.append(f"- `{when}` {emoji} {text}. *{quip}*")
        if len(plays) >= MAX_PLAYS:
            break

    if not plays:
        plays = ["- 🟠 *quiet in the booth. the player is probably watching game tape (doomscrolling).*"]

    with open(README, encoding="utf-8") as f:
        readme = f.read()
    block = "<!--PBP:START-->\n" + "\n".join(plays) + "\n<!--PBP:END-->"
    new = re.sub(r"<!--PBP:START-->.*?<!--PBP:END-->", lambda _: block, readme, flags=re.S)
    if new != readme:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)
        print("README updated")
    else:
        print("no change")


if __name__ == "__main__":
    main()
