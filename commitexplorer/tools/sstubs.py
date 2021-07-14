import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from git.objects import commit

from commitexplorer import project_root
from commitexplorer.common import PATH_TO_TOOLS, Tool, clone_github_project, Project, Sha, Commit


def get_full_github_url(author: str, repo: str) -> str:
    return f"https://github.com/{author}/{repo}"


class SStubs(Tool):
    def __init__(self, version: str):
        self.path = PATH_TO_TOOLS / type(self).__name__ / version
        with open(project_root / 'github.token', 'r') as f:
            self.token = f.read().strip()

    def run_on_project(self, project: Project, all_shas: List[commit.Commit]) -> Dict[Sha, Dict[str, Any]]:
        path, metadata = clone_github_project(project, self.token, return_metadata=True)
        if not Tool.is_java_project(metadata['langs']):
            print(f'{type(self).__name__}: not a java project, skipping ...')
            return {} #TODO remove duplication
        with tempfile.TemporaryDirectory() as f:
            project_path = Path(f) / 'project'
            project_path.mkdir()
            os.symlink(path, project_path / path.name)
            output_path = Path(f) / 'output'
            cmd = ["java", "-jar", "miner.jar", str(project_path), str(output_path)]
            subprocess.run(cmd, cwd=self.path, capture_output=True, check=True)

            result: Dict[Sha, Dict[str, Any]] = {}
            with open(output_path / 'bugs.json') as g:
                bugs: List[Dict] = json.load(g)
                for bug in bugs:
                    sha = bug['fixCommitSHA1']
                    if sha not in result:
                        result[sha] = {'bugs': [], 'sstubs': []}
                    result[sha]['bugs'].append(bug)

            with open(output_path / 'sstubs.json') as g:
                sstubs: List[Dict] = json.load(g)
                for sstub in sstubs:
                    sha = Sha(bug['fixCommitSHA1'])
                    if sha not in result:
                        result[sha] = {'sstubs': []}
                    result[sha]['sstubs'].append(sstub)
        return result

    def run_on_commit(self, commit: Commit):
        raise NotImplemented()
