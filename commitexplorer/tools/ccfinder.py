import re
from dataclasses import dataclass

import pygit2

from commitexplorer.common import Tool

cc_regex = re.compile('(?P<type>fix|feat|build|chore|ci|docs|style|refactor|perf|test)(?P<scope>(?:\([^()\r\n]*\)|\()?(?P<breaking>!)?)(?P<subject>:.*)?', re.DOTALL | re.IGNORECASE)


@dataclass
class ConventionalCommitFinder(Tool):
    lightweight_commits = True

    def run_on_commit(self, commit: pygit2.Commit):
        matcher = re.fullmatch(cc_regex, commit.message)
        if matcher is not None:
            return {'type': matcher.group('type'), 'conventional': True}
        else:
            return {'conventional': False}

