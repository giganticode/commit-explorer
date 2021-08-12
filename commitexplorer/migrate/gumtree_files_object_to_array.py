# Requires the PyMongo package.
# https://api.mongodb.com/python/current
from pymongo import MongoClient
from tqdm import tqdm

client = MongoClient('mongodb://10.10.20.160:27017/?readPreference=primary&appname=MongoDB%20Compass&directConnection=true&ssl=false')
result = client['commit_explorer']['commits'].find({'gumtree/3_0_0-beta2': {
    '$exists': True
}})

for commit in tqdm(result):
    if isinstance(commit["gumtree/3_0_0-beta2"], dict):
        lst = [{"file": key, **value} for key, value in  commit["gumtree/3_0_0-beta2"].items()]
        commit["gumtree/3_0_0-beta2"] = lst
        client['commit_explorer']['commits'].replace_one({'_id': commit['_id']}, commit)