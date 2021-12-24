import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

import pydriller
import pygit2

from commitexplorer.common import Tool, clone_project, GithubProject, Sha, path_to_working_dir


class SStubs(Tool):
    def run_on_project(self, project: GithubProject, all_shas: List[pygit2.Commit], limited_to_shas: Optional[Set[Sha]] = None) -> Dict[Sha, Dict[str, Any]]:
        # TODO implement limited_to_shas
        repo, metadata = clone_project(project, self.token, return_metadata=True)
        if not Tool.is_java_project(metadata['langs']):
            print(f'{type(self).__name__}: not a java project, skipping ...')
        else:
            with tempfile.TemporaryDirectory() as f:
                project_path = Path(f) / 'project'
                project_path.mkdir()
                working_dir = path_to_working_dir(repo)
                os.symlink(working_dir, project_path / working_dir.name)
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
            yield result

    def run_on_commit(self, commit: pydriller.Commit):
        raise NotImplemented()
