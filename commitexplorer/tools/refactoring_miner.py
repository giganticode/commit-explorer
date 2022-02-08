import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Tuple, Generator, Any, Optional, Set

import jsons as jsons
import pygit2
from jsons import DecodeError
from pygit2 import Commit, Repository

from commitexplorer.common import Tool, clone_project, Sha, path_to_working_dir, ProjectObj


logger = logging.getLogger(__name__)


@dataclass
class RefactoringMinerCommit:
    repository: str
    sha1: str
    url: str
    refactorings: List


@dataclass
class RefactoringMinerOutput:
    commits: List[RefactoringMinerCommit] = field(default_factory=list)


class RefactoringMiner(Tool):
    def run_on_commit(self, commit: pygit2.Commit):
        raise NotImplementedError()

    def run_on_project(self, project: ProjectObj, commits_new_to_old: List[Commit], limited_to_shas: Optional[Set[Sha]] = None) -> Generator[Dict[Sha, List], None, None]:
        repo, metadata = clone_project(project, self.token, return_metadata=True)
        if not Tool.is_java_project(metadata['langs']):
            logger.info(f'{type(self).__name__}: not a java project, skipping ...')
        else:
            return super(RefactoringMiner, self).run_on_project(project, commits_new_to_old, limited_to_shas)

    def run_on_commit_range(self, commit_range: List[pygit2.Commit], repo: Repository, timeout: Optional[int] = None, limited_to_shas: Optional[Set[Sha]] = None) -> Dict[Sha, List]: #TODO run on commit also for sstubs?
        older_commit = commit_range[-1]
        newer_commit = commit_range[0]
        with tempfile.NamedTemporaryFile() as f:
            logger.debug(f'Processing commits from {older_commit.hex} ({datetime.fromtimestamp(older_commit.commit_time).strftime("%Y-%m-%d %H:%M:%S")}) to {newer_commit.hex} ({datetime.fromtimestamp(newer_commit.commit_time).strftime("%Y-%m-%d %H:%M:%S")}) ...')
            working_dir = path_to_working_dir(repo)
            cmd = ["./RefactoringMiner", "-bc", str(working_dir), older_commit.hex, newer_commit.hex, '-json', f.name]
            logger.debug(f'Running command {cmd}')
            try:
                subprocess.run(cmd, cwd=self.path, capture_output=True, check=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning(f"Process {cmd} was interrupted because of the timeout.")
            try:
                output: RefactoringMinerOutput = jsons.loads(f.read(), RefactoringMinerOutput)
                dct = {c.sha1: {'status': 'ok', 'refactorings': c.refactorings} for c in output.commits}
                n_refactorings = len(dct.keys())
                for commit in commit_range[:-1]:
                    if commit.hex not in dct:
                        dct[commit.hex] = {'status': 'not-analyzed'}
                logger.debug(f'Refactorings detected: {n_refactorings}/{len(commit_range) - 1}')
            except DecodeError:
                logger.warning('Decode error')
                dct = {commit.hex: {'status': 'corrupted-output'} for commit in commit_range[:-1]}
            return dct
