"""Git client extracted from v1.0.

Wraps all git operations with retry logic, fail-closed semantics,
and credential redaction. Simplified for v1.1 single-source (GitHub only).

Source: v1.0 lines 344-456, 565-602, 1188-1247.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from chinatxtbook.config import WORK_DIR, GITHUB_REPO, VERSION
from chinatxtbook.utils.format import safe_error
from chinatxtbook.utils.platform import is_interrupted

# Transient error patterns for retry
_TRANSIENT = (
    "could not resolve",
    "timed out",
    "timeout",
    "connection",
    "early eof",
    "rpc failed",
    "hung up",
    "unable to access",
    "503",
    "502",
    "500",
    "curl",
)


class GitClient:
    """Git operations wrapper with retry, fail-closed, and credential safety.

    Source: v1.0 git() function (L349-378) + related git_* functions.
    """

    def __init__(
        self,
        work_dir: Path = WORK_DIR,
        repo_url: str = GITHUB_REPO,
        log_callback: Optional[Callable] = None,
    ):
        self.work_dir = work_dir
        self.repo_url = repo_url
        self.log = log_callback or (lambda msg, level="INFO": None)

    def run(
        self,
        args: list,
        retry: int = 3,
        allow_fetch: bool = False,
        input_text: Optional[str] = None,
    ) -> tuple:
        """Execute a git command with retry logic.

        Source: v1.0 lines 349-378.
        """
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        if not allow_fetch:
            env["GIT_NO_LAZY_FETCH"] = "1"

        last_err = ""
        for attempt in range(1, retry + 1):
            if is_interrupted():
                return False, "", "interrupted"
            try:
                r = subprocess.run(
                    ["git"] + args,
                    cwd=str(self.work_dir),
                    capture_output=True,
                    text=True,
                    input=input_text,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )
            except FileNotFoundError:
                self.log("未找到 git 命令，请先安装 Git", "ERROR")
                return False, "", "git not found"

            if r.returncode == 0:
                return True, r.stdout, r.stderr

            last_err = r.stderr.strip()
            transient = any(p in last_err.lower() for p in _TRANSIENT)
            self.log(
                f"  git {' '.join(args[:2])} 失败"
                f"({attempt}/{retry}{'' if transient else ', 非网络错误不重试'}): "
                f"{safe_error(last_err, 200)}",
                "WARN",
            )
            if not transient or attempt == retry:
                break
            time.sleep(3 * attempt)

        return False, "", last_err

    def configure_repo(self):
        """Set git config for the workspace. Source: v1.0 lines 380-383."""
        self.run(["config", "core.quotepath", "false"], retry=1)
        if sys.platform == "win32":
            self.run(["config", "core.longpaths", "true"], retry=1)

    def is_repo_valid(self) -> bool:
        """Check if workspace has a valid git repo. Source: v1.0 line 398."""
        return (self.work_dir / ".git").exists() and self.get_head_commit() is not None

    def get_head_commit(self) -> Optional[str]:
        """Get HEAD commit SHA. Source: v1.0 lines 394-396."""
        ok, out, _ = self.run(["rev-parse", "HEAD"], retry=1)
        return out.strip() if ok else None

    def get_origin_url(self) -> Optional[str]:
        """Get origin remote URL. Source: v1.0 lines 401-403."""
        ok, out, _ = self.run(["remote", "get-url", "origin"], retry=1)
        return out.strip() if ok else None

    def ls_tree(self, path_prefix: str = "", recursive: bool = False):
        """List files in git tree. Returns None on git failure, [] on empty.
        Source: v1.0 lines 385-392, 1249-1253."""
        args = ["ls-tree"]
        if recursive:
            args.append("-r")
        args.extend(["--name-only", "HEAD"])
        if path_prefix:
            args.extend(["--", path_prefix])
        ok, out, _ = self.run(args, retry=1)
        if not ok:
            return None  # fail-closed: distinguish error from empty
        return [line.strip() for line in out.strip().split("\n") if line.strip()]

    def path_exists_in_tree(self, path: str) -> bool:
        """Check if a directory exists in git tree. Source: v1.0 lines 405-407."""
        ok, out, _ = self.run(
            ["ls-tree", "-d", "--name-only", "HEAD", "--", path.rstrip("/")],
            retry=1,
        )
        return ok and bool(out.strip())

    def detect_default_branch(self, state: dict) -> str:
        """Detect default branch (master/main). Source: v1.0 lines 409-428."""
        if state.get("default_branch"):
            return state["default_branch"]

        branch = None
        ok, out, _ = self.run(
            ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], retry=1
        )
        if ok and "/" in out.strip():
            branch = out.strip().split("/", 1)[1]
        if not branch:
            for cand in ("master", "main"):
                ok, _, _ = self.run(
                    ["rev-parse", "--verify", "--quiet", f"origin/{cand}"], retry=1
                )
                if ok:
                    branch = cand
                    break
        if not branch:
            branch = "master"
            self.log("无法探测默认分支，回退为 master", "WARN")

        state["default_branch"] = branch
        return branch

    def clone(self, repo_url: str = None) -> bool:
        """Blobless clone of the repository. Source: v1.0 lines 1101-1130."""
        url = repo_url or self.repo_url
        if (self.work_dir / ".git").exists():
            if self.is_repo_valid():
                self.log("仓库骨架已就绪，跳过克隆", "OK")
                return True
            self.log(
                "检测到不完整的 .git（上次克隆可能中断）。"
                f"请删除 {self.work_dir} 目录后重新运行。",
                "ERROR",
            )
            return False

        self.log("━━━ STEP 1: 轻量克隆（仅提交与目录树，不下载 PDF） ━━━", "STEP")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.log("  git clone --filter=blob:none --no-checkout", "DATA")

        ok, _, err = self.run(
            ["clone", "--filter=blob:none", "--no-checkout", url, "."],
            allow_fetch=True,
        )
        if not ok:
            self.log(
                f"克隆失败: {safe_error(err, 200)}，请检查网络或代理后重试",
                "ERROR",
            )
            return False
        if not self.is_repo_valid():
            self.log(
                "克隆后仓库校验失败（rev-parse HEAD 不可用），"
                f"请删除 {self.work_dir} 目录后重试",
                "ERROR",
            )
            return False

        self.configure_repo()
        self.log("  克隆完成（目录树已就绪）", "OK")
        return True

    def sparse_checkout(self, paths: list[str]) -> bool:
        """Execute sparse-checkout for selected paths. Source: v1.0 lines 1206-1221."""
        ok, _, err = self.run(
            ["sparse-checkout", "set", "--no-cone", "--stdin"],
            retry=1,
            input_text="\n".join(paths) + "\n",
        )
        if not ok:
            self.log(f"sparse-checkout set 失败: {safe_error(err)}", "ERROR")
            return False

        ok, _, err = self.run(
            ["sparse-checkout", "reapply"], retry=1, allow_fetch=True
        )
        if not ok:
            self.log(f"sparse-checkout reapply 失败: {safe_error(err)}", "ERROR")
            return False
        return True

    def checkout(self, branch: str) -> bool:
        """Checkout branch (downloads selected files). Source: v1.0 lines 1217-1221."""
        self.log(
            f"  git checkout {branch}（下载选定文件，体积大时请耐心等待）...", "DATA"
        )
        ok, _, err = self.run(["checkout", branch], allow_fetch=True)
        if not ok:
            self.log(f"checkout 失败: {safe_error(err)}", "ERROR")
            return False
        return True

    def restore_files(self, file_paths: list[str]) -> bool:
        """Restore missing files from git. Source: v1.0 lines 1324-1337."""
        self.log(
            f"检测到 {len(file_paths)} 个文件需从仓库恢复...", "WARN"
        )
        ok_all = True
        for i in range(0, len(file_paths), 50):
            batch = file_paths[i : i + 50]
            ok, _, err = self.run(
                ["restore", "--source=HEAD", "--worktree", "--"] + batch,
                allow_fetch=True,
            )
            if not ok:
                self.log(f"  restore 失败: {safe_error(err)}", "ERROR")
                ok_all = False
        return ok_all

    def diff_names(self, old: str, new: str) -> tuple:
        """Run git diff --name-only. Source: v1.0 line 439."""
        return self.run(["diff", "--name-only", old, new], retry=1)

    def fetch(self, branch: str) -> bool:
        """Fetch from origin. Source: v1.0 lines 1498-1501."""
        ok, _, err = self.run(["fetch", "origin", branch], allow_fetch=True)
        if not ok:
            self.log(f"fetch 失败: {safe_error(err)}", "ERROR")
            return False
        return True

    def merge_ff(self, branch: str) -> bool:
        """Fast-forward merge. Source: v1.0 lines 1507-1510."""
        ok, _, err = self.run(
            ["merge", "--ff-only", f"origin/{branch}"], allow_fetch=True
        )
        if not ok:
            self.log(f"更新失败: {safe_error(err)}", "ERROR")
            return False
        return True

    def rev_parse(self, ref: str) -> Optional[str]:
        """Get commit SHA for a ref. Source: v1.0 line 1502."""
        ok, out, _ = self.run(["rev-parse", ref], retry=1)
        return out.strip() if ok else None

    def get_remote_sizes(self, ref: str) -> tuple:
        """Fetch directory/file sizes from GitHub Trees API.

        Source: v1.0 lines 568-602, simplified for GitHub-only.
        """
        from chinatxtbook.core.manifest import SPLIT_RE

        m = re.match(
            r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
            re.sub(r"://[^/@\s]+@", "://", self.repo_url or ""),
        )
        if not m:
            return None, None, False

        owner, name = m.groups()
        api = (
            f"https://api.github.com/repos/{owner}/{name}/git/trees/{ref}"
            "?recursive=1"
        )
        headers = {
            "User-Agent": f"textbook-tool/{VERSION}",
            "Accept": "application/vnd.github+json",
        }

        try:
            req = urllib.request.Request(api, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.log(f"  目录大小 API 获取失败: {e}", "WARN")
            return None, None, False

        tree = data.get("tree") or []
        truncated = bool(data.get("truncated"))
        dir_sizes, file_sizes = {}, {}

        for ent in tree:
            if ent.get("type") != "blob":
                continue
            sz = int(ent.get("size") or 0)
            p = ent.get("path", "")
            if SPLIT_RE.match(os.path.basename(p)):
                file_sizes[p] = sz
            parts = p.split("/")
            for depth in range(1, min(len(parts), 3)):
                prefix = "/".join(parts[:depth])
                dir_sizes[prefix] = dir_sizes.get(prefix, 0) + sz

        return dir_sizes, file_sizes, truncated
