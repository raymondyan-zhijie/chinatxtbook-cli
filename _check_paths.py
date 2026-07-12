import subprocess, os
from pathlib import Path

WORK_DIR = Path("ChinaTextbook_Workspace")

def git(cmd, **kw):
    r = subprocess.run(["git", "-C", str(WORK_DIR)] + cmd,
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, **kw)
    return r

# Check git status
r = git(["status", "--short"])
print(f"Status: {r.stdout[:500]}")

# Check HEAD commit
r = git(["rev-parse", "HEAD"])
print(f"HEAD: {r.stdout.strip()}")

# Check branch
r = git(["branch"])
print(f"Branch: {r.stdout.strip()}")

# Try resetting index
r = git(["read-tree", "--empty"])
print(f"read-tree empty: {r.returncode} {r.stderr[:100]}")

# Try restoring a simple path
r = git(["ls-tree", "-r", "--name-only", "HEAD", "--", "小学/数学/人教版/"])
paths = r.stdout.strip().split("\n")
p = paths[0]

# Try with GIT_TRACE
env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_TRACE": "1"}
r = git(["checkout", "HEAD", "--", p], env=env)
print(f"\nCheckout with trace: {r.returncode}")
print(f"stderr: {r.stderr[:500]}")

# Also check what's in the index
r = git(["ls-files", "--", p])
print(f"\nls-files for path: '{r.stdout.strip()}'")
