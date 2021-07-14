import json
from typing import Any, Dict

from commitexplorer.common import get_path_by_sha, Project, Sha
from commitexplorer.load import load_commit


def save_results(results: Dict[Sha, Dict[str, Any]], project: Project, rewrite_allowed: bool = False) -> None:
    for sha, tool_result in results.items():
        try:
            dct = load_commit(sha)
        except FileNotFoundError:
            dct = {}
        for tool_id, value in tool_result.items():
            if tool_id not in dct or rewrite_allowed:
                dct[tool_id] = value
        dct['owner'] = project.owner
        dct['repo'] = project.repo
        path = get_path_by_sha(sha, create=True)
        with open(path, 'w') as f:
            json.dump(dct, f)
