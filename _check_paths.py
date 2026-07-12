import subprocess, os
from pathlib import Path

WORK_DIR = Path("ChinaTextbook_Workspace")

r = subprocess.run(
    ["git", "-C", str(WORK_DIR), "ls-tree", "-r", "--name-only", "HEAD", "--", "小学/数学/人教版/"],
    capture_output=True, text=True, encoding="utf-8",
    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
)
path = r.stdout.strip().split("\n")[0]

# Test different commands to materialize the file
env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

tests = [
    ["restore", "--source=HEAD", "--worktree", path],
    ["checkout", "HEAD", "--", path],
    ["checkout", path],
    ["show", f"HEAD:{path}"],
]
for cmd in tests:
    r = subprocess.run(
        ["git", "-C", str(WORK_DIR)] + cmd,
        capture_output=True, encoding="utf-8", errors="replace",
        env=env,
    )
    ok = "OK" if r.returncode == 0 else "FAIL"
    print(f"{ok} git {' '.join(cmd[:3])}: {r.stderr[:100]}")

# Check if file now exists
fp = WORK_DIR / path
print(f"\nFile on disk: {fp.exists()}")
if fp.exists():
    print(f"  Size: {fp.stat().st_size}")
