import pydriller
import pygit2

from commitexplorer.common import Tool


class SpecialCommitFinder(Tool):

    def run_on_commit(self, commit: pydriller.Commit):
        return {'merge': commit.merge, 'initial': len(commit.parents) == 0}

