import json
import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Dict, Tuple, Union, NewType, List, Generator, Set

import github.Repository as githubrepo
import pydriller
from pygit2 import clone_repository, Repository, GitError
import pygit2
from github import Github
from github.GithubException import UnknownObjectException
from tqdm import tqdm

from commitexplorer import project_root

logger = logging.getLogger(__name__)


Sha = NewType('Sha', str)


@dataclass(frozen=True)
class Project:
    owner: str
    repo: str

    def __str__(self):
        return f'{self.owner}/{self.repo}'


@dataclass(frozen=True)
class Commit:
    project: Project
    sha: Sha


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
    path_to_repo_empty = not any(path_to_repo.iterdir())
    if path_to_repo_empty:
        print(f"Cloning {project} from GitHub...")
        repo = clone_repository(remote_repo.git_url, str(path_to_repo))
    metadata = load_metadata(path_to_metadata, remote_repo)

    return (repo, metadata) if return_metadata else repo


def commit_boundary_generator(lst: List, chunk_size) -> Generator[List[Any], None, None]:
    """
    >>> [rng for rng in commit_boundary_generator([], 2)]
    []
    >>> [rng for rng in commit_boundary_generator([1, 2, 3, 4], 2)]
    [[1, 2, 3], [3, 4]]
    >>> [rng for rng in commit_boundary_generator([1, 2, 3, 4], 3)]
    [[1, 2, 3, 4], [4]]
    >>> [rng for rng in commit_boundary_generator([1, 2, 3, 4], 20000)]
    [[1, 2, 3, 4]]
    """
    n = len(lst)
    for i in tqdm(range((n - 1) // chunk_size + 1)):
        newer_index = i * chunk_size
        older_index = min(n - 1, i * chunk_size + chunk_size)
        yield lst[newer_index: older_index+1]


@dataclass
class Tool(ABC):
    version: Optional[str]
    lightweight_commits: bool = field(default=False, init=False)

    def __post_init__(self):
        with open(project_root / 'github.token', 'r') as f:
            self.token = f.read().strip()
        if self.version is not None:
            self.path = PATH_TO_TOOLS / type(self).__name__ / self.version / "bin"
        else:
            self.path = None

    def run_on_project(self, project: Project, commits_new_to_old: List[pygit2.Commit], limited_to_shas: Optional[Set[Sha]] = None) -> Generator[Dict[Sha, Any], None, None]:
        commit_chunk = 100
        max_seconds_per_commit = 6
        repo, metadata = clone_github_project(project, self.token, return_metadata=True)
        n_commits = len(commits_new_to_old)
        if n_commits > 10000:
            print(f"Number of commits need to be processed: {n_commits}. It may take some time.")
        for commit_range in tqdm(commit_boundary_generator(commits_new_to_old, commit_chunk)):
            if limited_to_shas is not None:
                run_this_batch = False
                for commit in commit_range[:-1]:
                    if commit.hex in limited_to_shas:
                        print(f"This commit range contains commit {commit.hex}")
                        run_this_batch = True
                        break
            else:
                run_this_batch = True
            if run_this_batch:
                commit_result = self.run_on_commit_range(commit_range, repo, timeout=commit_chunk * max_seconds_per_commit, limited_to_shas=limited_to_shas)
                yield commit_result

    def run_on_commit_range(self, commit_range: List[pygit2.Commit], repo: Repository, timeout: Optional[int] = None, limited_to_shas: Optional[Set[Sha]] = None) -> Dict[Sha, List]:
        older_commit = commit_range[-1]
        newer_commit = commit_range[0]
        working_dir = str(path_to_working_dir(repo))
        if not self.lightweight_commits:
            commit_range = pydriller.Repository(working_dir, from_commit=older_commit.hex, to_commit=newer_commit.hex).traverse_commits()
        hash = 'hex' if self.lightweight_commits else 'hash'
        if limited_to_shas is not None:
            commit_range = [commit for commit in commit_range if getattr(commit, hash) in limited_to_shas]
        return {getattr(commit, hash): self.run_on_commit(commit) for commit in commit_range}

    @abstractmethod
    def run_on_commit(self, commit: pydriller.Commit):
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
