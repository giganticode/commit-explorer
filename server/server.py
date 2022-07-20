import http.server
import socketserver
import re
import json

from pymongo import MongoClient

PORT = 8180

sha_regex=re.compile('[0-9a-f]{40}')

client = MongoClient('mongodb://localhost:27017')
commit_collection = client['commit_explorer']['commits']
issue_collection = client['commit_explorer']['issues']


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server, directory=None):
        super().__init__(request, client_address, server)
        super().__init__(request, client_address, server)

    def send200(self, payload):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        payload_bytes = json.dumps(payload).encode('utf-8')
        self.wfile.write(payload_bytes)

    def handle_commit(self):
        sha = self.path[len('/art-exp/commit/'):]
        if not sha_regex.fullmatch(sha):
            return self.send_error(400, f'Invalid commit hashsum: {sha}')
        commit = commit_collection.find_one({'_id': sha})
        if commit is None:
            return self.send_error(404, f"Commit {sha} not found")
        try:
            issue_ids = commit['links']['bohr']['issues']
            issues = [issue_collection.find_one({'_id': issue_id}) for issue_id in issue_ids]
            commit['linked_issues'] = issues
        except KeyError:
            pass
        self.send200(commit)


    def handle_query(self):
        collection_id = self.path[len('/art-exp/query/'):]
        ids = [sha['_id'] for sha in commit_collection.find({collection_id: {"$exists": True}}, {"_id": 1})]
        print(f'Found {len(ids)} commits satisfying the query')
        self.send200(ids)

    def do_GET(self):
        if self.path.startswith('/art-exp'):
            if self.path.startswith('/art-exp/commit/'):
                self.handle_commit()
            elif self.path.startswith('/art-exp/query/'):
                self.handle_query()
            else:
                return self.send_error(404, f"Path not found: {self.path}")
        else:
            return http.server.SimpleHTTPRequestHandler.do_GET(self)


Handler = MyHttpRequestHandler
httpd = socketserver.TCPServer(("", PORT), Handler)
print("serving at port", PORT)
httpd.serve_forever()

