from types import SimpleNamespace
from typing import Any, Dict

import pymongo as pymongo

from commitexplorer.common import Project, Sha


class TmpMongo:
    def __init__(self, uri: str):
        self.uri = uri
        self.db_name = 'commit_explorer_test'

    def __enter__(self):
        self.client = pymongo.MongoClient('mongodb://localhost:27017')
        return self.client[self.db_name]

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.drop_database(self.db_name)


def save_results(results: Dict[Sha, Dict[str, Any]], project: Project, db) -> None:
    """
    >>> with TmpMongo('mongodb://localhost:27017') as db:
    ...    save_results({'abc34dbc33747830aff': {'tool1': {}, 'tool2': {}}}, SimpleNamespace(owner='giganticode', repo='bohr'), db)
    """
    for sha, tool_result in results.items():
        for tool_id, value in tool_result.items():
            db.commits.update_one({'_id': sha}, {
                '$setOnInsert': {'_id': sha, 'owner': project.owner, 'repo': project.repo},
                '$set': {tool_id: value}
            }, upsert=True)
