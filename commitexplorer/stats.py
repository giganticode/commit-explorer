import json
from pprint import pprint

from tqdm import tqdm

from commitexplorer.common import PATH_TO_STORAGE


def print_stats():
    total = 0
    stats = {
        "initial": {"present": 0, "processed": 0},
        "merge": {"present": 0, "processed": 0},
        "refactoring": {"present": 0, "processed": 0},
        "sstubs": {"present": 0, "processed": 0},
    }
    for i in tqdm(range(256)):
        for j in range(256):
            first_dir = format(i, 'x')
            second_dir = format(j, 'x')
            dir = PATH_TO_STORAGE / first_dir / second_dir
            if not dir.exists():
                continue
            for file in dir.iterdir():
                with file.open() as f:
                    js = json.load(f)
                    total += 1
                    if "refactoring_miner/2.1.0" in js:
                        stats['refactoring']['processed'] += 1
                        if js["refactoring_miner/2.1.0"]:
                            stats['refactoring']['present'] += 1

                    if "mine_sstubs/head" in js:
                        stats['sstubs']['processed'] += 1
                        if js["mine_sstubs/head"]:
                            stats['sstubs']['present'] += 1

                    if "special_commit_finder/0.1" in js and "initial" in js["special_commit_finder/0.1"]:
                        stats['initial']['processed'] += 1
                        if js["special_commit_finder/0.1"]["initial"]:
                            stats['initial']['present'] += 1

                    if "special_commit_finder/0.1" in js and "merge" in js["special_commit_finder/0.1"]:
                        stats['merge']['processed'] += 1
                        if js["special_commit_finder/0.1"]["merge"]:
                            stats['merge']['present'] += 1

        print("")
        print("")
        print(f'Scanned: {total}')
        pprint(stats)
    return None


print_stats()
