import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Generator

from pygit2 import Repository, Commit
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
            raise AssertionError("No projects found, check job.json or job.lock files.")
        return cls(config['tools'], projects)


def get_tool_by_id(id: str) -> Tool:
    tool_id, version = id.split('/')
    tool_class = tool_id_map[tool_id]
    tool = tool_class(version)
    return tool


def get_all_commits(repo: Repository) -> List[Commit]:
    if repo.is_empty:
        print(f'Warning: repo at {repo.path} has no commits.')
        return []
    all_commits = [commit for commit in repo.walk(repo.head.target)]
    return all_commits


def run_tools_on_project(tools: List[Tool], project: Project, repo: Repository) -> Generator:
    all_commits = get_all_commits(repo)
    for tool_id, tool in tools:
        try:
            for result_batch in tool.run_on_project(project, all_commits):
                commit_results: Dict[Sha, Dict[str, Any]] = {}
                for sha, commit_result in result_batch.items():
                    if sha not in commit_result:
                        commit_results[sha] = {}
                    commit_results[sha][tool_id] = commit_result
                yield commit_results
        except Exception as ex:
            print(f"Exception: {type(ex).__name__}, {ex}, skipping tool: {tool_id}  (project: {project})")
            traceback.print_tb(ex.__traceback__)


def mine(job: Job, lock_path: Path):
    tools = [(tool_id, get_tool_by_id(tool_id)) for tool_id in job.tools]
    with open(project_root / 'github.token') as f:
        token = f.read().strip()
    for project in tqdm(job.projects):
        try:
            with open(lock_path, 'w') as f:
                f.write(f'{project}')
            repo = clone_github_project(project, token)
            if repo is not None:
                for result_batch in run_tools_on_project(tools, project, repo):
                    save_results(result_batch, project)
        except Exception as ex:
            print(f"Exception: {type(ex).__name__}, {ex}, skipping project: {project}")
            traceback.print_tb(ex.__traceback__)
    lock_path.unlink()


if __name__ == '__main__':
    job_config = project_root / 'job.json'
    job_lock = job_config.with_suffix('.lock')
    job = Job.load_from_file(job_config, job_lock)
    mine(job, job_lock)
