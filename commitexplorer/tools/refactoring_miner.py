import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Tuple, Generator, Any, Optional

import jsons as jsons
from jsons import DecodeError
from pygit2 import Commit, Repository
from tqdm import tqdm

from commitexplorer.common import Tool, clone_github_project, Project, Sha, path_to_working_dir


@dataclass
class RefactoringMinerCommit:
    repository: str
    sha1: str
    url: str
    refactorings: List


@dataclass
class RefactoringMinerOutput:
    commits: List[RefactoringMinerCommit] = field(default_factory=list)


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


class RefactoringMiner(Tool):
    def run_on_commit(self, commit: Commit):
        raise NotImplementedError()

    def run_on_project(self, project: Project, all_shas_new_to_old: List[Commit]) -> Generator[Dict[Sha, List], None, None]:
        repo, metadata = clone_github_project(project, self.token, return_metadata=True)
        if not Tool.is_java_project(metadata['langs']):
            print(f'{type(self).__name__}: not a java project, skipping ...')
        else:
            commit_chunk = 100
            max_seconds_per_commit = 6
            for commit_range in tqdm(commit_boundary_generator(all_shas_new_to_old, commit_chunk)):
                commit_result = self._run_on_commit_range(commit_range, repo, commit_chunk * max_seconds_per_commit)
                yield commit_result

    def _run_on_commit_range(self, commit_range: List[Commit], repo: Repository, timeout: Optional[int] = None) -> Dict[Sha, List]: #TODO run on commit also for sstubs?
        older_commit = commit_range[-1]
        newer_commit = commit_range[0]
        with tempfile.NamedTemporaryFile() as f:
            print(f'Processing commits from {older_commit.hex} ({datetime.fromtimestamp(older_commit.commit_time).strftime("%Y-%m-%d %H:%M:%S")}) to {newer_commit.hex} ({datetime.fromtimestamp(newer_commit.commit_time).strftime("%Y-%m-%d %H:%M:%S")}) ...')
            working_dir = path_to_working_dir(repo)
            cmd = ["./RefactoringMiner", "-bc", str(working_dir), older_commit.hex, newer_commit.hex, '-json', f.name]
            print(f'Running command {cmd}')
            try:
                subprocess.run(cmd, cwd=self.path, capture_output=True, check=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                print(f"Warning: process {cmd} was interrupted because of the timeout.")
            try:
                output: RefactoringMinerOutput = jsons.loads(f.read(), RefactoringMinerOutput)
                dct = {c.sha1: {'status': 'ok', 'refactorings': c.refactorings} for c in output.commits}
                n_refactorings = len(dct.keys())
                for commit in commit_range[:-1]:
                    if commit.hex not in dct:
                        dct[commit.hex] = {'status': 'not-analyzed'}
                print(f'Refactorings detected: {n_refactorings}/{len(commit_range) - 1}')
            except DecodeError:
                print('Decode error')
                dct = {commit.hex: {'status': 'corrupted-output'} for commit in commit_range[:-1]}
            return dct
