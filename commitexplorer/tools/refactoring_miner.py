import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Generator, Any, Optional

import jsons as jsons
from git.objects import commit
from jsons import DecodeError
from tqdm import tqdm

from commitexplorer import project_root
from commitexplorer.common import PATH_TO_TOOLS, Tool, clone_github_project, Project, Sha, Commit


@dataclass
class RefactoringMinerCommit:
    repository: str
    sha1: str
    url: str
    refactorings: List


@dataclass
class RefactoringMinerOutput:
    commits: List[RefactoringMinerCommit] = field(default_factory=list)


def get_full_github_url(author: str, repo: str) -> str:
    return f"https://github.com/{author}/{repo}"


def commit_boundary_generator(lst: List, chunk_size) -> Generator[Tuple[Any, Any], None, None]:
    """
    >>> [(older, newer) for older, newer in commit_boundary_generator([1, 2, 3, 4], 2)]
    [(3, 1), (4, 3)]
    >>> [(older, newer) for older, newer in commit_boundary_generator([1, 2, 3, 4], 3)]
    [(4, 1), (4, 4)]
    >>> [(older, newer) for older, newer in commit_boundary_generator([1, 2, 3, 4], 20000)]
    [(4, 1)]
    """
    n = len(lst)
    for i in tqdm(range((n - 1) // chunk_size + 1)):
        newer = lst[i * chunk_size]
        older = lst[min(n - 1, i * chunk_size + chunk_size)]
        yield older, newer


class RefactoringMiner(Tool):
    def __init__(self, version: str):
        self.path = PATH_TO_TOOLS / type(self).__name__ / version / "bin"
        with open(project_root / 'github.token', 'r') as f:
            self.token = f.read().strip()

    def run_on_project(self, project: Project, all_shas_new_to_old: List[commit.Commit]) -> Generator[Dict[Sha, List], None, None]:
        path, metadata = clone_github_project(project, self.token, return_metadata=True)
        if not Tool.is_java_project(metadata['langs']):
            print(f'{type(self).__name__}: not a java project, skipping ...')
        else:
            commit_chunk = 1000
            max_seconds_per_commit = 6
            for older_commit, newer_commit in tqdm(commit_boundary_generator(all_shas_new_to_old, commit_chunk)):
                commit_result = self._run_on_commit_range(older_commit, newer_commit, path, commit_chunk * max_seconds_per_commit)
                yield commit_result

    def _run_on_commit_range(self, older_commit: commit.Commit, newer_commit: commit.Commit, path: Path, timeout: Optional[int] = None) -> Dict[Sha, List]: #TODO run on commit also for sstubs?
        with tempfile.NamedTemporaryFile() as f:
            print(f'Processing commits from {older_commit.hexsha} ({older_commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")}) to {newer_commit.hexsha} ({newer_commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")}) ...')
            cmd = ["./RefactoringMiner", "-bc", str(path), older_commit.hexsha, newer_commit.hexsha, '-json', f.name]
            print(f'Running command {cmd}')
            try:
                subprocess.run(cmd, cwd=self.path, capture_output=True, check=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                print(f"Warning: process {cmd} was interrupted because of the timeout.")
            try:
                output: RefactoringMinerOutput = jsons.loads(f.read(), RefactoringMinerOutput)
                n_commits_analyzed = len(output.commits)
                dct = {c.sha1: c.refactorings for c in output.commits if c.refactorings}
                n_refactorings = len(dct.items())
                print(f'Refactorings detected: {n_refactorings}/{n_commits_analyzed}')
            except DecodeError:
                dct = {}
            return dct

    def run_on_commit(self, commit: Commit) -> List:
        path = clone_github_project(commit.project, self.token)
        self._run_on_commit_range(commit, commit, path)

