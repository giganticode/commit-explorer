# Requires the PyMongo package.
# https://api.mongodb.com/python/current

from pymongo import MongoClient

client = MongoClient('mongodb://10.10.20.160:27017/?readPreference=primary&appname=MongoDB%20Compass&directConnection=true&ssl=false')
result = client['commit_explorer']['commits'].update_many({'$expr': {'$ne': [
    {
        '$getField': "refactoring_miner/2.1.0"
    }, None
]}}, [
    {
        '$set': {
            "refactoring_miner/2_1_0": {
                '$getField': "refactoring_miner/2.1.0"
            }
        }
    }, {
        '$replaceWith': {
            '$setField': {
                'field': "refactoring_miner/2.1.0",
                'input': '$$CURRENT',
                'value': '$$REMOVE'
            }
        }
    }
])
