from typing import Any

import pygit2

from commitexplorer.common import Tool


class MessageMiner(Tool):
    lightweight_commits = True

    def run_on_commit(self, commit: pygit2.Commit) -> Any:
        return commit.message
