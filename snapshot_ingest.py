"""Bounded local snapshot staging for fixtures and explicitly supplied Sandbox samples.

No provider client, public endpoint, background service, or customer-data access.
SQLite is a stdlib disk index/checkpoint, not a new deployed database service.
Transport completeness never proves an atomic snapshot at a mutable provider.
"""
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _time(value):
    if not isinstance(value, str):
        raise ValueError('Snapshot timestamp missing')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Snapshot timestamp invalid') from None
    if parsed.tzinfo is None:
        raise ValueError('Snapshot timestamp needs timezone')
    return parsed


def _nested_complete(value, depth=0):
    if depth > 20:
        raise ValueError('Snapshot nested depth exceeded')
    if isinstance(value, dict):
        if 'nodes' in value or 'edges' in value:
            info = value.get('pageInfo')
            if not isinstance(info, dict) or info.get('hasNextPage') is not False:
                raise ValueError('Snapshot nested pagination incomplete')
        for child in value.values():
            _nested_complete(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _nested_complete(child, depth + 1)


class SnapshotStore:
    """One immutable scope, <=100k records, <=250/page, <=64KiB/record, <=256MiB.

    Callers supply already authorized records. Scope equality is a local binding,
    not authentication or permission to fetch a merchant's data.
    """
    def __init__(self, path, scope, *, expected_count):
        if type(expected_count) is not int or not 0 <= expected_count <= 100000:
            raise ValueError('Snapshot count outside controlled limit')
        required = {'tenant_id', 'provider', 'source_id', 'entity', 'window_start',
                    'window_end', 'snapshot_id', 'evidence_kind'}
        if not isinstance(scope, dict) or set(scope) != required:
            raise ValueError('Snapshot scope incomplete')
        if (scope['evidence_kind'] not in ('synthetic_fixture', 'sandbox_sample')
                or not isinstance(scope['snapshot_id'], str)
                or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', scope['snapshot_id'])):
            raise ValueError('Snapshot evidence scope unsupported')
        if str(uuid.UUID(scope['tenant_id'])) != scope['tenant_id']:
            raise ValueError('Snapshot tenant invalid')
        if scope['provider'] == 'qbo_sandbox':
            valid = re.fullmatch(r'[0-9]{1,32}', scope['source_id']) and scope['entity'] in (
                'Invoice', 'Payment', 'CreditMemo', 'PurchaseOrder', 'Bill')
        elif scope['provider'] == 'shopify':
            valid = re.fullmatch(r'[a-z0-9][a-z0-9-]{0,61}\.myshopify\.com', scope['source_id']) and scope['entity'] == 'Order'
            if expected_count > 25000:
                raise ValueError('Shopify snapshot needs disjoint windows of at most 25000 records')
        else:
            valid = False
        if not valid or _time(scope['window_start']) >= _time(scope['window_end']):
            raise ValueError('Snapshot provider/window invalid')
        self.scope = json.loads(_json(scope))
        self.expected_count = expected_count
        self.path = Path(path).absolute()
        if (not self.path.parent.is_dir() or self.path.parent.stat().st_mode & 0o077
                or any(parent.is_symlink() for parent in self.path.parents)):
            raise ValueError('Snapshot directory must be private and non-symlink')
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        self._check_file()
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS pages (number INTEGER PRIMARY KEY, cursor TEXT, digest TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS records (seq INTEGER PRIMARY KEY, record_id TEXT UNIQUE NOT NULL, reference TEXT, payload TEXT NOT NULL, digest TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS record_reference ON records(reference)')
            found = db.execute('SELECT value FROM metadata WHERE id=1').fetchone()
            if found:
                self._bound(json.loads(found[0]))
            else:
                state = {'scope': self.scope, 'expected_count': expected_count, 'records': 0,
                         'pages': 0, 'next_cursor': None, 'bytes': 0, 'complete': False,
                         'page_chain_sha256': '0' * 64}
                db.execute('INSERT INTO metadata VALUES(1, ?)', (_json(state),))

    def _check_file(self):
        st = self.path.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077 or st.st_nlink != 1:
            raise ValueError('Snapshot file unsafe')

    @contextmanager
    def _db(self):
        self._check_file()
        lock = os.open(str(self.path) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock, 'rb') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            db = sqlite3.connect(self.path, timeout=5)
            try:
                db.execute('PRAGMA synchronous=FULL')
                with db:
                    yield db
            finally:
                db.close()

    def _bound(self, state):
        if state['scope'] != self.scope or state['expected_count'] != self.expected_count:
            raise ValueError('Snapshot scope mismatch')

    def add_page(self, scope, number, cursor, next_cursor, rows):
        if scope != self.scope or type(number) is not int or not 0 <= number <= 100000:
            raise ValueError('Snapshot scope/page mismatch')
        if any(x is not None and (not isinstance(x, str) or not 1 <= len(x) <= 256) for x in (cursor, next_cursor)):
            raise ValueError('Snapshot cursor invalid')
        if not isinstance(rows, list) or len(rows) > 250:
            raise ValueError('Snapshot page limit exceeded')
        encoded = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('Snapshot record invalid')
            _nested_complete(row)
            if self.scope['provider'] == 'shopify':
                ident, updated = row.get('id'), row.get('updatedAt')
                if row.get('test') is not True or not isinstance(ident, str) or not re.fullmatch(r'gid://shopify/Order/[0-9]+', ident):
                    raise ValueError('Snapshot Shopify test scope invalid')
                reference = ident
            else:
                ident = row.get('Id')
                metadata = row.get('MetaData')
                updated = metadata.get('LastUpdatedTime') if isinstance(metadata, dict) else None
                from invoice_audit import _invoice_shopify_order_ref
                reference = _invoice_shopify_order_ref(row) if self.scope['entity'] == 'Invoice' else None
            if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9:/_-]{1,256}', ident):
                raise ValueError('Snapshot record ID invalid')
            if not _time(self.scope['window_start']) <= _time(updated) < _time(self.scope['window_end']):
                raise ValueError('Snapshot record timestamp outside window')
            payload = _json(row)
            if len(payload.encode()) > 65536:
                raise ValueError('Snapshot record byte limit exceeded')
            encoded.append((ident, reference, payload, hashlib.sha256(payload.encode()).hexdigest()))
        digest = hashlib.sha256(_json([scope, number, cursor, next_cursor, rows]).encode()).hexdigest()
        with self._db() as db:
            state = json.loads(db.execute('SELECT value FROM metadata WHERE id=1').fetchone()[0])
            self._bound(state)
            old = db.execute('SELECT digest FROM pages WHERE number=?', (number,)).fetchone()
            if old:
                if old[0] != digest:
                    raise ValueError('Snapshot changed page replay')
                return {'replayed': True, 'records': state['records'], 'complete': state['complete']}
            if state['complete'] or number != state['pages'] or cursor != state['next_cursor']:
                raise ValueError('Snapshot checkpoint/cursor mismatch')
            if next_cursor is not None and (next_cursor == cursor or db.execute('SELECT 1 FROM pages WHERE cursor=?', (next_cursor,)).fetchone()):
                raise ValueError('Snapshot cursor loop')
            total = state['records'] + len(rows)
            total_bytes = state['bytes'] + sum(len(row[2].encode()) for row in encoded)
            if (total > self.expected_count or total_bytes > 256 * 1024**2
                    or (next_cursor is None and total != self.expected_count)
                    or (next_cursor is not None and (not rows or total >= self.expected_count))):
                raise ValueError('Snapshot count/byte completeness mismatch')
            try:
                db.executemany('INSERT INTO records(record_id,reference,payload,digest) VALUES(?,?,?,?)', encoded)
            except sqlite3.IntegrityError:
                raise ValueError('Snapshot duplicate record ID') from None
            db.execute('INSERT INTO pages VALUES(?,?,?)', (number, cursor, digest))
            state.update(records=total, pages=number + 1, next_cursor=next_cursor, bytes=total_bytes,
                         complete=next_cursor is None,
                         page_chain_sha256=hashlib.sha256((state['page_chain_sha256'] + digest).encode()).hexdigest())
            db.execute('UPDATE metadata SET value=? WHERE id=1', (_json(state),))
        return {'replayed': False, 'records': total, 'complete': next_cursor is None}

    def summary(self):
        with self._db() as db:
            state = json.loads(db.execute('SELECT value FROM metadata WHERE id=1').fetchone()[0])
            self._bound(state)
            duplicates = db.execute('SELECT COUNT(*) FROM (SELECT reference FROM records WHERE reference IS NOT NULL GROUP BY reference HAVING COUNT(*)>1)').fetchone()[0]
            return {**{k: v for k, v in state.items() if k != 'scope'},
                    'scope_sha256': hashlib.sha256(_json(self.scope).encode()).hexdigest(),
                    'duplicate_reference_groups': duplicates, 'source_snapshot_verified': False,
                    'financial_correctness_verified': False}

    def add_qbo_page(self, scope, number, start_position, body):
        """Normalize a bounded GET /query response; COUNT is pinned in the manifest."""
        if self.scope['provider'] != 'qbo_sandbox' or type(start_position) is not int or start_position < 1:
            raise ValueError('Snapshot QBO position invalid')
        response = body.get('QueryResponse') if isinstance(body, dict) and not body.get('Fault') else None
        if not isinstance(response, dict):
            raise ValueError('Snapshot QBO response incomplete')
        rows = response.get(self.scope['entity'], [])
        if (not isinstance(rows, list) or ('totalCount' in response and (
                type(response['totalCount']) is not int or response['totalCount'] != self.expected_count))
                or (rows and (type(response.get('startPosition')) is not int
                              or response['startPosition'] != start_position
                              or type(response.get('maxResults')) is not int
                              or response['maxResults'] != len(rows)))):
            raise ValueError('Snapshot QBO pagination/count mismatch')
        following = start_position + len(rows)
        return self.add_page(scope, number, None if start_position == 1 else str(start_position),
                             str(following) if following <= self.expected_count else None, rows)

    def add_shopify_page(self, scope, number, after, body):
        """Normalize query-only Shopify pages; verify source identity and cursors."""
        data = body.get('data') if isinstance(body, dict) and not body.get('errors') else None
        if self.scope['provider'] != 'shopify' or not isinstance(data, dict):
            raise ValueError('Snapshot Shopify response incomplete')
        shop, connection = data.get('shop'), data.get('orders')
        if (not isinstance(shop, dict) or shop.get('myshopifyDomain') != self.scope['source_id']
                or not isinstance(connection, dict) or not isinstance(connection.get('pageInfo'), dict)):
            raise ValueError('Snapshot Shopify source/pagination mismatch')
        info = connection['pageInfo']
        if type(info.get('hasNextPage')) is not bool or (info['hasNextPage'] and not info.get('endCursor')):
            raise ValueError('Snapshot Shopify cursor incomplete')
        return self.add_page(scope, number, after, info.get('endCursor') if info['hasNextPage'] else None,
                             connection.get('nodes'))

    def iter_records(self):
        with self._db() as db:
            state = json.loads(db.execute('SELECT value FROM metadata WHERE id=1').fetchone()[0])
            self._bound(state)
            if not state['complete']:
                raise ValueError('Snapshot incomplete; records not published')
            count = 0
            for payload, digest in db.execute('SELECT payload,digest FROM records ORDER BY seq'):
                if hashlib.sha256(payload.encode()).hexdigest() != digest:
                    raise ValueError('Snapshot payload integrity mismatch')
                count += 1
                yield json.loads(payload)
            if count != self.expected_count:
                raise ValueError('Snapshot count integrity mismatch')
