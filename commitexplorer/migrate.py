import json
import os
from pathlib import Path

from commitexplorer.cli import db

storage_path = os.environ['COMMIT_EXPLORER_STORAGE']


for dirpath, dirnames, filenames in os.walk(storage_path):
    for file in filenames:
        path = Path(dirpath) / file
        with path.open() as f:
            dct = json.loads(f.read())
            sha = str(path.parent.name) + str(path.parent.parent.name) + str(path.name)
            if len(sha) != 40:
                raise AssertionError(sha)
            db.commits.insert_one({'_is': sha, **dct})
    if len(filenames) == 0:
        print(f'Processing {dirpath}')
        print(f'Commits in the db: {db.commits.estimated_document_count()}')


