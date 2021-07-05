import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pygit2 as pygit2
from github import Github, GithubException
from github.GithubException import UnknownObjectException

from commitexplorer import project_root

logger = logging.getLogger(__name__)


@dataclass
class Commit:
    owner: str
    repo: str
    sha: Optional[str]


def get_path_by_sha(sha: str, create: bool = False) -> Path:
    path = PATH_TO_STORAGE / sha[:2] / sha[2:4] / sha[4:]
    if create and not path.parent.exists():
        path.parent.mkdir(parents=True)
    return path


def clone_github_project(owner: str, repo: str, token: Optional[str] = None) -> Path:
    path_to_repo: Path = PATH_TO_REPO_CACHE / owner / repo
    if path_to_repo.exists() and any(path_to_repo.iterdir()):
        logger.debug(f"Project {owner}/{repo} already exists in project cache.")
        return path_to_repo
    print(f"Cloning {owner}/{repo} from GitHub...")
    github = Github(token)
    if not path_to_repo.exists():
        path_to_repo.mkdir(parents=True)
    try:
        repo = github.get_repo(f'{owner}/{repo}')
        pygit2.clone_repository(repo.git_url, str(path_to_repo))
    except UnknownObjectException:
        print(f'Project {owner}/{repo} not found. Was it removed?')
        (path_to_repo / "NOT_FOUND").touch()
    return path_to_repo


class Tool(ABC):
    version: str

    @abstractmethod
    def run(self, commit: Commit) -> Any:
        pass


PATH_TO_STORAGE = project_root / 'storage'
PATH_TO_TOOLS = project_root / 'software'
PATH_TO_REPO_CACHE = project_root / 'repo-cache'