from typing import Any

import pydriller
from pydriller import ModificationType

from commitexplorer.common import Tool
from commitexplorer.util.accuratechanges import calculate_changes


class MessageMiner(Tool):
    lightweight_commits = True

    def run_on_commit(self, commit: pygit2.Commit) -> Any:
        return commit.message
