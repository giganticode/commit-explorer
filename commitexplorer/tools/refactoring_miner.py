import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict

import jsons as jsons
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


class RefactoringMiner(Tool):
    def __init__(self, version: str):
        self.path = PATH_TO_TOOLS / type(self).__name__ / version / "bin"
        with open(project_root / 'github.token', 'r') as f:
            self.token = f.read().strip()

    def run_on_project(self, project: Project, all_shas: List[Sha]) -> Dict[Sha, List]:
        path, metadata = clone_github_project(project, self.token, return_metadata=True)
        if not Tool.is_java_project(metadata['langs']):
            print(f'{type(self).__name__}: not a java project, skipping ...')
            return {}
        res = {}
        # TODO log: n commits analyzed in m seconds
        n_commits = len(all_shas)
        commit_chunk = 1000
        for i in tqdm(range(n_commits // commit_chunk + 1)):
            start_commit = Commit(project, all_shas[i * commit_chunk])
            end_commit = Commit(project, all_shas[min(n_commits - 1, i * commit_chunk + commit_chunk - 1)])
            commit_result = self._run_on_commit_range(end_commit, start_commit, path)
            res.update(commit_result)
        return res

    def _run_on_commit_range(self, start_commit: Commit, end_commit: Commit, path: Path) -> Dict[Sha, List]: #TODO run on commit also for sstubs?
        with tempfile.NamedTemporaryFile() as f:
            cmd = ["./RefactoringMiner", "-bc", str(path), start_commit.sha, end_commit.sha, '-json', f.name]
            subprocess.run(cmd, cwd=self.path, capture_output=True, check=True)
            commits: RefactoringMinerOutput = jsons.loads(f.read(), RefactoringMinerOutput)
            return {c.sha1: c.refactorings for c in commits.commits if c.refactorings}

    def run_on_commit(self, commit: Commit) -> List:
        path = clone_github_project(commit.project, self.token)
        self._run_on_commit_range(commit, commit, path)

