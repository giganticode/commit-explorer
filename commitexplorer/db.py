from types import SimpleNamespace
from typing import Any, Dict, List, Set

import pymongo as pymongo
from pymongo.errors import WriteError, DocumentTooLarge
from pygit2 import Commit

from commitexplorer.common import GithubProject, Sha, ProjectObj, GitProject
from datetime import datetime


DOT_REPLACEMENT = '_'


def escape_dot(s: str) -> str:
    """
    >>> escape_dot("1.0_2")
    '1_0_2'
    """
    return s.replace('.', DOT_REPLACEMENT)


class TmpMongo:
    def __init__(self, uri: str):
        self.uri = uri
        self.db_name = 'commit_explorer_integration_test'

    def __enter__(self):
        self.client = pymongo.MongoClient('mongodb://localhost:27017')
        return self.client[self.db_name]

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.drop_database(self.db_name)


def save_results(results: Dict[Sha, Dict[str, Any]], project: ProjectObj, db) -> None:
    """
    >>> with TmpMongo('mongodb://localhost:27017') as db:
    ...    save_results({'abc34dbc33747830aff': {'tool1/1.0': {}, 'tool2/2.0': {}}}, SimpleNamespace(owner='giganticode', repo='bohr'), db)
    ...    save_results({'abc34dbc33747830aff': {'tool2/3.0': {}}}, SimpleNamespace(owner='giganticode', repo='bohr'), db)
    ...    db.commits.find_one({'_id': 'abc34dbc33747830aff'})
    {'_id': 'abc34dbc33747830aff', 'owner': 'giganticode', 'repo': 'bohr', 'tool1/1_0': {}, 'tool2/2_0': {}, 'tool2/3_0': {}}

    >>> with TmpMongo('mongodb://localhost:27017') as db:
    ...    lots_of_data = 'a' * 1024 * 1024 * 20
    ...    save_results({'abc34dbc33747830aff': {'tool1/1.0': lots_of_data, 'tool2/2.0': {}}}, SimpleNamespace(owner='giganticode', repo='bohr'), db)
    ...    db.commits.find_one({'_id': 'abc34dbc33747830aff'})
    {'_id': 'abc34dbc33747830aff', 'owner': 'giganticode', 'repo': 'bohr', 'tool1/1_0': {'status': 'value-too-large'}, 'tool2/2_0': {}}
    """
    for sha, tool_result in results.items():
        for tool_id, value in tool_result.items():
            tool_id = escape_dot(tool_id)
            if isinstance(project, GithubProject):
                set_on_insert_dct = {'_id': sha, 'owner': project.owner, 'repo': project.repo}
            elif isinstance(project, GitProject):
                set_on_insert_dct = {'_id': sha, 'url': project.get_url()}
            else:
                raise AssertionError()
            try:
                db.commits.update_one({'_id': sha}, {
                    '$setOnInsert': set_on_insert_dct,
                    '$set': {tool_id: value}
                }, upsert=True)
            except (WriteError, DocumentTooLarge):
                db.commits.update_one({'_id': sha}, {
                    '$setOnInsert': set_on_insert_dct,
                    '$set': {tool_id: {'status': 'value-too-large'}}
                }, upsert=True)


def mark_project_as_run(project: ProjectObj, tool_id: str, database):
    """
    >>> with TmpMongo('mongodb://localhost:27017') as db: # doctest: +ELLIPSIS
    ...    mark_project_as_run(GithubProject('giganticode', 'bohr'), 'tool1/1.0', db)
    ...    mark_project_as_run(GithubProject('giganticode', 'bohr'), 'tool1/2.0', db)
    ...    db.runs.find_one({'_id': 'giganticode/bohr'})
    {'_id': 'giganticode/bohr', 'tools': {'tool1/1_0': '20...', 'tool1/2_0': '20...'}}
    """
    tool_id = escape_dot(tool_id)
    database.runs.update_one({'_id': project.get_repo_id()},
                             {'$setOnInsert': {'_id': project.get_repo_id(), "tools": {}}}
                             , upsert=True)
    database['runs'].update_one({'_id': project.get_repo_id()}, [
        {
            '$set': {
                'tools': {
                    tool_id : str(datetime.now())
                }
            }
        }
    ])


def get_already_explored_commits(commits: List[Commit], tool_id: str, database) -> Dict[Sha, Commit]:
    """
    >>> with TmpMongo('mongodb://localhost:27017') as db: # doctest: +ELLIPSIS
    ...    res = db.commits.insert_one({'_id': '1', 'special_commit_finder/0_1': []})
    ...    res = db.commits.insert_one({'_id': '2', })
    ...    res = db.commits.insert_one({'_id': '33', 'special_commit_finder/0_1': []})
    ...    commits = [SimpleNamespace(hex='1'), SimpleNamespace(hex='2'), SimpleNamespace(hex='3')]
    ...    get_already_explored_commits(commits, 'special_commit_finder/0.1', db)
    {'1': {'_id': '1', 'special_commit_finder/0_1': []}}
    """
    commit_hexes = [commit.hex for commit in commits]
    commits_from_db = database.commits.find(
        filter={'$and': [
            {'_id': {'$in': commit_hexes}},
            {escape_dot(tool_id): {'$exists': True}}
        ]}
    ) #TODO think about optimization, index on owner + repo, and query by project?
    commits_from_db_dict = {commit['_id']: commit for commit in commits_from_db}

    return commits_from_db_dict


def get_tools_not_run_on_project(tools: List[str], project: ProjectObj, database) -> List[str]:
    """
    >>> with TmpMongo('mongodb://localhost:27017') as db: # doctest: +ELLIPSIS
    ...    res = db.runs.insert_one({'_id': 'giganticode/bohr', 'tools': {'tool_1': '23:30'}})
    ...    res = db.runs.insert_one({'_id': 'giganticode/bohr2', })
    ...    get_tools_not_run_on_project(['tool.1', 'tool.2'], 'giganticode/bohr', db)
    ['tool.2']
    >>> with TmpMongo('mongodb://localhost:27017') as db: # doctest: +ELLIPSIS
    ...    res = db.runs.insert_one({'_id': 'giganticode/bohr2'})
    ...    get_tools_not_run_on_project(['tool.1', 'tool.2'], 'giganticode/bohr', db)
    ['tool.1', 'tool.2']
    """
    run = database.runs.find_one({'_id': project.get_repo_id()})
    already_run_tools_from_db = run['tools'].keys() if run is not None else []
    tools_not_run = [tool for tool in tools if escape_dot(tool) not in already_run_tools_from_db]
    return tools_not_run


def get_important_commits(database, query) -> Dict[GithubProject, Set[Sha]]:
    """
    >>> with TmpMongo('mongodb://localhost:27017') as db: # doctest: +ELLIPSIS
    ...    res = db.commits.insert_one({'_id': 'abc34dbc33747830af1', 'manual_labels': {'herzig': 1}, 'owner': 'a', 'repo': 'b'})
    ...    res = db.commits.insert_one({'_id': 'abc34dbc33747830af2', 'owner': 'a', 'repo': 'b'})
    ...    res = db.commits.insert_one({'_id': 'abc34dbc33747830af3', 'manual_labels': {'berger': 0}, 'owner': 'a', 'repo': 'c'})
    ...    res = db.commits.insert_one({'_id': 'abc34dbc33747830af4', })
    ...    get_important_commits(db)
    {Project(owner='a', repo='b'): {'abc34dbc33747830af1'}, Project(owner='a', repo='c'): {'abc34dbc33747830af3'}}
    """
    commits_from_db = database.commits.find(
        filter=query
    )
    res = {}
    for commit in commits_from_db:
        if 'owner' in commit:
            project = GithubProject(commit['owner'], commit['repo'])
        else:
            project = GitProject(commit['url'])
        if not project in res:
            res[project] = set()
        res[project].add(commit['_id'])
    return res
