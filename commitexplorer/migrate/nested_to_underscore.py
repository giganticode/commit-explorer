# Requires the PyMongo package.
# https://api.mongodb.com/python/current
from pymongo import MongoClient

client = MongoClient('mongodb://10.10.20.160:27017/?readPreference=primary&appname=MongoDB%20Compass&directConnection=true&ssl=false')
result = client['commit_explorer']['commits'].update_many({'gumtree/3': {
        '$exists': True
    }}, [{
        '$unset': 'gumtree/3_0_0-beta2'
    }, {
        '$set': {
            'gumtree/3_0_0-beta2': '$$CURRENT.gumtree/3.0.0-beta2'
        }
    }, {
        '$unset': 'gumtree/3'
    }
])

