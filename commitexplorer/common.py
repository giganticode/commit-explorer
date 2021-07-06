import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Dict, Tuple, Union

import pygit2 as pygit2
from github import Github
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


def clone_metadata(owner: str, repo: str, token: Optional[str] = None) -> Dict[str, Any]:
    path_to_repo_metadata: Path = Path(str(PATH_TO_REPO_CACHE / owner / repo) + ".metadata")
    if not path_to_repo_metadata.exists():
        path_to_repo_metadata.parent.mkdir(exist_ok=True, parents=True)
        github = Github(token)
        repo = github.get_repo(f'{owner}/{repo}')
        metadata = {'langs': repo.get_languages()}

        with path_to_repo_metadata.open('w') as f:
            json.dump(metadata, f)
        return metadata
    with path_to_repo_metadata.open() as f:
        return json.load(f)


def clone_github_project(owner: str, repo: str, token: Optional[str] = None, return_metadata: Optional[bool] = False) -> Union[Path, Tuple[Path, Dict[str, Any]]]:
    path_to_repo: Path = PATH_TO_REPO_CACHE / owner / repo
    metadata = clone_metadata(owner, repo, token)
    if path_to_repo.exists() and any(path_to_repo.iterdir()):
        logger.debug(f"Project {owner}/{repo} already exists in project cache.")
        if return_metadata:
            return path_to_repo, metadata
        else:
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
    if return_metadata:
        return path_to_repo, metadata
    else:
        return path_to_repo


class Tool(ABC):
    version: str

    @abstractmethod
    def run(self, commit: Commit) -> Any:
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


PATH_TO_STORAGE = project_root / 'storage'
PATH_TO_TOOLS = project_root / 'software'
PATH_TO_REPO_CACHE = project_root / 'repo-cache'