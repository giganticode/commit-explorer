import json
from typing import Any, Dict

from commitexplorer.common import get_path_by_sha, Commit
from commitexplorer.load import load_commit


def save_results(results: Dict, commit: Commit, rewrite_allowed: bool = False) -> None:
    transposed_result = {}
    for tool, tool_result in results.items():
        for sha, sha_result in tool_result.items():
            if sha not in transposed_result:
                transposed_result[sha] = {}
            transposed_result[sha][tool] = sha_result
    for sha, sha_result in transposed_result.items():
        transposed_result[sha]['owner'] = commit.owner
        transposed_result[sha]['repo'] = commit.repo

    for sha, r in transposed_result.items():
        try:
            dct = load_commit(sha)
        except FileNotFoundError:
            dct = {}
        for key, value in r.items():
            if key in dct and not rewrite_allowed:
                raise ValueError(f"Key {key} already exists: {dct[key]}")
            dct[key] = value
        path = get_path_by_sha(sha, create=True)
        with open(path, 'w') as f:
            json.dump(dct, f)
