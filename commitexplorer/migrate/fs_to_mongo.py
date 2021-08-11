import json
import os
from pathlib import Path
from typing import Dict, List

from commitexplorer.cli import db


def remove_large_values(dct: Dict) -> Dict:
    res = {}
    for key, value in dct.items():
        if len(json.dumps(value).encode('utf-8')) > 1024 * 1024 * 10:
            print(f'Omitting {key}')
            res[key] = {'status': 'value-too-large'}
        else:
            res[key] = value
    return res


def validate_and_fix_tool_ids(commit_document: Dict) -> Dict:
    """
    >>> validate_and_fix_tool_ids({'_id': 'af34af', 'tools': {'unknown_tool': {}}})
    Traceback (most recent call last):
    ...
    ValueError: Unknown key: unknown_tool
    >>> validate_and_fix_tool_ids({'_id': 'af34af', 'tools': {}})
    {'_id': 'af34af', 'tools': {}}
    >>> validate_and_fix_tool_ids({'_id': 'af34af', 'tools': {'mine_sstubs/head': [], 'refactoring_miner/2.1.0': {}, 'special_commit_finder/0.1': 3}})
    {'_id': 'af34af', 'tools': {'mine_sstubs/head': [], 'refactoring_miner/2_1_0': {}, 'special_commit_finder/0_1': 3}}
    """
    keys_tranformation = {
        'mine_sstubs/head': 'mine_sstubs/head',
        'refactoring_miner/2.1.0': 'refactoring_miner/2_1_0',
        'special_commit_finder/0.1': 'special_commit_finder/0_1',
        'gumtree/3.0.0-beta2': 'gumtree/3_0_0-beta2'
    }
    new_tools = {}
    for key in commit_document['tools'].keys():
        if key not in keys_tranformation:
            raise ValueError(f'Unknown key: {key}')

    for key, new_key in keys_tranformation.items():
        if key in commit_document['tools']:
            new_tools[new_key] = commit_document['tools'][key]

    commit_document['tools'] = new_tools
    return commit_document


def check_no_dots_and_dollars_in_keys(dct: Dict) -> None:
    """
    >>> check_no_dots_and_dollars_in_keys({'a': 1, 'b': {'c': {'2': 1}}})
    >>> check_no_dots_and_dollars_in_keys({'a': 1, 'b': {'c': {'2.0': 1}}})
    Traceback (most recent call last):
    ...
    ValueError: Value: 2.0, type: str
    >>> check_no_dots_and_dollars_in_keys({'a': 1, 'b': {'c': {'$20': 1}}})
    Traceback (most recent call last):
    ...
    ValueError: Value: $20, type: str
    >>> check_no_dots_and_dollars_in_keys({'a': 1, 'b': {'c': {2.0: 1}}})
    Traceback (most recent call last):
    ...
    ValueError: Value: 2.0, type: float
    """
    if isinstance(dct, List):
        for l in dct:
            check_no_dots_and_dollars_in_keys(l)
    elif isinstance(dct, Dict):
        for key, value in dct.items():
            if not isinstance(key, str) or '.' in key or key.startswith('$'):
                raise ValueError(f'Value: {key}, type: {type(key).__name__}')
            check_no_dots_and_dollars_in_keys(value)


def save_commits_from_fs_to_db(database):
    storage_path = os.environ['COMMIT_EXPLORER_STORAGE']
    for dirpath, dirnames, filenames in os.walk(storage_path):
        for file in filenames:
            path = Path(dirpath) / file
            with path.open() as f:
                dct = json.loads(f.read())
                sha = str(path.parent.parent.name) + str(path.parent.name) + str(path.name)
                if len(sha) != 40:
                    raise AssertionError(sha)

                dct = validate_and_fix_tool_ids(dct)
                check_no_dots_and_dollars_in_keys(dct)
                dct = remove_large_values(dct)
                database.commits.insert_one({'_id': sha, **dct})

        if len(filenames) == 0:
            print(f'Processing {dirpath}')
            print(f'Commits in the db: {database.commits.estimated_document_count()}')


if __name__ == '__main__':
    save_commits_from_fs_to_db(db)


