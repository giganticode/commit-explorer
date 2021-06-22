import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import git
import pygit2
from tqdm import tqdm

from commitexplorer import project_root
from commitexplorer.common import Commit, Tool, clone_github_project
from commitexplorer.save import save_results
from commitexplorer.tools import tool_id_map

Sha = str


@dataclass
class Job:
    tools: List[str]
    commits: List[Commit]

    @classmethod
    def load_from_file(cls, path: Path, lock_path: Path) -> 'Job':
        with open(path, 'r') as f:
            config = json.load(f)
        all_commits = [Commit(c['owner'], c['repo'], None) for c in config['commits']]
        commits = None
        if lock_path.exists():
            with open(lock_path, 'r') as f:
                last_processing = f.read().strip().split('/')
                for i, commit in enumerate(all_commits):
                    if commit.owner == last_processing[0] and commit.repo == last_processing[1]:
                        commits = all_commits[i:]
        else:
            commits = all_commits
        if commits is None:
            raise AssertionError()
        return cls(config['tools'], commits)


def get_tool_by_id(id: str) -> Tool:
    tool_id, version = id.split('/')
    tool_class = tool_id_map[tool_id]
    tool = tool_class(version)
    return tool


def mine(job: Job, lock_path: Path):
    tools = [(tool_id, get_tool_by_id(tool_id)) for tool_id in job.tools]
    for commit in tqdm(job.commits):
        with open(lock_path, 'w') as f:
            f.write(f'{commit.owner}/{commit.repo}')
        commit_results = {}
        for tool_id, tool in tools:
            try:
                # TODO save commits in batch
                result = tool.run(commit)
                commit_results[tool_id] = result
            except Exception as ex:
                print(f"Exception: {ex}, tool: {tool_id}, commit: {commit}")
        try:
            path = clone_github_project(commit.owner, commit.repo)
            all_shas = [commit.hexsha for commit in git.Repo(path).iter_commits()]
            save_results(commit_results, commit, all_shas)
        except Exception as ex:
            print(f"Exception: {ex}, tool: commit: {commit}")
    lock_path.unlink()


if __name__ == '__main__':
    job_config = project_root / 'job.json'
    job_lock = job_config.with_suffix('.lock')
    job = Job.load_from_file(job_config, job_lock)
    mine(job, job_lock)
