import os
from pathlib import Path

from setuptools import find_packages, setup

bohr_framework_root = Path(__file__).parent


def version() -> str:
    with open(os.path.join(bohr_framework_root / "commitexplorer", "VERSION")) as version_file:
        return version_file.read().strip()


setup(
    name="commit-explorer",
    version=version(),
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.1,<9",
        "rich>=10.3.0,<11",
        "jsons>=1.4.2,<5",
        "PyGithub>=1.55,<2",
        "pygit2>=1.6.0,<2",
        "tqdm>=4.61.1,<5"
    ],
    entry_points="""
        [console_scripts]
        ce=commitexplorer.cli:ce
    """,
)
