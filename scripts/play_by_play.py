"""Turn recent public GitHub activity into sports play-by-play and splice it into README.md."""

import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime

USER = os.environ.get("GH_USER", "yasher3413")
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
MAX_PLAYS = 6
BOT_BRANCH_PREFIXES = ("claude/", "dependabot/", "renovate/", "copilot/")

COLOR = [
    "crowd goes mild.",
    "the rink goes quiet. in a good way.",
    "you cannot teach that.",
    "he's been doing this all season, folks.",
    "the booth is speechless.",
    "somebody check on his sleep schedule.",
    "that one's going on the highlight reel.",
    "textbook. absolutely textbook.",
    "the bench is on its feet.",
    "refs are reviewing it. it stands.",
    "and he didn't even close a tab.",
    "somewhere, a Leafs fan weeps. it's him.",
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
    """Return the play text, or None to skip the event."""
    repo = e["repo"]["name"]
    short = repo.split("/", 1)[-1]
    link = f"[{short}](https://github.com/{repo})"
    p = e.get("payload") or {}
    t = e["type"]

    if short == USER:  # don't narrate edits to this profile repo itself
        return None
    if t == "PushEvent":
        n = p.get("size") or len(p.get("commits") or []) or 0
        return f"{n}-commit drive into {link}" if n > 1 else f"takes a shift in {link}"
    if t == "CreateEvent":
        if p.get("ref_type") == "repository":
            return f"signs {link} to an entry-level contract"
        if p.get("ref_type") == "branch" and not str(p.get("ref", "")).startswith(BOT_BRANCH_PREFIXES):
            return f"draws up a new play, `{p.get('ref')}`, in {link}"
        if p.get("ref_type") == "tag":
            return f"tags `{p.get('ref')}` in {link}"
    if t == "PullRequestEvent":
        pr = p.get("pull_request") or {}
        num = pr.get("number", "")
        if p.get("action") == "closed" and pr.get("merged"):
            return f"scores. PR #{num} merged in {link}"
        if p.get("action") == "opened":
            return f"throws deep, opens PR #{num} in {link}"
    if t == "IssuesEvent" and p.get("action") in ("opened", "closed"):
        num = (p.get("issue") or {}).get("number", "")
        if p["action"] == "opened":
            return f"takes a penalty, issue #{num} in {link}"
        return f"kills the penalty, closes issue #{num} in {link}"
    if t == "WatchEvent":
        return f"scouting {link}"
    if t == "ForkEvent":
        return f"trades for {link}"
    if t == "ReleaseEvent" and p.get("action") == "published":
        return f"raises a banner: {link} `{(p.get('release') or {}).get('tag_name', '')}`"
    if t == "PublicEvent":
        return f"{link} goes public. presser at four"
    return None


def update_counters():
    """Keep the misery counters on the whiteboard current."""
    path = os.path.join(os.path.dirname(__file__), "..", "assets", "rink.svg")
    if not os.path.exists(path):
        return
    today = date.today()
    leafs = f"{(today - date(1967, 5, 2)).days:,}"  # last Stanley Cup
    cowboys = f"{(today - date(1996, 1, 14)).days:,}"  # last NFC Championship Game
    with open(path, encoding="utf-8") as f:
        svg = f.read()
    new = re.sub(r'(<tspan id="leafs-days">)[^<]*', lambda m: m.group(1) + leafs, svg)
    new = re.sub(r'(<tspan id="cowboys-days">)[^<]*', lambda m: m.group(1) + cowboys, new)
    new = re.sub(r"Days since a Leafs Cup: [\d,]+", f"Days since a Leafs Cup: {leafs}", new)
    new = re.sub(r"NFC title game: [\d,]+", f"NFC title game: {cowboys}", new)
    if new != svg:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        print("counters updated")


def main():
    update_counters()
    try:
        events = fetch_events()
    except Exception as exc:  # network hiccup: leave the README alone
        print(f"could not fetch events: {exc}", file=sys.stderr)
        return

    plays, seen = [], set()
    for e in events:
        text = describe(e)
        if not text:
            continue
        key = (e["type"], e["repo"]["name"], text)
        if key in seen:  # collapse back-to-back identical plays
            continue
        seen.add(key)
        when = datetime.strptime(e["created_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%b %d").upper()
        quip = COLOR[int(hashlib.md5(e["id"].encode()).hexdigest(), 16) % len(COLOR)]
        plays.append(f"- `{when}` {text}. *{quip}*")
        if len(plays) >= MAX_PLAYS:
            break

    if not plays:
        plays = ["- *quiet in the booth. he is probably watching game tape (doomscrolling).*"]

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
