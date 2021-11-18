import logging
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Dict, Generator, Optional, Tuple, Set

import jsons
import pygit2
from jsons import DecodeError
from pygit2 import Repository, GIT_RESET_HARD, Commit
from tqdm import tqdm

from commitexplorer.common import Tool, clone_github_project, Project, Sha, path_to_working_dir, PATH_TO_TOOLS

logger = logging.getLogger(__name__)


class NoGeneratorFound(Exception):
    pass


class OtherError(Exception):
    def __init__(self, stderr: str):
        self.stderr = stderr


class UnknownError(Exception):
    pass


class ExternalProcessError(Exception):
    pass


class ToolNotInstalledError(Exception):
    pass


class GumTree(Tool): # rich commit data
    @staticmethod
    def parse_output(cmd, stdout: str, stderr: str, file: str) -> Optional[List[Dict]]:
        if "No generator found for file" in stderr:
            raise NoGeneratorFound()
        elif "Error loading file or folder" in stderr:
            print(f"Command: {cmd}")
            print(f'Error loading file or folder: {file}')
            print(stderr)
            raise RuntimeError()
        elif "SyntaxException" in stderr and "readStandardOutput" in stderr:
            print(f"Command: {cmd}")
            print(f'ExternalProcessError: {file}')
            raise ExternalProcessError()
        elif "java.io.IOException: Cannot run program" in stderr:
            print(f"Command: {cmd}")
            print(f'ToolNotInstalledError: {file}')
            raise ToolNotInstalledError()
        elif "NoViableAltException" in stderr or "java.util.ConcurrentModificationException" in stderr:
            print(f"Command: {cmd}")
            print(f'Unknown Error: {file}')
            print(stdout)
            print(stderr)
            raise OtherError(stderr)
        else:
            try:
                return jsons.loads(stdout)['actions']
            except DecodeError:
                print(f"Command: {cmd}")
                print(stdout)
                print(stderr)
                raise UnknownError()

    @staticmethod
    def copy_and_repo(path_to_cloned_dir: Path, path_to_copied_repo: Path, subfolder: str) -> Tuple[Repository, Path]:
        path_to_old_revision = Path(path_to_copied_repo) / subfolder
        shutil.copytree(path_to_cloned_dir, path_to_old_revision)
        return Repository(path_to_old_revision), path_to_old_revision

    def run_on_file(self, old_repo_path: Path, new_repo_path: Path, old_file: str, new_file: str, timeout: Optional[int] = None) -> Optional[Dict]:
        old_commit_path = Path(old_repo_path) / old_file
        new_commit_path = Path(new_repo_path) / new_file
        if not old_commit_path.exists():
            return {'status': 'ok', 'actions': [{'action': 'add-file'}]}
        if not new_commit_path.exists():
            return {'status': 'ok', 'actions': [{'action': 'remove-file'}]}

        cmd = ["./gumtree", "textdiff", str(old_commit_path), str(new_commit_path), '-f', 'json']
        try:
            python_parser_path = str(PATH_TO_TOOLS / 'pythonparser')
            my_env = {**os.environ, 'PATH': python_parser_path + os.pathsep + os.environ['PATH']}
            completed_process = subprocess.run(cmd, cwd=str(self.path), capture_output=True, check=True, timeout=timeout, env=my_env)
            output = completed_process.stdout.decode('utf-8')
            error_text = completed_process.stderr.decode('utf-8')
            result = self.parse_output(cmd, output, error_text, new_file)
            return {'status': 'ok', 'actions': result}
        except subprocess.TimeoutExpired:
            print(f"Warning: process {cmd} was interrupted because of the timeout.")
            return None

    def run_on_project(self, project: Project, commits_new_to_old: List[pygit2.Commit], timeout: Optional[int] = None, limited_to_shas: Optional[Set[Sha]] = None) -> Generator[Dict[Sha, Dict[str, Dict]], None, None]:
        # TODO implement limited_to_shas
        repo, metadata = clone_github_project(project, self.token, return_metadata=True)
        with TemporaryDirectory() as tmp_dir:
            working_directory = path_to_working_dir(repo)
            old_repo, old_repo_path = self.copy_and_repo(working_directory, tmp_dir, 'old')
            new_repo, new_repo_path = self.copy_and_repo(working_directory, tmp_dir, 'new')
            for i in tqdm(range(len(commits_new_to_old) - 1)):
                commit = commits_new_to_old[i]
                new_repo.reset(commit.hex, GIT_RESET_HARD)
                if i + 1 < len(commits_new_to_old):
                    previous_commit = commits_new_to_old[i + 1]
                    old_repo.reset(previous_commit.oid, GIT_RESET_HARD)
                else:
                    shutil.rmtree(old_repo_path)
                files = []
                for patch in commit.tree.diff_to_tree(previous_commit.tree):
                    delta = patch.delta
                    dct = {'file': delta.new_file.path}
                    try:
                        result = self.run_on_file(old_repo_path, new_repo_path, delta.old_file.path, delta.new_file.path)
                        dct['result'] = result
                        dct['status'] = 'ok'
                    except NoGeneratorFound:
                        dct['status'] = 'error-no-generator-found'
                    except ExternalProcessError:
                        dct['status'] = 'external-process-error'
                    except ToolNotInstalledError:
                        dct['status'] = 'tool-not-installed-error'
                    except OtherError:
                        dct['status'] = 'other-error'
                    except UnknownError:
                        dct['status'] = 'unknown-error'
                    files.append(dct)

                yield {commit.hex: files}

    def run_on_commit(self, commit: pygit2.Commit) -> List:
        raise NotImplemented()


