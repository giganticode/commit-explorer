import json
from pprint import pprint
from random import random, shuffle
from typing import Optional, Dict, Tuple

from commitexplorer.common import PATH_TO_STORAGE


def get_random_commit(with_key: str) -> Optional[Tuple[str, Dict]]:
    attempts = 100000
    for _ in range(attempts):
        first_dir = format(int(random() * 0xff), 'x')
        second_dir = format(int(random() * 0xff), 'x')
        dir = PATH_TO_STORAGE / first_dir / second_dir
        if not dir.exists():
            continue
        all_files = [f for f in dir.iterdir()]
        shuffle(all_files)
        for file in all_files:
            with file.open() as f:
                js = json.load(f)
                if with_key in js and js[with_key]:
                    sha = first_dir + second_dir + file.name
                    url = f'https://github.com/{js["owner"]}/{js["repo"]}/commit/{sha}'
                    return url, js
    return None


file, js = get_random_commit('refactoring_miner/2.1.0')
print(file)
pprint(js)

print("======")
file, js = get_random_commit('mine_sstubs/head')
print(file)
pprint(js)