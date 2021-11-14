from commitexplorer.tools.gumtree import GumTree
from commitexplorer.tools.refactoring_miner import RefactoringMiner
from commitexplorer.tools.spacy import SpacyRunner
from commitexplorer.tools.special_commit_finder import SpecialCommitFinder
from commitexplorer.tools.sstubs import SStubs

tool_id_map = {
    'refactoring_miner': RefactoringMiner,
    'mine_sstubs': SStubs,
    'special_commit_finder': SpecialCommitFinder,
    'gumtree': GumTree,
    'spacy': SpacyRunner,
}