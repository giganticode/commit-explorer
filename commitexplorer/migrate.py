import json
import os
from pathlib import Path
from typing import Dict

from pymongo.errors import WriteError, DocumentTooLarge

from commitexplorer.cli import db

storage_path = os.environ['COMMIT_EXPLORER_STORAGE']


def remove_large_values(dct: Dict) -> Dict:
    res = {}
    for key, value in dct.items():
        if len(json.dumps(value).encode('utf-8')) > 1024 * 1024 * 10:
            print(f'Omiting {key}')
            res[key]['status'] = 'value-too-large'
        else:
            res[key] = value
    return res


def save_commits_from_fs_to_db():
    for dirpath, dirnames, filenames in os.walk(storage_path):
        for file in filenames:
            path = Path(dirpath) / file
            with path.open() as f:
                dct = json.loads(f.read())
                sha = str(path.parent.parent.name) + str(path.parent.name) + str(path.name)
                if len(sha) != 40:
                    raise AssertionError(sha)
                try:
                    db.commits.insert_one({'_id': sha, **dct})
                except (WriteError, DocumentTooLarge):
                    print(f'Document too large ==========================> {sha}')
                    dct = remove_large_values(dct)
                    db.commits.insert_one({'_id': sha, **dct})

        if len(filenames) == 0:
            print(f'Processing {dirpath}')
            print(f'Commits in the db: {db.commits.estimated_document_count()}')


save_commits_from_fs_to_db()


