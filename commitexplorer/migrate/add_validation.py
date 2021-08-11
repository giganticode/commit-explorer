from collections import OrderedDict

from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/?readPreference=primary&appname=MongoDB%20Compass&directConnection=true&ssl=false')
db = client['commit_explorer_test']

sha_schema = {
                 'bsonType': 'string',
                 'pattern': '[0-9a-f]{40}'
             }

side_locations_schema = {
    'bsonType': 'array',
    'items': {
        'bsonType': 'object',
        'required': [
            'filePath', 'startLine', 'endLine', 'startColumn', 'endColumn', 'codeElement', 'codeElementType', 'description'
        ],
        'properties': {
            'filePath': {
                'bsonType': 'string'
            },
            'startLine': {
                'bsonType': 'int'
            },
            'endLine': {
                'bsonType': 'int'
            },
            'startColumn': {
                'bsonType': 'int'
            },
            'endColumn': {
                'bsonType': 'int'
            },
            'codeElement': {
                'anyOf': [
                    {
                        'bsonType': 'string'
                    }, {
                        'bsonType': 'null'
                    }
                ]
            },
            'codeElementType': {
                'bsonType': 'string'
            },
            'description': {
                'bsonType': 'string'
            }
        }
    }
}

commits_schema = {
    '$jsonSchema': {
        'bsonType': 'object',
        'required': [
            'owner', 'repo', '_id'
        ],
        'properties': {
            '_id': sha_schema,
            'owner': {
                'bsonType': 'string'
            },
            'repo': {
                'bsonType': 'string'
            },
            'special_commit_finder/0_1': {
                'bsonType': 'object',
                'required': [
                    'initial', 'merge'
                ],
                'properties': {
                    'initial': {
                        'bsonType': 'bool'
                    },
                    'merge': {
                        'bsonType': 'bool'
                    }
                }
            },
            'refactoring_miner/2_1_0': {
                'anyOf': [
                    {
                        'bsonType': 'array',
                        'items': {
                            'bsonType': 'object',
                            'required': [
                                'type', 'description', 'leftSideLocations', 'rightSideLocations'
                            ],
                            'properties': {
                                'type': {
                                    'bsonType': 'string'
                                },
                                'description': {
                                    'bsonType': 'string'
                                },
                                'leftSideLocations': side_locations_schema,
                                'rightSideLocations': side_locations_schema
                            }
                        }
                    }, {
                        'bsonType': 'object',
                        'required': [
                            'status'
                        ],
                        'properties': {
                            'status': {
                                'bsonType': 'string'
                            }
                        }
                    }
                ]
            },
            'mine_sstubs/head': {
                'bsonType': 'object',
                'required': [
                    'bugs', 'sstubs'
                ],
                'properties': {
                    'bugs': {
                        'bsonType': 'array',
                        'items': {
                            'bsonType': 'object',
                            'required': [
                                'fixCommitSHA1', 'fixCommitParentSHA1', 'bugFilePath', 'fixPatch', 'projectName', 'bugLineNum', 'bugNodeStartChar', 'bugNodeLength', 'fixLineNum', 'fixNodeStartChar', 'fixNodeLength', 'sourceBeforeFix', 'sourceAfterFix'
                            ],
                            'properties': {
                                'fixCommitSHA1': sha_schema,
                                'fixCommitParentSHA1': sha_schema,
                                'bugFilePath': {
                                    'bsonType': 'string'
                                },
                                'fixPatch': {
                                    'bsonType': 'string'
                                },
                                'projectName': {
                                    'bsonType': 'string'
                                },
                                'bugLineNum': {
                                    'bsonType': 'int'
                                },
                                'bugNodeStartChar': {
                                    'bsonType': 'int'
                                },
                                'bugNodeLength': {
                                    'bsonType': 'int'
                                },
                                'fixLineNum': {
                                    'bsonType': 'int'
                                },
                                'fixNodeStartChar': {
                                    'bsonType': 'int'
                                },
                                'fixNodeLength': {
                                    'bsonType': 'int'
                                },
                                'sourceBeforeFix': {
                                    'bsonType': 'string'
                                },
                                'sourceAfterFix': {
                                    'bsonType': 'string'
                                }
                            }
                        }
                    },
                    'sstubs': {
                        'bsonType': 'array'
                    }
                }
            },
            'gumtree/3_0_0-beta2': {
                'bsonType': 'array',
                'items': {
                    'bsonType': 'object',
                    'required': [
                        'file', 'status'
                    ],
                    'properties': {
                        'file': {
                            'bsonType': 'string'
                        },
                        'status': {
                            'bsonType': 'string'
                        },
                        'actions': {
                            'bsonType': 'array',
                            'items': {
                                'bsonType': 'object',
                                'required': [
                                    'action'
                                ],
                                'properties': {
                                    'action': {
                                        'bsonType': 'string'
                                    },
                                    'tree': {
                                        'bsonType': 'string'
                                    },
                                    'parent': {
                                        'bsonType': 'string'
                                    },
                                    'at': {
                                        'bsonType': 'int'
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

query = [('collMod', 'commits'),
         ('validator', commits_schema),
         ('validationLevel', 'strict'),
         ('validationAction', 'error')]
query = OrderedDict(query)
db.command(query)

runs_schema = {
    '$jsonSchema': {
        'bsonType': 'object',
        'required': [
            'tools', '_id'
        ],
        'properties': {
            '_id': {
                'bsonType': 'string'
            },
            'tools': {
                'bsonType': 'object',
                'properties': {
                    'special_commit_finder/0_1': {
                        'bsonType': 'string'
                    },
                    'refactoring_miner/2_1_0': {
                        'bsonType': 'string'
                    },
                    'mine_sstubs/head': {
                        'bsonType': 'string'
                    },
                    'gumtree/3_0_0-beta2': {
                        'bsonType': 'string'
                    }
                },
                'additionalProperties': False
            }
        }
    }
}

query = [('collMod', 'runs'),
         ('validator', runs_schema),
         ('validationLevel', 'strict'),
         ('validationAction', 'error')]
query = OrderedDict(query)
db.command(query)