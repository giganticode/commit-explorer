import json
import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Dict, Tuple, Union, NewType, List, Generator

import github.Repository as githubrepo
from pygit2 import clone_repository, Repository, GitError
from github import Github
from github.GithubException import UnknownObjectException

from commitexplorer import project_root

logger = logging.getLogger(__name__)


Sha = NewType('Sha', str)


@dataclass
class Project:
    owner: str
    repo: str

    def __str__(self):
        return f'{self.owner}/{self.repo}'


@dataclass
class Commit:
    project: Project
    sha: Sha


def get_path_by_sha(sha: str, create: bool = False) -> Path:
    path = PATH_TO_STORAGE / sha[:2] / sha[2:4] / sha[4:]
    if create and not path.parent.exists():
        path.parent.mkdir(parents=True)
    return path


def path_exists_and_not_empty(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def path_to_working_dir(repo: Repository) -> Path:
    if not repo.path.endswith('.git/'):
        raise AssertionError(f'Repo path should end with .git but is: {repo.path}')
    return Path(repo.path).parent


def load_metadata(path_to_metadata: Path, remote_repo: githubrepo.Repository):
    if not path_to_metadata.exists():
        metadata = {'langs': remote_repo.get_languages()}

        with path_to_metadata.open('w') as f:
            json.dump(metadata, f)
    else:
        with path_to_metadata.open() as f:
            metadata = json.load(f)
    return metadata


def clone_github_project(project: Project, token: Optional[str] = None, return_metadata: Optional[bool] = False) -> Optional[Union[Repository, Tuple[Repository, Dict[str, Any]]]]:
    path_to_repo: Path = PATH_TO_REPO_CACHE / project.owner / project.repo
    path_to_metadata: Path = Path(str(path_to_repo) + ".metadata")

    if path_exists_and_not_empty(path_to_repo):
        if (path_to_repo / "NOT_FOUND").exists():
            print(f"We already tried to mine the project {project} but it was not found.")
            return (None, None) if return_metadata else None
        if path_to_metadata.exists():
            print(f"Project {project} and metadata already exist in project cache.")
            with path_to_metadata.open() as f:
                metadata = json.load(f)
            try:
                repo = Repository(path_to_repo)
            except GitError as ex:
                print(f'Warning: error {ex} has been raised. Removing repo at {path_to_repo} and trying to clone it one more time.')
                shutil.rmtree(str(path_to_repo), ignore_errors=True)
                repo = clone_github_project(project, token)
            return (repo, metadata) if return_metadata else repo

    github = Github(token)
    if not path_to_repo.exists():
        path_to_repo.mkdir(parents=True)
    try:
        remote_repo = github.get_repo(f'{project}')
    except UnknownObjectException:
        print(f'Project {project} not found. Was it removed?')
        (path_to_repo / "NOT_FOUND").touch()
        return (None, None) if return_metadata else None
    if not any(path_to_repo.iterdir()):
        print(f"Cloning {project} from GitHub...")
        repo = clone_repository(remote_repo.git_url, str(path_to_repo))
    metadata = load_metadata(path_to_metadata, remote_repo)

    return (repo, metadata) if return_metadata else repo


@dataclass
class Tool(ABC):
    version: str

    def __post_init__(self):
        with open(project_root / 'github.token', 'r') as f:
            self.token = f.read().strip()
        self.path = PATH_TO_TOOLS / type(self).__name__ / self.version / "bin"

    @abstractmethod
    def run_on_project(self, project: Project, all_shas: List[Commit]) -> Generator[Dict[Sha, Any], None, None]:
        pass

    @abstractmethod
    def run_on_commit(self, commit: Commit):
        pass

    @staticmethod
    def is_java_project(lang_metadata: Dict[str, int]) -> bool:
        """
        >>> Tool.is_java_project({'Java': 10, 'C': 30})
        True
        >>> Tool.is_java_project({'Java': 1, 'C': 30})
        False
        """
        return Tool.code_percentage(lang_metadata, 'Java') > 0.05

    @staticmethod
    def code_percentage(lang_metadata: Dict[str, int], lang: str) -> float:
        """
        >>> Tool.code_percentage({'Java': 10, 'C': 30}, 'Java')
        0.25
        """
        all_languages = sum([b for b in lang_metadata.values()])
        try:
            return lang_metadata[lang] / all_languages
        except KeyError:
            return 0.0


PATH_TO_TOOLS = project_root / 'software'
try:
    PATH_TO_STORAGE = Path(os.environ['COMMIT_EXPLORER_STORAGE'])
except KeyError:
    PATH_TO_STORAGE = project_root / 'storage'
    print(f"Warning: COMMIT_EXPLORER_STORAGE env variable not set -- using : {PATH_TO_STORAGE}.")

try:
    PATH_TO_REPO_CACHE = Path(os.environ['COMMIT_EXPLORER_REPO_CACHE'])
except KeyError:
    PATH_TO_REPO_CACHE = project_root / 'repo-cache'
    print(f"Warning: COMMIT_EXPLORER_REPO_CACHE env variable not set -- using: {PATH_TO_REPO_CACHE}.")
