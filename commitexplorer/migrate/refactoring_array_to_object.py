# Requires the PyMongo package.
# https://api.mongodb.com/python/current
from pymongo import MongoClient
from tqdm import tqdm

client = MongoClient('mongodb://10.10.20.160:27017/?readPreference=primary&appname=MongoDB%20Compass&directConnection=true&ssl=false')
result = client['commit_explorer']['commits'].find({'refactoring_miner/2_1_0': {
    '$exists': True
}})

for commit in tqdm(result):
    if isinstance(commit['refactoring_miner/2_1_0'], list):
        obj = {'status': 'ok', 'refactorings': commit['refactoring_miner/2_1_0']}
        commit['refactoring_miner/2_1_0'] = obj
        client['commit_explorer']['commits'].replace_one({'_id': commit['_id']}, commit)