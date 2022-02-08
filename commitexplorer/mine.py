import json
import logging
import os
import traceback
from dataclasses import dataclass
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple, Set, Optional, Union

from pygit2 import Repository, Commit
from tqdm import tqdm

from commitexplorer import project_root
from commitexplorer.common import Tool, clone_project, Sha, GithubProject, GitProject, ProjectObj
from commitexplorer.db import save_results, mark_project_as_run, get_already_explored_commits, \
    get_tools_not_run_on_project, get_important_commits
from commitexplorer.tools import tool_id_map


logger = logging.getLogger(__name__)


@dataclass
class Job:
    tools: List[str]
    project: Union[GithubProject, GitProject]
    limited_to_shas: Optional[Set[Sha]]


@dataclass
class JobList:
    tools: List[str]
    projects: Dict[Union[GithubProject, GitProject], Optional[Set[Sha]]]

    def __iter__(self) -> Job:
        for project, limited_to_shas in sorted(self.projects.items(), key=lambda p: p[0].get_repo_id()):
            yield Job(self.tools, project, limited_to_shas)

    def __len__(self):
        return len(self.projects)

    @staticmethod
    def from_projects(project_names: List[str]) -> Dict[ProjectObj, Optional[Set[Sha]]]:
        projects = {}
        for project_id in project_names:
            if project_id.endswith('.git'):
                projects[GitProject(project_id)] = None
            else:
                owner_and_repo = project_id.split('/')
                if len(owner_and_repo) != 2:
                    raise ValueError(f'Invalid job file; invalid project id: {project_id}')
                projects[GithubProject(owner_and_repo[0], owner_and_repo[1])] = None
        return projects

    @classmethod
    def load_from_file(cls, path: Path, database) -> 'JobList':

        with open(path, 'r') as f:
            config = json.load(f)

        if 'projects' in config:
            projects = JobList.from_projects(config['projects'])
        elif 'commit-query' in config:
            logger.info('Commit query is passed. Quering commits that need to be mined ...')
            projects = get_important_commits(database, config['commit-query'])
            n_commits = len([c for project_commits in projects.values() for c in project_commits])
            logger.info(f'Running tools for {n_commits} commits ...')
        else:
            raise ValueError(f'Invalid job.json. Neither projects no commit-query field was found.')

        return cls(config['tools'], projects)


def get_tool_by_id(id: str) -> Tool:
    id_parts = id.split('/')
    tool_id, version = id_parts if len(id_parts) == 2 else (id_parts[0], None)
    if tool_id not in tool_id_map:
        raise ValueError(f'Unknown tool: {tool_id}. Check job.json file')
    tool_class = tool_id_map[tool_id]
    tool = tool_class(version)
    return tool


def get_all_commits(repo: Repository) -> List[Commit]:
    if repo.is_empty:
        logger.warning(f'Repo at {repo.path} has no commits.')
        return []
    all_commits = [commit for commit in repo.walk(repo.head.target)]
    return all_commits


def run_tools_on_project(tools: List[Tuple[str, Tool]], project: GithubProject, repo: Repository, database, limited_to_shas: Optional[Set[Sha]] = None) -> Generator:
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
                logger.info(f"Tool {tool_id} is already run on all commits ... marking the project as run ")
            else:
                if commit_to_start_from > 0:
                    logger.info(f'Tool has already run on some commits, starting running tool {tool_id} '
                          f'on commit number {commit_to_start_from} counting from the newest ({all_commits_from_newest[commit_to_start_from].hex})')
                for result_batch in tool.run_on_project(project, all_commits_from_newest[commit_to_start_from:], limited_to_shas):
                    commit_results: Dict[Sha, Dict[str, Any]] = {}
                    for sha, commit_result in result_batch.items():
                        if sha not in commit_result:
                            commit_results[sha] = {}
                        commit_results[sha][tool_id] = commit_result
                    yield commit_results
            if limited_to_shas is None:
                mark_project_as_run(project, tool_id, database)
        except Exception as ex:
            logger.exception(f"Exception: {type(ex).__name__}, {ex}, skipping tool: {tool_id}  (project: {project})")
            traceback.print_tb(ex.__traceback__)


def run_job(param):
    job, database = param
    with open(project_root / 'github.token') as f:
        token = f.read().strip()
    try:
        repo = clone_project(job.project, token)
        if repo is not None:
            tool_ids__to_run = get_tools_not_run_on_project(job.tools, job.project, database)
            if tool_ids__to_run:
                tools_to_run = [(tool_id, get_tool_by_id(tool_id)) for tool_id in job.tools]
                for result_batch in run_tools_on_project(tools_to_run, job.project, repo, database, job.limited_to_shas):
                    save_results(result_batch, job.project, database)
            else:
                logger.info(f'Skipping {job.project}. Tools has been already run')
            return job.project
    except Exception as ex:
        logger.exception(f"Exception: {type(ex).__name__}, {ex}, skipping project: {job.project}")
        traceback.print_tb(ex.__traceback__)


def mine(database):
    job_config = project_root / 'job.json'
    job_list = JobList.load_from_file(job_config, database)

    n_processes = os.cpu_count() // 2
    logger.info(f"Using {n_processes} processes")
    with ThreadPool(processes=n_processes) as pool:
        job_parameters = [(job, database) for job in job_list]
        it = pool.imap_unordered(run_job, job_parameters, chunksize=1)
        for _ in tqdm(it, total=len(job_parameters), desc="Jobs: "):
            pass