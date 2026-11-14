import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('erp_server', Path(__file__).parents[1] / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        server.DB_PATH = os.path.join(self.directory.name, 'test.sqlite3')
        server.initialize()

    def tearDown(self):
        self.directory.cleanup()

    def mode(self, mode):
        with server.connect() as db:
            db.execute("UPDATE settings SET value=? WHERE key='mode'", (mode,))

    def test_pending_does_not_create_entity_until_accepted(self):
        result, status = server.receive('products', {'external_id': '12', 'sku': 'DEMO'})
        self.assertEqual(status, 202)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM entities').fetchone()[0], 0)
            server.accept(db, result['request_id'])
            self.assertEqual(db.execute('SELECT count(*) FROM entities').fetchone()[0], 1)

    def test_failure_is_recorded_and_can_be_accepted_later(self):
        self.mode('fail')
        result, status = server.receive('orders', {'external_id': '42', 'total': 20})
        self.assertEqual(status, 503)
        with server.connect() as db:
            row = db.execute('SELECT * FROM requests').fetchone()
            self.assertEqual(row['status'], 'failed')
            self.assertEqual(db.execute('SELECT count(*) FROM entities').fetchone()[0], 0)
            server.accept(db, result['request_id'])
            self.assertEqual(db.execute('SELECT status FROM requests').fetchone()[0], 'accepted')

    def test_repeated_updates_do_not_duplicate_entities(self):
        self.mode('accept')
        for name in ('First', 'Updated'):
            _, status = server.receive('customers', {'external_id': '7', 'firstname': name})
            self.assertEqual(status, 200)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM entities').fetchone()[0], 1)
            self.assertEqual(json.loads(db.execute('SELECT payload FROM entities').fetchone()[0])['firstname'], 'Updated')
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 2)

    def test_missing_id_and_invalid_entity_rejected(self):
        for kind, payload in [('products', {}), ('other', {'external_id': 1}), ('orders', {'external_id': True})]:
            with self.assertRaises(ValueError):
                server.receive(kind, payload)

if __name__ == '__main__':
    unittest.main()
