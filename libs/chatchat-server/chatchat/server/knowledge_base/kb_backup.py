"""
知识库源文件自动云端备份(私有 git 仓库)。

当用户通过 WebUI/API 向知识库上传、更新或删除文件后，backup_files() 会重新扫描该知识库的 content 目录，把完整文件树镜像到本地备份仓库并 commit+push 到配置的私有远程仓库。

配置全部来自环境变量(见 .env.example / docker-compose.win.yaml):
    KB_BACKUP_ENABLED        是否开启,默认 false
    KB_BACKUP_REMOTE_URL     私有备份仓库 HTTPS 地址(不含 token)
    KB_BACKUP_TOKEN          细粒度 PAT,仅授权该仓库 Contents 读写;留空仅本地测试
    KB_BACKUP_BRANCH         备份分支,默认 main
    KB_BACKUP_REPO_PATH      本地备份 git 仓库路径,默认 <CHATCHAT_ROOT>/kb_backup_repo
    KB_BACKUP_COMMIT_AUTHOR_NAME / _EMAIL  提交作者,默认 MDT / mdt@local

安全约定:
    - token 只通过 push 子进程 argv 的临时 URL 使用,不写入 .git/config;
    - origin 只保存不含 token 的裸地址;
    - 所有可能进入日志的文本都经 _redact() 脱敏。
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple
from urllib.parse import quote, urlsplit, urlunsplit

from chatchat.utils import build_logger

logger = build_logger()


class BackupError(Exception):
    pass


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def backup_enabled() -> bool:
    return _env_bool("KB_BACKUP_ENABLED", False)


def _redact(text: str, token: str) -> str:
    if not token or not text:
        return text
    return (
        text.replace(token, "***")
        .replace(quote(token, safe=""), "***")
        .replace(quote(token, safe="!$&'()*+,;=:@"), "***")
    )


def _git_env() -> dict:
    env = dict(os.environ)
    env.update(
        {
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
            "GIT_TERMINAL_PROMPT": "0",  # 缺凭据时快速失败,不挂起等待输入
        }
    )
    return env


def _run_git(args: List[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_git_env(),
        )
    except subprocess.TimeoutExpired as e:
        raise BackupError(f"git 命令超时({timeout}s): {' '.join(args[:2])}") from e
    except FileNotFoundError as e:
        raise BackupError("git 未安装") from e


def _embed_token(remote_url: str, token: str) -> str:
    """把 token 嵌入 http(s) 地址的 netloc,用于本次 push;非 http(s) 原样返回。"""
    if not token:
        return remote_url
    parts = urlsplit(remote_url)
    if parts.scheme in ("http", "https"):
        host = parts.hostname or ""
        netloc = f"x-access-token:{quote(token, safe='')}@{host}"
        if parts.port:
            netloc += f":{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return remote_url


def ensure_repo(
    repo_path: Path,
    branch: str,
    remote_url: str,
    author_name: str,
    author_email: str,
) -> None:
    """幂等地在 repo_path 初始化(或复用)本地备份仓库。"""
    repo_path.mkdir(parents=True, exist_ok=True)
    if not (repo_path / ".git").exists():
        r = _run_git(["init", "-b", branch], cwd=repo_path)
        if r.returncode != 0:
            # 兼容不支持 -b 的旧 git
            r = _run_git(["init"], cwd=repo_path)
            if r.returncode != 0:
                raise BackupError("git init 失败")
            r = _run_git(["symbolic-ref", "HEAD", f"refs/heads/{branch}"], cwd=repo_path)
            if r.returncode != 0:
                raise BackupError("设置默认分支失败")

    for cmd in (
        ["config", "user.name", author_name or "MDT"],
        ["config", "user.email", author_email or "mdt@local"],
    ):
        r = _run_git(cmd, cwd=repo_path)
        if r.returncode != 0:
            raise BackupError(f"git 配置失败: {r.stderr.strip()}")

    # origin 只存不含 token 的裸地址
    r = _run_git(["remote", "get-url", "origin"], cwd=repo_path)
    if r.returncode == 0:
        r = _run_git(["remote", "set-url", "origin", remote_url], cwd=repo_path)
    else:
        r = _run_git(["remote", "add", "origin", remote_url], cwd=repo_path)
    if r.returncode != 0:
        raise BackupError(f"配置 origin 失败: {r.stderr.strip()}")


def _load_config() -> dict:
    from chatchat.settings import Settings  # 延迟导入,避免模块加载时的循环依赖

    repo_path = os.environ.get("KB_BACKUP_REPO_PATH", "").strip()
    if not repo_path:
        repo_path = str(Settings.CHATCHAT_ROOT / "kb_backup_repo")
    return {
        "remote_url": os.environ.get("KB_BACKUP_REMOTE_URL", "").strip(),
        "token": os.environ.get("KB_BACKUP_TOKEN", "").strip(),
        "branch": (os.environ.get("KB_BACKUP_BRANCH", "main").strip() or "main"),
        "repo_path": Path(repo_path),
        "author_name": os.environ.get("KB_BACKUP_COMMIT_AUTHOR_NAME", "MDT").strip(),
        "author_email": os.environ.get("KB_BACKUP_COMMIT_AUTHOR_EMAIL", "mdt@local").strip(),
    }


def backup_files(kb_name: str, filenames: List[str]) -> Tuple[bool, str]:
    """把指定知识库完整镜像到私有 git 仓库并 push。

    filenames 仅保留兼容旧调用方；每次执行都会重新扫描知识库 content 目录，
    因此新增、修改和删除都会同步到云端。
    """
    if not backup_enabled():
        return True, "云端备份未启用"

    from chatchat.settings import Settings  # 延迟导入,避免模块加载时的循环依赖
    from chatchat.server.knowledge_base.utils import get_file_path, list_files_from_folder

    cfg = _load_config()
    if not cfg["remote_url"]:
        return False, "未配置 KB_BACKUP_REMOTE_URL"

    token = cfg["token"]
    try:
        ensure_repo(
            cfg["repo_path"],
            cfg["branch"],
            cfg["remote_url"],
            cfg["author_name"],
            cfg["author_email"],
        )
    except BackupError as e:
        logger.error(f"知识库备份初始化失败: {e}")
        return False, str(e)

    kb_root = Path(Settings.basic_settings.KB_ROOT_PATH)
    current_files = list_files_from_folder(kb_name)
    kb_repo_root = cfg["repo_path"] / kb_name

    # 以本地 content 目录为准，复制全部当前文件。
    for name in current_files:
        src = Path(get_file_path(kb_name, name))
        if not src.is_file():
            continue
        dst = kb_repo_root / Path(name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            logger.error(f"复制备份文件失败 {name}: {e}")
            return False, f"复制备份文件失败: {name}"

    # 删除云端镜像中本地已经不存在的文件。
    current_set = {Path(name).as_posix() for name in current_files}
    if kb_repo_root.is_dir():
        for path in sorted(kb_repo_root.rglob("*"), reverse=True):
            if path.is_file() and path.relative_to(kb_repo_root).as_posix() not in current_set:
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass

    rel_kb = kb_repo_root.relative_to(cfg["repo_path"]).as_posix()
    r = _run_git(["add", "-A", "--", rel_kb], cwd=cfg["repo_path"])
    if r.returncode != 0:
        return False, f"git add 失败: {_redact(r.stderr, token)}"

    # 同名同内容时不产生空 commit。
    r = _run_git(["diff", "--cached", "--quiet"], cwd=cfg["repo_path"])
    if r.returncode == 0:
        return True, f"云端已是最新({len(current_files)} 个文件)"
    if r.returncode != 1:
        return False, f"git diff 失败: {_redact(r.stderr, token)}"

    msg = f"sync {kb_name}: {len(current_files)} file(s)"
    r = _run_git(["commit", "-m", msg], cwd=cfg["repo_path"])
    if r.returncode != 0:
        return False, f"git commit 失败: {_redact(r.stderr, token)}"

    push_url = _embed_token(cfg["remote_url"], token)
    r = _run_git(
        ["push", push_url, f"HEAD:refs/heads/{cfg['branch']}"],
        cwd=cfg["repo_path"],
        timeout=180,
    )
    if r.returncode != 0:
        return False, f"git push 失败: {_redact(r.stderr, token)}"

    return True, f"已完整同步 {len(current_files)} 个文件到云端"
