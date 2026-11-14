"""Small local ERP simulator. No third-party Python dependencies."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = os.getenv('ERP_DB', '/data/erp.sqlite3')
TOKEN = os.getenv('ERP_API_TOKEN', '')
KINDS = ('products', 'orders', 'customers')


def connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
          CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          INSERT OR IGNORE INTO settings VALUES ('mode', 'pending');
          CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
            external_id TEXT NOT NULL, payload TEXT NOT NULL,
            status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS entities (
            kind TEXT NOT NULL, external_id TEXT NOT NULL,
            payload TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(kind, external_id));
        ''')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def accept(db, request_id):
    row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
    if row is None:
        raise ValueError('Request not found')
    # Upsert permits a failed request to be accepted later without duplicate entities.
    db.execute('''INSERT INTO entities VALUES (?,?,?,?)
      ON CONFLICT(kind, external_id) DO UPDATE SET payload=excluded.payload,
      updated_at=excluded.updated_at''', (row['kind'], row['external_id'], row['payload'], now()))
    db.execute("UPDATE requests SET status='accepted', error=NULL WHERE id=?", (request_id,))


def receive(kind, payload):
    if kind not in KINDS or not isinstance(payload, dict):
        raise ValueError('Expected a product, order or customer JSON object')
    external_id = payload.get('external_id')
    if not isinstance(external_id, (str, int)) or isinstance(external_id, bool) or not str(external_id).strip():
        raise ValueError('external_id is required')
    if len(str(external_id)) > 200:
        raise ValueError('external_id is too long')
    with connect() as db:
        mode = db.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]
        status = {'accept': 'accepted', 'fail': 'failed', 'pending': 'pending'}[mode]
        error = 'Simulated ERP failure' if mode == 'fail' else None
        cursor = db.execute('''INSERT INTO requests
          (kind,external_id,payload,status,error,created_at) VALUES (?,?,?,?,?,?)''',
          (kind, str(external_id), json.dumps(payload), status, error, now()))
        request_id = cursor.lastrowid
        if status == 'accepted':
            accept(db, request_id)
    return {'request_id': request_id, 'status': status, 'error': error}, (503 if mode == 'fail' else 202 if mode == 'pending' else 200)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, value, content_type='application/json'):
        content = json.dumps(value).encode() if content_type == 'application/json' else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/health':
            return self.respond(200, {'status': 'ok'})
        if path == '/':
            return self.respond(200, Path(__file__).with_name('index.html').read_bytes(), 'text/html; charset=utf-8')
        if path == '/dashboard':
            with connect() as db:
                mode = db.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]
                requests = [dict(row) for row in db.execute('SELECT * FROM requests ORDER BY id DESC LIMIT 200')]
                entities = [dict(row) for row in db.execute('SELECT * FROM entities ORDER BY updated_at DESC LIMIT 500')]
                counts = {kind: db.execute('SELECT COUNT(*) FROM entities WHERE kind=?', (kind,)).fetchone()[0] for kind in KINDS}
            return self.respond(200, {'mode': mode, 'requests': requests, 'entities': entities, 'counts': counts})
        return self.respond(404, {'error': 'Not found'})

    def do_POST(self):
        path = urlparse(self.path).path
        # Browser controls are same-origin; integration endpoints require the token.
        if path.startswith('/api/'):
            if not TOKEN or self.headers.get('Authorization') != f'Bearer {TOKEN}':
                return self.respond(401, {'error': 'Invalid API token'})
        elif path.startswith('/control/'):
            if self.headers.get('Origin') != f'http://{self.headers.get("Host")}':
                return self.respond(403, {'error': 'Same-origin browser request required'})
        else:
            return self.respond(404, {'error': 'Not found'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024 * 1024:
                return self.respond(413, {'error': 'JSON body must be between 1 byte and 1 MB'})
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('JSON object required')
            if path.startswith('/api/') and path.split('/')[-1] in KINDS:
                result, status = receive(path.split('/')[-1], payload)
                return self.respond(status, result)
            if path == '/control/mode':
                mode = payload.get('mode')
                if mode not in ('pending', 'accept', 'fail'):
                    raise ValueError('Choose pending, accept or fail')
                with connect() as db:
                    db.execute("UPDATE settings SET value=? WHERE key='mode'", (mode,))
                return self.respond(200, {'mode': mode})
            if path == '/control/decision':
                request_id = int(payload.get('id', 0))
                with connect() as db:
                    row = db.execute('SELECT status FROM requests WHERE id=?', (request_id,)).fetchone()
                    if row is None:
                        return self.respond(404, {'error': 'Request not found'})
                    if row['status'] == 'accepted':
                        return self.respond(409, {'error': 'Already accepted'})
                    if payload.get('decision') == 'accept':
                        accept(db, request_id)
                    elif payload.get('decision') == 'fail':
                        db.execute("UPDATE requests SET status='failed',error='Failed manually' WHERE id=?", (request_id,))
                    else:
                        raise ValueError('Choose accept or fail')
                return self.respond(200, {'status': 'updated'})
            if path == '/control/demo':
                kind = payload.get('kind', 'products')
                result, status = receive(kind, payload.get('payload'))
                return self.respond(status, result)
            return self.respond(404, {'error': 'Not found'})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            return self.respond(400, {'error': str(error)})
        except sqlite3.Error:
            return self.respond(500, {'error': 'ERP storage error'})


if __name__ == '__main__':
    if not TOKEN:
        raise SystemExit('ERP_API_TOKEN is required; run bin/setup before starting the stack.')
    initialize()
    ThreadingHTTPServer(('0.0.0.0', int(os.getenv('PORT', '8080'))), Handler).serve_forever()
