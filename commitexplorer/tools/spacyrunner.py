import jsons
import pydriller

from commitexplorer.common import Tool
# from commitexplorer.tools.nlp import get_commit_cores, nlp


class SpacyRunner(Tool):

    def run_on_commit(self, commit: pydriller.Commit):
        return {'parsed_message': jsons.dump(get_commit_cores(commit.msg, nlp))}