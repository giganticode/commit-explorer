import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

import git
from tqdm import tqdm

from commitexplorer import project_root
from commitexplorer.common import Tool, clone_github_project, Sha, Project
from commitexplorer.save import save_results
from commitexplorer.tools import tool_id_map


@dataclass
class Job:
    tools: List[str]
    projects: List[Project]

    @classmethod
    def load_from_file(cls, path: Path, lock_path: Path) -> 'Job':
        with open(path, 'r') as f:
            config = json.load(f)
        all_projects = [Project(c['owner'], c['repo']) for c in config['projects']]
        projects = None
        if lock_path.exists():
            with open(lock_path, 'r') as f:
                last_processing = f.read().strip().split('/')
                for i, project in enumerate(all_projects):
                    if project.owner == last_processing[0] and project.repo == last_processing[1]:
                        projects = all_projects[i:]
        else:
            projects = all_projects
        if projects is None:
            raise AssertionError()
        return cls(config['tools'], projects)


def get_tool_by_id(id: str) -> Tool:
    tool_id, version = id.split('/')
    tool_class = tool_id_map[tool_id]
    tool = tool_class(version)
    return tool


def mine(job: Job, lock_path: Path):
    tools = [(tool_id, get_tool_by_id(tool_id)) for tool_id in job.tools]
    with open(project_root / 'github.token') as f:
        token = f.read().strip()
    for project in tqdm(job.projects):
        path = clone_github_project(project, token)
        if path is None:
            continue
        all_commits = [commit for commit in git.Repo(path).iter_commits()]
        with open(lock_path, 'w') as f:
            f.write(f'{project}')
        commit_results: Dict[Sha, Dict[str, Any]] = {}
        for tool_id, tool in tools:
            try:
                # TODO save commits in batch - what does this mean? :)
                result = tool.run_on_project(project, all_commits)
                for sha, commit_result in result.items():
                    if sha not in commit_result:
                        commit_results[sha] = {}
                    commit_results[sha][tool_id] = commit_result
            except Exception as ex:
                print(f"Exception: {type(ex).__name__}, {ex}, tool: {tool_id}, project: {project}")
                traceback.print_tb(ex.__traceback__)
        try:
            save_results(commit_results, project)
        except Exception as ex:
            print(f"Exception: {type(ex).__name__}, {ex}, tool: commit: {project}")
            traceback.print_tb(ex.__traceback__)
    lock_path.unlink()


if __name__ == '__main__':
    job_config = project_root / 'job.json'
    job_lock = job_config.with_suffix('.lock')
    job = Job.load_from_file(job_config, job_lock)
    mine(job, job_lock)
