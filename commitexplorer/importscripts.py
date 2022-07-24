from pathlib import Path

import pandas as pd
import pymongo
import requests
from pymongo import MongoClient, UpdateOne
from pymongo.results import UpdateResult
from tqdm import tqdm


def import_levin(path, database):
    import_csv(path, 'levin', ['bug', 'label', 'ADDING_ATTRIBUTE_MODIFIABILITY', 'ADDING_CLASS_DERIVABILITY',
                               'ADDING_METHOD_OVERRIDABILITY', 'ADDITIONAL_CLASS', 'ADDITIONAL_FUNCTIONALITY',
                               'ADDITIONAL_OBJECT_STATE', 'ALTERNATIVE_PART_DELETE', 'ALTERNATIVE_PART_INSERT',
                               'ATTRIBUTE_RENAMING', 'ATTRIBUTE_TYPE_CHANGE', 'CLASS_RENAMING', 'COMMENT_DELETE',
                               'COMMENT_INSERT', 'COMMENT_MOVE', 'COMMENT_UPDATE', 'CONDITION_EXPRESSION_CHANGE',
                               'DECREASING_ACCESSIBILITY_CHANGE', 'DOC_DELETE', 'DOC_INSERT', 'DOC_UPDATE',
                               'INCREASING_ACCESSIBILITY_CHANGE', 'METHOD_RENAMING', 'PARAMETER_DELETE',
                               'PARAMETER_INSERT', 'PARAMETER_ORDERING_CHANGE', 'PARAMETER_RENAMING',
                               'PARAMETER_TYPE_CHANGE', 'PARENT_CLASS_CHANGE', 'PARENT_CLASS_DELETE',
                               'PARENT_CLASS_INSERT', 'PARENT_INTERFACE_CHANGE', 'PARENT_INTERFACE_DELETE',
                               'PARENT_INTERFACE_INSERT', 'REMOVED_CLASS', 'REMOVED_FUNCTIONALITY',
                               'REMOVED_OBJECT_STATE', 'REMOVING_ATTRIBUTE_MODIFIABILITY',
                               'REMOVING_CLASS_DERIVABILITY', 'REMOVING_METHOD_OVERRIDABILITY', 'RETURN_TYPE_CHANGE',
                               'RETURN_TYPE_DELETE', 'RETURN_TYPE_INSERT', 'STATEMENT_DELETE', 'STATEMENT_INSERT',
                               'STATEMENT_ORDERING_CHANGE', 'STATEMENT_PARENT_CHANGE', 'STATEMENT_UPDATE',
                               'UNCLASSIFIED_CHANGE'], database)


def import_herzig(path, database):
    import_csv(path, 'herzig', ['bug', 'ID', 'CLASSIFIED', 'TYPE'], database)


def import_berger(path, database):
    import_csv(path, 'berger', ['bug'], database)


def import_mauczka(path, database):
    import_csv(path, 'mauczka', ['sw_corrective', 'sw_perfective', 'nfr_maintainability', 'nfr_usability',
                                'nfr_functionality', 'nfr_reliability', 'nfr_efficiency', 'nfr_portability',
                                'nfr_none', 'hl_forward', 'hl_reengineering', 'hl_corrective', 'hl_management'], database)


def import_krasniqi(path, database):
    import_csv(path, 'krasniqi', ['refactoring_class', 'refactoring_type'], database)


def import_bohr_manual_label_hlib(path_labels, path_commits, database):
    operations = []
    commits = pd.read_csv(path_commits)
    links = pd.read_csv(path_labels)
    merged = pd.merge(commits, links, on='commit_id')
    for row in merged.iterrows():
        update = {'$set': {'manual_labels.bohr.hlib': {'label': row[1]['label'],
                           'note': row[1]['note'] if not pd.isna(row[1]['note']) else None,
                           'certainty': row[1]['certainty'] if not pd.isna(row[1]['certainty']) else None,
                           'showcase': True if not pd.isna(row[1]['showcase']) and row[1]['showcase'] else False}}}
        operations.append(UpdateOne({"_id": row[1]['sha']}, update, upsert=True))
    database.commits.bulk_write(operations)


def import_200k_issues(path_issues, path_commits, path_links, database):
    operations = []
    operations_issues = []
    columns = ['title', 'body', 'labels']
    issues = pd.read_csv(path_issues)
    commits = pd.read_csv(path_commits)
    links = pd.read_csv(path_links)
    merged = pd.merge(pd.merge(commits, links, on='commit_id'), issues, on='issue_id')
    for row in merged.iterrows():
        update1 = {'$set': {column: row[1][column] if not pd.isna(row[1][column]) else None for column in columns}}
        id = f'github://{row[1]["owner_y"]}/{row[1]["repository_y"]}{row[1]["identifier"]}'
        operations_issues.append(UpdateOne({"_id": id}, update1, upsert=True))
        update = {'$set': {"links.bohr.issues": [id]}}
        operations.append(UpdateOne({"_id": row[1]['sha_x']}, update, upsert=True))

    database.issues.bulk_write(operations_issues)
    database.commits.bulk_write(operations)


def import_200k(path_commits, path_files, database):
    operations = []
    commits = pd.read_csv(path_commits)
    for row in commits.iterrows():
        update = {'$set': {"message": row[1]['message'], "bohr.200k_commits": True}, '$unset': {"files": ""}}
        if 'owner' in row[1] and not pd.isna(row[1]['owner']):
            update['$set']['owner'] = row[1]['owner']
        if 'repository' in row[1] and not pd.isna(row[1]['repository']):
            update['$set']['repo'] = row[1]['repository']
        operations.append(UpdateOne({"_id": row[1]['sha']}, update, upsert=True))
    files = pd.read_csv(path_files)
    merged = pd.merge(files, commits, on='commit_id')
    columns_to_add = ['filename', 'status', 'previous_filename', 'patch', 'change']
    for row in merged.iterrows():
        if not pd.isna(row[1]['filename']):
            update = {'$push': {"files": {name: row[1][name] for name in columns_to_add if not pd.isna(row[1][name])}}}
            operations.append(UpdateOne({"_id": row[1]['sha']}, update, upsert=True))
        else:
            print(f'NaN: {row[1]["sha"]}')

    database.commits.bulk_write(operations)


def import_herzig_tangled(database):
    a = requests.get('https://raw.githubusercontent.com/kimherzig/untangling_changes/master/atomic_fixes/jruby/jruby_atomic_fixes.csv')
    atomic_shas = a.text.split('\n')
    count = 0
    for sha in atomic_shas:
        update_result = database.commits.update_one({'_id': sha}, {"$set": {"manual_labels.herzig_tangled.tangled": False}})
        if update_result.raw_result['n'] == 1:
            count += 1
        else:
            print(f'Not foudn sha: {sha}')

    print(f'Set {count} out of {len(atomic_shas)} atomic commits')

    b = requests.get('https://raw.githubusercontent.com/kimherzig/untangling_changes/master/obvious_blobs/jruby/jruby_obvious_blobs.csv')
    lines = b.text.split('\n')[1:]
    blob_shas = [line.split(',')[0] for line in lines]
    count_blobs = 0
    for sha in blob_shas:
        update_result = database.commits.update_one({'_id': sha}, {"$set": {"manual_labels.herzig_tangled.tangled": True}})
        if update_result.raw_result['n'] == 1:
            count_blobs += 1

    print(f'Set {count_blobs} out of {len(blob_shas)} tangled commits')



def import_csv(path, name, columns, database):
    df = pd.read_csv(path)
    operations = []
    for row in df.iterrows():
        update = {'$set': {"message": row[1]['message']}}
        if 'owner' in row[1] and not pd.isna(row[1]['owner']):
            update['$set']['owner'] = row[1]['owner']
        if 'repository' in row[1] and not pd.isna(row[1]['repository']):
            update['$set']['repo'] = row[1]['repository']
        if len(columns) > 0:
            update['$set']["manual_labels"] = {name: {l: row[1][l] for l in columns}}
        operations.append(UpdateOne({"_id": row[1]['sha']}, update, upsert=True))
    print(f"Writing {len(operations)} records to db ...")
    database.commits.bulk_write(operations)


def import_idan(database):
    with dvc.api.open('data/random_batch_18_nov_2020.csv', repo='https://github.com/evidencebp/commit-classification', rev='bfffa8700f6263719d52db979ef9d235c974a543') as f:
        df = pd.read_csv(f)
    df = df[df['Is_Refactor'].astype(str) != 'nan']

    operations = []

    def str_to_bool(s):
        if s in ['TRUE', True]:
            return True
        elif s in ['flase', 'FALSE', False]:
            return False
        else:
            raise ValueError(f'{s}')


    for _, item in tqdm(df.iterrows()):
        owner, repo = item['repo_name'].split('/')
        update = {'$set': {
            'message': item['message'],
            'owner': owner,
            'repo': repo,
            'idan/0_1': {},
        }}
        fields = ['Is_Refactor', 'Is_Perfective', 'Is_Adaptive', 'Is_Corrective']
        for field in fields:
            if not pd.isna(item[field]):
                update['$set']['idan/0_1'][field] = str_to_bool(item[field])
        fields_str = ['Justification', 'Comment']
        for field in fields_str:
            if not pd.isna(item[field]):
                update['$set']['idan/0_1'][field] = item[field]
        operations.append(UpdateOne({"_id": item['commit']}, update, upsert=True))


    database.bulk_write(operations)


def import_all():
    path_to_dir = Path('/Users/hlib/dev/bohr/data')
    path_to_200k_commits = path_to_dir / '200k-commits.csv'
    path_to_200k_commits_issues = path_to_dir / '200k-commits-issues.csv'
    path_to_200k_commits_files = path_to_dir / '200k-commits-files.csv'
    path_to_200k_commits_link_issues = path_to_dir / '200k-commits-link-issues.csv'
    path_to_200k_commits_manual_labels = path_to_dir / '200k-commits-manual-labels.csv'
    path_to_berger = path_to_dir / 'berger.csv'
    path_to_herzig = path_to_dir / 'herzig.csv'
    path_to_levin = path_to_dir / '1151-commits.csv'
    path_to_krasniqi = path_to_dir / 'fine-grained-refactorings.csv'
    path_to_mauczka = path_to_dir / 'developer-labeled.csv'

    database = MongoClient('mongodb://10.10.20.160:27017')['commit_explorer']

    # import_200k(path_to_200k_commits, path_to_200k_commits_files, database)
    # import_berger(path_to_berger, database)
    # import_herzig(path_to_herzig, database)
    # import_levin(path_to_levin, database)
    # import_krasniqi(path_to_krasniqi, database)
    import_mauczka(path_to_mauczka, database)
    # import_200k_issues(path_to_200k_commits_issues, path_to_200k_commits, path_to_200k_commits_link_issues, database)
    # import_bohr_manual_label_hlib(path_to_200k_commits_manual_labels, path_to_200k_commits, database)

    database.commits.create_index([("bohr.200k_commits", pymongo.ASCENDING)])
    database.commits.create_index([("manual_labels.berger", pymongo.ASCENDING)])
    database.commits.create_index([("manual_labels.herzig", pymongo.ASCENDING)])
    database.commits.create_index([("manual_labels.levin", pymongo.ASCENDING)])
    database.commits.create_index([("manual_labels.krasniqi", pymongo.ASCENDING)])
    database.commits.create_index([("manual_labels.import_mauczka", pymongo.ASCENDING)])
    database.commits.create_index([("manual_labels.manual_labels.bohr.hlib", pymongo.ASCENDING)])
    database.commits.create_index([("idan/0_1", pymongo.ASCENDING)])


if __name__ == '__main__':
    database = MongoClient('mongodb://localhost:27017')['commit_explorer_test']
    import_herzig_tangled(database)