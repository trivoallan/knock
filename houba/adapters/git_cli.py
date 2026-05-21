"""Wrapper subprocess autour de git (clone, commit, push, tag, rev-parse)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from houba.errors import GitError


class GitCliAdapter:
    def __init__(self, binary: str | None = None) -> None:
        # Résolution différée : on valide seulement si binary explicite est fourni.
        # La résolution PATH se fait au premier appel (lazy) pour ne pas bloquer
        # la construction du Container dans des environnements sans git.
        if binary is not None:
            if not Path(binary).is_file():
                raise GitError(f"git binary not found: {binary}")
            self._bin: str | None = binary
        else:
            self._bin = None

    def _resolve(self) -> str:
        if self._bin is not None:
            return self._bin
        resolved = shutil.which("git")
        if not resolved:
            raise GitError("git binary not found in PATH")
        self._bin = resolved
        return self._bin

    def clone(self, url: str, destination: Path, *, branch: str | None = None) -> None:
        args = ["clone"]
        if branch is not None:
            args += ["--branch", branch]
        args += [url, str(destination)]
        self._run(args, cwd=None)

    def checkout(self, repo: Path, ref: str) -> None:
        self._run(["checkout", ref], cwd=repo)

    def add(self, repo: Path, paths: list[str]) -> None:
        self._run(["add", *paths], cwd=repo)

    def commit(self, repo: Path, message: str) -> None:
        self._run(["commit", "-m", message], cwd=repo)

    def push(self, repo: Path, *, remote: str, ref: str) -> None:
        self._run(["push", remote, ref], cwd=repo)

    def tag(self, repo: Path, *, name: str, message: str | None = None) -> None:
        args = ["tag", "-a", name]
        if message is not None:
            args += ["-m", message]
        else:
            args += ["-m", name]
        self._run(args, cwd=repo)

    def current_revision(self, repo: Path) -> str:
        return self._run(["rev-parse", "HEAD"], cwd=repo).strip()

    def _run(self, args: list[str], *, cwd: Path | None) -> str:
        try:
            r = subprocess.run(  # noqa: S603
                [self._resolve(), *args],
                cwd=str(cwd) if cwd else None,
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise GitError(str(e)) from e
        if r.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout
