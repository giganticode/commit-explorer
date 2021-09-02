import http.server
import socketserver
import re
import json

from pymongo import MongoClient

PORT = 8180

sha_regex=re.compile('[0-9a-f]{40}')

client = MongoClient('mongodb://localhost:27017')
commit_collection = client['commit_explorer']['commits']


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server, directory=None):
        super().__init__(request, client_address, server)

    def send200(self, payload):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        payload_bytes = json.dumps(payload).encode('utf-8')
        self.wfile.write(payload_bytes)

    def handle_commit(self):
        sha = self.path[11:]
        if not sha_regex.fullmatch(sha):
            return self.send_error(400, f'Invalid commit hashsum: {sha}')
        commit = commit_collection.find_one({'_id': sha})
        if commit is not None:
            self.send200(commit)
        else:
            return self.send_error(404, f"Commit {sha} not found")

    def handle_query(self):
        ids = [sha['_id'] for sha in commit_collection.find({'bohr.200k_commits': {"$exists": True}}, {"_id": 1})]
        print(f'Found {len(ids)} commits satisfying the query')
        self.send200(ids)

    def do_GET(self):
        if self.path.startswith('/ce/commit/'):
            self.handle_commit()
        elif self.path.startswith('/ce/query/'):
            self.handle_query()
        else:
            return http.server.SimpleHTTPRequestHandler.do_GET(self)


Handler = MyHttpRequestHandler
httpd = socketserver.TCPServer(("", PORT), Handler)
print("serving at port", PORT)
httpd.serve_forever()