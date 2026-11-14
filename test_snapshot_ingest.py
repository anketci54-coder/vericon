"""Local snapshot acceptance; synthetic records, no provider/user session."""
import copy
import json

import pytest

from snapshot_ingest import SnapshotStore


@pytest.fixture
def scope():
    return {'tenant_id': '11111111-1111-4111-8111-111111111111',
            'provider': 'qbo_sandbox', 'source_id': '12345', 'entity': 'Invoice',
            'window_start': '2026-01-01T00:00:00+00:00',
            'window_end': '2026-02-01T00:00:00+00:00',
            'snapshot_id': 'fixture-1', 'evidence_kind': 'synthetic_fixture'}


def row(ident, ref=None):
    return {'Id': str(ident), 'MetaData': {'LastUpdatedTime': '2026-01-02T00:00:00+00:00'},
            'CustomField': [{'Name': 'Shopify Order ID', 'StringValue': str(ref or ident)}],
            'CurrencyRef': {'value': 'USD'}, 'TotalAmt': '10.00'}


def test_snapshot_resume_replay_and_cross_page_duplicate_reference(tmp_path, scope):
    path = tmp_path / 'snapshot.sqlite'
    tmp_path.chmod(0o700)
    store = SnapshotStore(path, scope, expected_count=3)
    store.add_page(scope, 0, None, 'next', [row(1), row(2)])
    with pytest.raises(ValueError, match='incomplete'):
        list(store.iter_records())
    resumed = SnapshotStore(path, scope, expected_count=3)
    assert resumed.add_page(scope, 0, None, 'next', [row(1), row(2)])['replayed'] is True
    resumed.add_page(scope, 1, 'next', None, [row(3, ref=1)])
    summary = resumed.summary()
    assert summary['complete'] and summary['records'] == 3
    assert summary['duplicate_reference_groups'] == 1 and summary['source_snapshot_verified'] is False
    assert [r['Id'] for r in resumed.iter_records()] == ['1', '2', '3']
    assert path.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize('fault', ['tenant', 'source', 'window', 'count', 'cursor', 'page_gap',
                                  'duplicate_id', 'changed_replay', 'nested', 'timestamp', 'oversize'])
def test_snapshot_rejects_corruption_without_advancing_checkpoint(tmp_path, scope, fault):
    tmp_path.chmod(0o700)
    path = tmp_path / 'snapshot.sqlite'
    store = SnapshotStore(path, scope, expected_count=2)
    store.add_page(scope, 0, None, 'next', [row(1)])
    before = store.summary()
    changed = copy.deepcopy(scope)
    rows = [row(2)]; number = 1; cursor = 'next'; next_cursor = None
    if fault == 'tenant': changed['tenant_id'] = '22222222-2222-4222-8222-222222222222'
    if fault == 'source': changed['source_id'] = '67890'
    if fault == 'window': changed['window_end'] = '2026-03-01T00:00:00+00:00'
    if fault == 'count': rows = []
    if fault == 'cursor': cursor = 'other'
    if fault == 'page_gap': number = 2
    if fault == 'duplicate_id': rows = [row(1)]
    if fault == 'changed_replay': number = 0; cursor = None; next_cursor = 'next'; rows = [row(9)]
    if fault == 'nested': rows[0]['lines'] = {'nodes': [], 'pageInfo': {'hasNextPage': True}}
    if fault == 'timestamp': rows[0]['MetaData']['LastUpdatedTime'] = '2026-02-01T00:00:00+00:00'
    if fault == 'oversize': rows[0]['Note'] = 'x' * 65536
    with pytest.raises(ValueError):
        store.add_page(changed, number, cursor, next_cursor, rows)
    assert store.summary() == before
    with pytest.raises(ValueError):
        SnapshotStore(path, {**scope, 'source_id': '67890'}, expected_count=2)


def test_snapshot_empty_bounds_and_symlink(tmp_path, scope):
    tmp_path.chmod(0o700)
    with pytest.raises(ValueError):
        SnapshotStore(tmp_path / 'large.sqlite', scope, expected_count=100001)
    with pytest.raises(ValueError):
        SnapshotStore(tmp_path / 'customer.sqlite', {**scope, 'evidence_kind': 'customer'}, expected_count=1)
    store = SnapshotStore(tmp_path / 'empty.sqlite', scope, expected_count=0)
    store.add_page(scope, 0, None, None, [])
    assert store.summary()['complete'] and list(store.iter_records()) == []
    link = tmp_path / 'link.sqlite'; link.symlink_to(tmp_path / 'empty.sqlite')
    with pytest.raises(ValueError):
        SnapshotStore(link, scope, expected_count=0)


def test_snapshot_source_specific_shopify_nested_completeness(tmp_path, scope):
    tmp_path.chmod(0o700)
    scope.update(provider='shopify', source_id='fixture.myshopify.com', entity='Order')
    with pytest.raises(ValueError, match='disjoint windows'):
        SnapshotStore(tmp_path / 'too_many.sqlite', scope, expected_count=25001)
    store = SnapshotStore(tmp_path / 'shopify.sqlite', scope, expected_count=1)
    order = {'id': 'gid://shopify/Order/1', 'test': True, 'updatedAt': '2026-01-02T00:00:00Z',
             'lineItems': {'nodes': []}}
    with pytest.raises(ValueError, match='nested'):
        store.add_page(scope, 0, None, None, [order])
    order['lineItems']['pageInfo'] = {'hasNextPage': False}
    store.add_page(scope, 0, None, None, [order])
    assert store.summary()['complete']


def test_snapshot_read_detects_stored_payload_corruption(tmp_path, scope):
    import sqlite3
    tmp_path.chmod(0o700)
    path = tmp_path / 'snapshot.sqlite'
    store = SnapshotStore(path, scope, expected_count=1)
    store.add_page(scope, 0, None, None, [row(1)])
    with sqlite3.connect(path) as db:
        db.execute('UPDATE records SET payload=?', (json.dumps(row(9)),))
    with pytest.raises(ValueError, match='integrity'):
        list(store.iter_records())


def test_provider_page_envelopes_fail_closed(tmp_path, scope):
    tmp_path.chmod(0o700)
    store = SnapshotStore(tmp_path / 'qbo.sqlite', scope, expected_count=1)
    for bad in ({'Fault': {}}, {'QueryResponse': {'totalCount': 2}},
                {'QueryResponse': {'Invoice': [row(1)], 'startPosition': 2, 'maxResults': 1}}):
        with pytest.raises(ValueError):
            store.add_qbo_page(scope, 0, 1, bad)
    store.add_qbo_page(scope, 0, 1, {'QueryResponse': {'Invoice': [row(1)], 'startPosition': 1, 'maxResults': 1}})
    assert store.summary()['complete']
    scope.update(provider='shopify', source_id='fixture.myshopify.com', entity='Order')
    shop = SnapshotStore(tmp_path / 'shop.sqlite', scope, expected_count=0)
    body = {'data': {'shop': {'myshopifyDomain': 'other.myshopify.com'},
                     'orders': {'nodes': [], 'pageInfo': {'hasNextPage': False}}}}
    with pytest.raises(ValueError):
        shop.add_shopify_page(scope, 0, None, body)
    body['data']['shop']['myshopifyDomain'] = scope['source_id']
    shop.add_shopify_page(scope, 0, None, body)
    assert shop.summary()['complete']


def test_snapshot_process_exit_resume_and_partial_page_rollback(tmp_path, scope):
    import subprocess
    import sys
    tmp_path.chmod(0o700)
    path = tmp_path / 'snapshot.sqlite'
    script = '''
import json, os, sys
from snapshot_ingest import SnapshotStore
scope=json.loads(sys.argv[2]); row=json.loads(sys.argv[3])
store=SnapshotStore(sys.argv[1], scope, expected_count=3)
store.add_page(scope, 0, None, 'next', [row])
os._exit(23)
'''
    process = subprocess.run([sys.executable, '-B', '-c', script, str(path), json.dumps(scope), json.dumps(row(1))],
                             capture_output=True, timeout=10)
    assert process.returncode == 23
    resumed = SnapshotStore(path, scope, expected_count=3)
    before = resumed.summary()
    # First INSERT succeeds; the second violates uniqueness. Entire page rolls back.
    with pytest.raises(ValueError, match='duplicate'):
        resumed.add_page(scope, 1, 'next', None, [row(2), row(1)])
    assert resumed.summary() == before
    resumed.add_page(scope, 1, 'next', None, [row(2), row(3)])
    assert [r['Id'] for r in resumed.iter_records()] == ['1', '2', '3']
