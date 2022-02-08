import logging
import os
from configparser import ConfigParser

import click
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from commitexplorer import __version__, project_root
from commitexplorer import mine as m

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


logger = logging.getLogger(__name__)


def get_db():
    try:
        env = os.environ['ENV']
    except KeyError:
        env = 'prod'

    config = ConfigParser()
    config.read([project_root / 'config', project_root / 'config.local'])
    mongodb_uri = config[env]['mongodb_uri']
    mongodb_database_name = config[env]['mongodb_database_name']
    logger.info(f'Using env: {env}, mongodb_uri: {mongodb_uri}, database name: {mongodb_database_name}')

    db = MongoClient(mongodb_uri)[mongodb_database_name]
    return db


db = get_db()


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__)
def ce():
    pass


@ce.command()
@click.argument("sha")
def show(sha: str) -> None:
    try:
        commit = db.commits.find_one({'_id': sha})
        if commit is not None:
            print(commit)
        else:
            print(f"Commit with sha {sha} is not found")
    except ConnectionFailure:
        print(f"Connection to db failed")


@ce.command()
def mine() -> None:
    m.mine(db)


if __name__ == '__main__':
    ce()
