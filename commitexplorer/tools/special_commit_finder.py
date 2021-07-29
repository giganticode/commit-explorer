from typing import List, Generator, Dict, Any

from pydriller import Repository

from commitexplorer.common import Tool, Commit, Project, Sha, clone_github_project, path_to_working_dir


class SpecialCommitFinder(Tool):
    def run_on_project(self, project: Project, all_shas: List[Commit]) -> Generator[Dict[Sha, Any], None, None]:
        if len(all_shas) == 0:
            yield {}
            return

        repo = clone_github_project(project)
        working_dir = str(path_to_working_dir(repo))
        yield {commit.hash: {'merge': commit.merge, 'initial': len(commit.parents) == 0} for commit in Repository(working_dir).traverse_commits()}

    def run_on_commit(self, commit: Commit):
        raise NotImplemented()

