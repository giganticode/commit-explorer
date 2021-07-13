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
        for sha in (all_shas if len(all_shas) < 1000 else tqdm(all_shas)): #TODO if the project is too big, save earlier
            commit_result = self._run_on_commit(Commit(project, sha), path)
            if commit_result:
                res[sha] = commit_result
        return res

    def _run_on_commit(self, commit: Commit, path: Path) -> List: #TODO run on commit also for sstubs?
        with tempfile.NamedTemporaryFile() as f:
            cmd = ["./RefactoringMiner", "-c", str(path), commit.sha, '-json', f.name]
            subprocess.run(cmd, cwd=self.path, capture_output=True, check=True)
            commits: RefactoringMinerOutput = jsons.loads(f.read(), RefactoringMinerOutput)
            return commits.commits[0].refactorings if commits.commits else []

    def run_on_commit(self, commit: Commit) -> List:
        path = clone_github_project(commit.project, self.token)
        self._run_on_commit(commit, path)

