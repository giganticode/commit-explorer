import json
import os
import traceback
from dataclasses import dataclass
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple

from pygit2 import Repository, Commit
from pymongo import MongoClient
from tqdm import tqdm

from commitexplorer import project_root
from commitexplorer.common import Tool, clone_github_project, Sha, Project
from commitexplorer.db import save_results, mark_project_as_run, get_already_explored_commits, \
    get_tools_not_run_on_project
from commitexplorer.tools import tool_id_map


@dataclass
class Job:
    tools: List[str]
    project: Project


@dataclass
class JobList:
    tools: List[str]
    projects: List[Project]

    def __iter__(self) -> Job:
        for project in self.projects:
            yield Job(self.tools, project)

    def __len__(self):
        return len(self.projects)

    @classmethod
    def load_from_file(cls, path: Path) -> 'JobList':

        with open(path, 'r') as f:
            config = json.load(f)

        projects = []
        for ps in config['projects']:
            owner_and_repo = ps.split('/')
            if len(owner_and_repo) != 2:
                raise ValueError(f'Invalid job file; invalid project id: {ps}')
            projects.append(Project(owner_and_repo[0], owner_and_repo[1]))

        return cls(config['tools'], projects)


def get_tool_by_id(id: str) -> Tool:
    tool_id, version = id.split('/')
    if tool_id not in tool_id_map:
        raise ValueError(f'Unknown tool: {tool_id}. Check job.json file')
    tool_class = tool_id_map[tool_id]
    tool = tool_class(version)
    return tool


def get_all_commits(repo: Repository) -> List[Commit]:
    if repo.is_empty:
        print(f'Warning: repo at {repo.path} has no commits.')
        return []
    all_commits = [commit for commit in repo.walk(repo.head.target)]
    return all_commits


def run_tools_on_project(tools: List[Tuple[str, Tool]], project: Project, repo: Repository, database) -> Generator:
    all_commits_from_newest = get_all_commits(repo)
    for tool_id, tool in tools:
        try:
            already_explored_commits = get_already_explored_commits(all_commits_from_newest, tool_id, database)
            commit_to_start_from = len(all_commits_from_newest)
            for i, commit in enumerate(all_commits_from_newest):
                if commit.hex not in already_explored_commits:
                    commit_to_start_from = i
                    break
            if commit_to_start_from == len(all_commits_from_newest):
                print(f"Tool {tool_id} is already run on all commits ... marking the project as run ")
            else:
                if commit_to_start_from > 0:
                    print(f'Tool has already run on some commits, starting running tool {tool_id} '
                          f'on commit number {commit_to_start_from} counting from the newest ({all_commits_from_newest[commit_to_start_from].hex})')
                for result_batch in tool.run_on_project(project, all_commits_from_newest[commit_to_start_from:]):
                    commit_results: Dict[Sha, Dict[str, Any]] = {}
                    for sha, commit_result in result_batch.items():
                        if sha not in commit_result:
                            commit_results[sha] = {}
                        commit_results[sha][tool_id] = commit_result
                    yield commit_results
            mark_project_as_run(project, tool_id, database)
        except Exception as ex:
            print(f"Exception: {type(ex).__name__}, {ex}, skipping tool: {tool_id}  (project: {project})")
            traceback.print_tb(ex.__traceback__)


def run_job(param):
    job, database = param
    with open(project_root / 'github.token') as f:
        token = f.read().strip()
    try:
        repo = clone_github_project(job.project, token)
        if repo is not None:
            tool_ids__to_run = get_tools_not_run_on_project(job.tools, job.project, database)
            if tool_ids__to_run:
                tools_to_run = [(tool_id, get_tool_by_id(tool_id)) for tool_id in job.tools]
                for result_batch in run_tools_on_project(tools_to_run, job.project, repo, database):
                    save_results(result_batch, job.project, database)
            else:
                print(f'Skipping {job.project}. Tools has been already run')
            return job.project
    except Exception as ex:
        print(f"Exception: {type(ex).__name__}, {ex}, skipping project: {job.project}")
        traceback.print_tb(ex.__traceback__)


def mine(database):
    job_config = project_root / 'job.json'
    job_list = JobList.load_from_file(job_config)

    n_processes = os.cpu_count() // 2
    print(f"Using {n_processes} processes")
    with ThreadPool(processes=n_processes) as pool:
        it = pool.imap_unordered(run_job, [(job, database) for job in job_list], chunksize=1)
        for _ in tqdm(it, total=len(job_list)):
            pass


if __name__ == '__main__':
    mine(MongoClient('mongodb://localhost:27017')['commit_explorer_test'])
