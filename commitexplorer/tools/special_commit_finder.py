from typing import List, Generator, Dict, Any

from git.objects import commit
from pydriller import Repository

from commitexplorer.common import Tool, Commit, Project, Sha, clone_github_project


class SpecialCommitFinder(Tool):
    def __init__(self, version: str):
        pass

    def run_on_project(self, project: Project, all_shas: List[commit.Commit]) -> Generator[Dict[Sha, Any], None, None]:
        path = clone_github_project(project)
        yield {commit.hash: {'merge': commit.merge, 'initial': len(commit.parents) == 0} for commit in Repository(str(path)).traverse_commits()}

    def run_on_commit(self, commit: Commit):
        raise NotImplemented()

