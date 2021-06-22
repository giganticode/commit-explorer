import json
from typing import Dict

import jsons

from commitexplorer.common import get_path_by_sha


class CorruptedFileError(Exception):
    pass


def load_commit(sha: str) -> Dict:
    path = get_path_by_sha(sha)
    with open(path) as f:
        try:
            return json.load(f)
        except json.decoder.JSONDecodeError as ex:
            raise CorruptedFileError() from ex