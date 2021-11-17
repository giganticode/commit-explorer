from typing import List, Generator, Dict, Any, Optional

from pydriller import Repository, ModificationType

from commitexplorer.common import Tool, Commit, Project, Sha, clone_github_project, path_to_working_dir
from commitexplorer.util.accuratechanges import calculate_changes


class FileMiner(Tool):
    @staticmethod
    def _get_status(self, file) -> str:
        if file.old_path is None and file.new_path is None:
            raise AssertionError('Both old and new paths cannot be empty.')
        if file.old_path is None:
            return 'added'
        if file.new_path is None:
            return 'removed'
        # if file.

    def run_on_project(self, project: Project, all_shas: List[Commit]) -> Generator[Dict[Sha, Any], None, None]:
        if len(all_shas) == 0:
            yield {}
            return

        repo = clone_github_project(project)
        working_dir = str(path_to_working_dir(repo))
        # yield {commit.hash: [(file.) for file in commit.modified_files] for commit in Repository(working_dir).traverse_commits()}
        for commit in Repository(working_dir).traverse_commits():
            res = []
            for file in commit.modified_files:
                file_data = {'patch': file.diff,
                             'changes': calculate_changes(file.diff),
                             'filename': file.new_path if file.new_path else file.old_path}
                if file.change_type == ModificationType.RENAME:
                    file_data['previous_filename'] = file.old_path
                modification_type_to_status = {
                    ModificationType.ADD: 'added',
                    ModificationType.RENAME: 'renamed',
                    ModificationType.DELETE: 'removed',
                    ModificationType.MODIFY: 'modified'
                }
                if file.change_type in modification_type_to_status:
                    file_data['status'] = modification_type_to_status[file.change_type]
                else:
                    file_data['status'] = None
                res.append(file_data)
            yield {commit.hash: res}

    def run_on_commit(self, commit: Commit):
        raise NotImplemented()


if __name__ == '__main__':
    from pprint import pprint
    for a in FileMiner('1').run_on_project(Project('giganticode', 'bohr'), ['1']):
        pprint(a)