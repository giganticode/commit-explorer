import logging

import click

from commitexplorer import __version__, project_root
from commitexplorer.load import load_commit
from commitexplorer import mine as m

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


logger = logging.getLogger(__name__)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__)
def ce():
    pass


@ce.command()
@click.argument("sha")
def show(sha: str) -> None:
    try:
        print(load_commit(sha))
    except FileNotFoundError:
        print(f"Commit with sha {sha} is not found")


@ce.command()
def mine() -> None:
    job_config = project_root / 'job.json'
    job_lock = job_config.with_suffix('.lock')
    job = m.Job.load_from_file(job_config, job_lock)
    m.mine(job, job_lock)
