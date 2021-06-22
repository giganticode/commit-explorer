import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Dict

import jsons as jsons

from commitexplorer import project_root
from commitexplorer.common import Commit, PATH_TO_TOOLS, Tool, clone_github_project


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

    def run(self, commit: Commit) -> Dict:
        path = clone_github_project(commit.owner, commit.repo, self.token)
        with tempfile.NamedTemporaryFile() as f:
            cmd = ["./RefactoringMiner", "-a", str(path), '-json', f.name]
            subprocess.run(cmd, cwd=self.path, capture_output=True, check=True)
            commits: RefactoringMinerOutput = jsons.loads(f.read(), RefactoringMinerOutput)
            result = {c.sha1: c.refactorings for c in commits.commits if c.refactorings}
        return result
