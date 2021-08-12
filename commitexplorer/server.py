#!/usr/bin/env python3
import http.server
import socketserver
import re

from pymongo import MongoClient

PORT = 8180

sha_regex=re.compile('[0-9a-f]{40}')

client = MongoClient('mongodb://localhost:27017')
commit_collection = client['commit_explorer']['commits']


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server, directory=None):
        super().__init__(request, client_address, server)

    def do_GET(self):
        if self.path.startswith('/ce/'):
            sha = self.path[4:]
            if not sha_regex.fullmatch(sha):
                return self.send_error(400, f'Invalid commit hashsum: {sha}')
            commit = commit_collection.find_one({'_id': sha})
            if commit is not None:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(commit)
            else:
                return self.send_error(404, f"Commit {sha} not found")

        else:
            return http.server.SimpleHTTPRequestHandler.do_GET(self)


Handler = MyHttpRequestHandler
httpd = socketserver.TCPServer(("", PORT), Handler)
print("serving at port", PORT)
httpd.serve_forever()