"""Isolated synthetic arithmetic benchmark; never calls a provider API.

Run: python3 -B benchmark_invoice_audit.py
Financial chain: python3 -B benchmark_invoice_audit.py --financial
Snapshot ingest: python3 -B benchmark_invoice_audit.py --snapshot
Outputs JSON to stdout. Limits each worker to 1 GiB and 45 CPU seconds.
Live read adapters cap at 5 Shopify orders/100 QBO entities. Snapshot mode
stages fixture provider pages on disk; it never calls an external provider.
21 sequential batches per size; p95/p99 are empirical, not a capacity guarantee.
Cost uses VERICON_BENCHMARK_VCPU_HOUR_USD (default illustrative $0.05/vCPU-hour).
It excludes all providers, storage, network, auth, idle time and operations.
"""
import sys,os,pathlib,json,time,resource,statistics,subprocess,math,hashlib
ROOT=pathlib.Path(__file__).resolve().parent


def financial_workload(n):
    """Stream synthetic 20-order windows through existing financial functions.

    This is an offline workload, not a new ingestion or pagination implementation.
    Every tenth invoice has a one-cent balance error; the next payment has a
    different customer. All other zero-cash credit offsets must verify, while
    every report must still require settlement review.
    """
    import socket
    def forbid_network(*args, **kwargs):
        raise AssertionError('Financial benchmark must not access the network')
    socket.socket.connect = forbid_network
    socket.create_connection = forbid_network
    import invoice_audit as a
    a.requests.sessions.Session.request = forbid_network
    assert 1 <= n <= 100000
    hourly = float(os.environ.get('VERICON_BENCHMARK_VCPU_HOUR_USD', '0.05'))
    assert math.isfinite(hourly) and hourly >= 0
    money = lambda amount: {'shopMoney': {'amount': str(amount), 'currencyCode': 'USD'}}
    fingerprint = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':')).encode()).digest()
    samples = []
    input_hash = hashlib.sha256()
    checked = offsets = balance_errors = customer_errors = 0
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    for start in range(0, n, 20):
        orders, invoices, credits, payments = [], [], [], []
        ids = list(range(start + 1, min(start + 20, n) + 1))
        for ident in ids:
            gid = f'gid://shopify/Order/{ident}'
            customer = {'value': f'C{ident}'}
            currency = {'value': 'USD'}
            sale = {'DetailType': 'SalesItemLineDetail', 'Amount': 100,
                'SalesItemLineDetail': {'Qty': 1, 'UnitPrice': 100,
                    'ItemRef': {'name': 'VERICON-TEST-001'}, 'TaxCodeRef': {'value': 'NON'}}}
            orders.append({'id': gid, 'name': f'#{ident}', 'test': True,
                'displayFinancialStatus': 'PARTIALLY_REFUNDED',
                'subtotalPriceSet': money(100), 'totalTaxSet': money(0), 'totalPriceSet': money(100),
                'lineItems': {'nodes': [{'sku': 'VERICON-TEST-001', 'quantity': 1,
                    'originalUnitPriceSet': money(100), 'discountedTotalSet': money(100)}]},
                'shippingLines': {'nodes': [{'title': 'Standart', 'discountedPriceSet': money(0)}]},
                'transactions': [{'kind': 'SALE', 'status': 'SUCCESS', 'test': True, 'amountSet': money(100)}],
                'refunds': [{'id': f'gid://shopify/Refund/{ident}', 'order': {'id': gid},
                    'totalRefundedSet': money(40), 'transactions': {'pageInfo': {'hasNextPage': False},
                    'nodes': [{'id': f'gid://shopify/OrderTransaction/{ident}', 'kind': 'REFUND',
                        'status': 'SUCCESS', 'test': True, 'amountSet': money(40)}]}}]})
            invoices.append({'Id': f'I{ident}', 'DocNumber': str(ident), 'TotalAmt': 100,
                'Balance': '60.01' if ident % 10 == 0 else '60.00',
                'CurrencyRef': currency, 'CustomerRef': customer, 'TxnTaxDetail': {'TotalTax': 0},
                'CustomField': [{'Name': 'Shopify Order ID', 'StringValue': str(ident)}],
                'LinkedTxn': [{'TxnId': f'P{ident}', 'TxnType': 'Payment'}],
                'Line': [sale, {'DetailType': 'SubTotalLineDetail', 'Amount': 100}]})
            credits.append({'Id': f'CM{ident}', 'TotalAmt': 40, 'Balance': 0,
                'CurrencyRef': currency, 'CustomerRef': customer, 'TxnTaxDetail': {'TotalTax': 0},
                'CustomField': [{'Name': 'Shopify Refund ID', 'StringValue': str(ident)}],
                'Line': [{'DetailType': 'SalesItemLineDetail', 'Amount': 40,
                    'SalesItemLineDetail': {'TaxCodeRef': {'value': 'NON'}}}]})
            payments.append({'Id': f'P{ident}', 'TotalAmt': 0, 'UnappliedAmt': 0,
                'CurrencyRef': currency,
                'CustomerRef': {'value': 'OTHER_SYNTHETIC_CUSTOMER'} if ident % 10 == 1 else customer,
                'Line': [{'Amount': 40, 'LinkedTxn': [{'TxnId': f'I{ident}', 'TxnType': 'Invoice'}]},
                         {'Amount': 40, 'LinkedTxn': [{'TxnId': f'CM{ident}', 'TxnType': 'CreditMemo'}]}]})
        inputs = (orders, invoices, credits, payments)
        before = fingerprint(inputs)
        begin = time.perf_counter()
        arithmetic = a.audit_all(invoices, payments, credits)
        duplicates = a.audit_duplicate_invoice_references(invoices)
        batch = a.audit_order_financial_batch(*inputs)
        report = a.financial_discrepancy_report(batch, orders, invoices)
        samples.append(time.perf_counter() - begin)
        assert fingerprint(inputs) == before
        input_hash.update(before)
        assert arithmetic['verified_invoice_count'] == len(ids)
        assert arithmetic['financial_loss_claimed'] is False
        assert duplicates['candidate_groups'] == 0 and duplicates['reference_scan_complete']
        assert report['orders_checked'] == len(ids) == report['orders_to_review']
        assert report['verified'] is False and report['bank_settlement_verified'] is False
        assert [row['shopify_order_id'] for row in report['rows']] == [o['id'] for o in orders]
        for ident, row in zip(ids, report['rows']):
            assert row['qbo_invoice_id'] == f'I{ident}'
            assert row['payment_verified'] is False and row['review_required'] is True
            assert row['bank_settlement_verified'] is False
            if ident % 10 == 0:
                assert row['reason'] == 'REVIEW_MULTI_INVOICE_BALANCE'
                assert row['difference_amount'] == '-0.01' and row['offset_verified'] is False
                balance_errors += 1
            elif ident % 10 == 1:
                assert row['reason'] == 'BLOCKED_MULTI_OFFSET_ACCOUNTING'
                assert row['difference_amount'] is None and row['offset_verified'] is False
                customer_errors += 1
            else:
                assert row['offset_verified'] is True and row['difference_amount'] == '0'
                offsets += 1
            checked += 1
    cpu = time.process_time() - cpu_start
    wall = time.perf_counter() - wall_start
    assert checked == n and offsets + balance_errors + customer_errors == n
    percentile = lambda p: sorted(samples)[math.ceil(len(samples) * p) - 1]
    return {'scope': 'offline financial chain in independent 20-order windows; no ingest/auth/provider/persistence',
        'n': n, 'documents': 4 * n, 'windows': len(samples), 'window_size_max': 20,
        'wall_seconds_including_generation_hash_oracle': wall, 'cpu_seconds': cpu,
        'one_core_cpu_percent': 100 * cpu / wall,
        'audit_seconds': sum(samples), 'window_p50_seconds': percentile(.5),
        'window_p95_seconds': percentile(.95), 'window_p99_seconds': percentile(.99),
        'percentile_scope': 'empirical 20-order audit windows, not full-run or API latency',
        'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        'checked_orders': checked, 'verified_zero_cash_offsets': offsets,
        'expected_one_cent_balance_errors': balance_errors, 'expected_wrong_customer_errors': customer_errors,
        'settlement_review_count': n, 'synthetic_false_positives': 0, 'synthetic_false_negatives': 0,
        'input_unchanged_sha256': input_hash.hexdigest(), 'oracle': 'PASS', 'external_api_calls': 0,
        'cost_assumption_vcpu_hour_usd': hourly, 'illustrative_cpu_only_usd': cpu * hourly / 3600,
        'cost_scope': 'assumption only; not billed SaaS cost; excludes API/auth/storage/network/idle/operations',
        'limitations': 'single process; synthetic fixed pilot SKU; no cross-window duplicate detection or atomic snapshot'}


def snapshot_workload(n):
    """Provider-shaped JSON -> durable checkpoints -> integrity -> invoice audit.

    Two complete fixture snapshots, cross-page duplicate references, interruption
    and page replay. No source consistency/customer accuracy/capacity claim.
    """
    import socket
    import tempfile
    import invoice_audit as a
    from snapshot_ingest import SnapshotStore
    def forbidden(*args, **kwargs):
        raise AssertionError('Snapshot benchmark must not access a network')
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    a.requests.sessions.Session.request = forbidden
    assert 1 <= n <= 100000
    hourly = float(os.environ.get('VERICON_BENCHMARK_VCPU_HOUR_USD', '0.05'))
    assert math.isfinite(hourly) and hourly >= 0
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    money = lambda cents: f'{cents // 100}.{cents % 100:02d}'
    scope = {'tenant_id': '11111111-1111-4111-8111-111111111111',
        'provider': 'qbo_sandbox', 'source_id': '12345', 'entity': 'Invoice',
        'window_start': '2026-01-01T00:00:00+00:00', 'window_end': '2026-02-01T00:00:00+00:00',
        'snapshot_id': f'fixture-{n}', 'evidence_kind': 'synthetic_fixture'}
    shop_scope = {**scope, 'provider': 'shopify', 'source_id': 'fixture.myshopify.com', 'entity': 'Order'}
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    input_hash = [hashlib.sha256(), hashlib.sha256()]
    page_times = []
    with tempfile.TemporaryDirectory(prefix='vericon-snapshot-bench-') as temp:
        root = pathlib.Path(temp)
        invoice_store = SnapshotStore(root / 'invoices.sqlite', scope, expected_count=n)
        order_stores = []
        replay_count = 0
        for page, start in enumerate(range(0, n, 250)):
            invoices, orders = [], []
            end = min(start + 250, n)
            partition = start // 25000
            partition_start = partition * 25000
            partition_end = min(partition_start + 25000, n)
            shop_page = (start - partition_start) // 250
            if start == partition_start:
                shop_scope = {**shop_scope, 'snapshot_id': f'fixture-{n}-part-{partition}',
                    'window_start': f'2026-01-{1 + partition * 7:02d}T00:00:00+00:00',
                    'window_end': f'2026-01-{8 + partition * 7:02d}T00:00:00+00:00'}
                order_store = SnapshotStore(root / f'orders-{partition}.sqlite', shop_scope,
                                            expected_count=partition_end - partition_start)
                order_stores.append(order_store)
            updated = f'2026-01-{2 + partition * 7:02d}T00:00:00Z'
            for ident in range(start + 1, end + 1):
                cents = 500 + ident % 97
                ref = ident - 999 if ident % 1000 == 0 else ident
                invoices.append({'Id': str(ident), 'MetaData': {'LastUpdatedTime': updated},
                    'CurrencyRef': {'value': 'USD'}, 'TotalAmt': money(2 * cents),
                    'TxnTaxDetail': {'TotalTax': 0},
                    'CustomField': [{'Name': 'Shopify Order ID', 'StringValue': str(ref)}],
                    'Line': [{'DetailType': 'SalesItemLineDetail',
                              'Amount': money(2 * cents + (ident % 10 == 0)),
                              'SalesItemLineDetail': {'Qty': 2, 'UnitPrice': money(cents),
                                                     'ItemRef': {'name': f'SYNTHETIC-{ident % 50}'}}},
                             {'DetailType': 'SubTotalLineDetail', 'Amount': money(2 * cents)}]})
                orders.append({'id': f'gid://shopify/Order/{ident}', 'name': f'#{ident}', 'test': True,
                    'updatedAt': updated,
                    'totalPriceSet': {'shopMoney': {'amount': money(2 * cents), 'currencyCode': 'USD'}},
                    'lineItems': {'nodes': [{'sku': f'SYNTHETIC-{ident % 50}', 'quantity': 2}],
                                  'pageInfo': {'hasNextPage': False}}, 'refunds': []})
            qbo = {'QueryResponse': {'Invoice': invoices, 'startPosition': start + 1, 'maxResults': len(invoices)}}
            shop = {'data': {'shop': {'myshopifyDomain': shop_scope['source_id']},
                'orders': {'nodes': orders, 'pageInfo': {'hasNextPage': end < partition_end, 'endCursor': f'cursor-{end}'}}}}
            before = hashlib.sha256(canonical([qbo, shop])).digest()
            for digest, rows in zip(input_hash, (invoices, orders)):
                for record in rows:
                    digest.update(canonical(record))
            begin = time.perf_counter()
            # JSON serialization/parsing represents actual provider payload boundaries.
            invoice_store.add_qbo_page(scope, page, start + 1, json.loads(canonical(qbo)))
            order_store.add_shopify_page(shop_scope, shop_page, None if shop_page == 0 else f'cursor-{start}', json.loads(canonical(shop)))
            page_times.append(time.perf_counter() - begin)
            if page == 1:
                # Release all handles, reopen the durable checkpoint, replay once.
                invoice_store = SnapshotStore(root / 'invoices.sqlite', scope, expected_count=n)
                order_store = SnapshotStore(root / f'orders-{partition}.sqlite', shop_scope,
                                            expected_count=partition_end - partition_start)
                order_stores[-1] = order_store
                assert invoice_store.add_qbo_page(scope, page, start + 1, qbo)['replayed']
                assert order_store.add_shopify_page(shop_scope, shop_page, f'cursor-{start}', shop)['replayed']
                replay_count += 2
            assert hashlib.sha256(canonical([qbo, shop])).digest() == before
        ingest_seconds = time.perf_counter() - wall_start
        qsummary = invoice_store.summary()
        ssummaries = [store.summary() for store in order_stores]
        assert qsummary['complete'] and all(s['complete'] for s in ssummaries)
        assert qsummary['duplicate_reference_groups'] == n // 1000
        assert all(s['duplicate_reference_groups'] == 0 for s in ssummaries)
        reviewed = checked = 0
        output_hash = [hashlib.sha256(), hashlib.sha256()]
        for ident, inv in enumerate(invoice_store.iter_records(), 1):
            assert inv['Id'] == str(ident)
            output_hash[0].update(canonical(inv))
            result = a.audit_invoice(inv)
            expected = 'REVIEW_LINE_AMOUNT' if ident % 10 == 0 else 'LINE_AMOUNTS_MATCH'
            assert result['status'] == expected
            reviewed += result['status'] == 'REVIEW_LINE_AMOUNT'
            checked += 1
        ident = 0
        for store in order_stores:
            for order in store.iter_records():
                ident += 1
                assert order['id'] == f'gid://shopify/Order/{ident}'
                output_hash[1].update(canonical(order))
        assert checked == n and reviewed == n // 10
        assert [x.hexdigest() for x in input_hash] == [x.hexdigest() for x in output_hash]
        storage_bytes = sum(p.stat().st_size for p in root.iterdir() if p.is_file())
        payload_bytes = qsummary['bytes'] + sum(s['bytes'] for s in ssummaries)
    cpu, wall = time.process_time() - cpu_start, time.perf_counter() - wall_start
    percentile = lambda p: sorted(page_times)[math.ceil(len(page_times) * p) - 1]
    return {'scope': 'offline fixture provider pages, durable snapshot ingest and invoice arithmetic',
        'orders': n, 'invoices': n, 'records': 2 * n, 'page_size_max': 250,
        'provider_shaped_pages': 2 * len(page_times), 'idempotent_replays': replay_count,
        'shopify_disjoint_windows': len(order_stores),
        'wall_seconds': wall, 'cpu_seconds': cpu, 'ingest_seconds': ingest_seconds,
        'page_pair_p50_seconds': percentile(.5), 'page_pair_p95_seconds': percentile(.95),
        'page_pair_p99_seconds': percentile(.99),
        'percentile_scope': 'empirical pairs of <=250-record pages; one full run per size',
        'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        'storage_bytes': storage_bytes, 'payload_bytes': payload_bytes,
        'reviewed_invoices': reviewed, 'cross_page_duplicate_reference_groups': n // 1000,
        'input_equals_stored_sha256': [x.hexdigest() for x in input_hash],
        'synthetic_false_positives': 0, 'synthetic_false_negatives': 0,
        'oracle': 'PASS', 'external_api_calls': 0, 'source_snapshot_verified': False,
        'cost_assumption_vcpu_hour_usd': hourly, 'illustrative_cpu_only_usd': cpu * hourly / 3600,
        'cost_scope': 'assumption, not bill; storage measured in bytes, provider/idle/auth/ops excluded',
        'limitations': 'fixture-only acceptance; mutable provider snapshot, merchant ingest and real SaaS capacity unverified'}


if sys.argv[1:] == ['--snapshot']:
    results = []
    for n in (1000, 10000, 100000):
        child = subprocess.run([sys.executable, '-B', __file__, '--snapshot-worker', str(n)],
            capture_output=True, text=True, timeout=90)
        if child.returncode:
            raise RuntimeError(f'Snapshot benchmark failed at {n}; exit={child.returncode}')
        results.append(json.loads(child.stdout))
    print(json.dumps(results, indent=2))
elif len(sys.argv) == 3 and sys.argv[1] == '--snapshot-worker':
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    print(json.dumps(snapshot_workload(int(sys.argv[2]))))
elif sys.argv[1:] == ['--financial']:
    results = []
    for n in (1000, 10000, 100000):
        child = subprocess.run([sys.executable, '-B', __file__, '--financial-worker', str(n)],
            capture_output=True, text=True, timeout=60)
        if child.returncode:
            raise RuntimeError(f'Financial benchmark failed at {n}; exit={child.returncode}')
        results.append(json.loads(child.stdout))
    print(json.dumps(results, indent=2))
elif len(sys.argv) == 3 and sys.argv[1] == '--financial-worker':
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
    print(json.dumps(financial_workload(int(sys.argv[2]))))
elif len(sys.argv)>1:
    resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(45,45))
    sys.path.insert(0,str(ROOT))
    import invoice_audit as a
    n=int(sys.argv[1])
    assert 1 <= n <= 100000
    repeats=21
    hourly=float(os.environ.get('VERICON_BENCHMARK_VCPU_HOUR_USD', '0.05'))
    assert math.isfinite(hourly) and hourly>=0
    def forbid_network(*args, **kwargs):
        raise AssertionError('Synthetic benchmark must not call providers')
    a.requests.sessions.Session.request=forbid_network
    # Independent integer cents oracle: 2 * 500 == 1000; every tenth line records 1001.
    rows=[{'Id':str(i+1),'CurrencyRef':{'value':'USD'},'TotalAmt':'10.00',
        'TxnTaxDetail':{'TotalTax':0},'Line':[
            {'DetailType':'SalesItemLineDetail','Amount':'10.01' if i%10==0 else '10.00',
             'SalesItemLineDetail':{'Qty':2,'UnitPrice':5}},
            {'DetailType':'SubTotalLineDetail','Amount':'10.00'}]} for i in range(n)]
    fingerprint=lambda: hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    before=fingerprint()
    expected={str(i+1) for i in range(n) if i%10==0}
    samples=[];cpu_start=time.process_time();wall_start=time.perf_counter()
    for trial in range(repeats):
        start=time.perf_counter();result=a.audit_all(rows)
        samples.append(time.perf_counter()-start)
        assert result['review_invoice_count']==(n+9)//10
        assert result['verified_invoice_count']==n-(n+9)//10
        assert result['blocked_invoice_count']==0 and result['financial_loss_claimed'] is False
        assert set(result['review_invoice_ids'])==expected
    cpu=time.process_time()-cpu_start;wall=time.perf_counter()-wall_start
    assert fingerprint()==before
    percentile=lambda p:sorted(samples)[math.ceil(len(samples)*p)-1]
    batch=a.audit_order_invoice_batch([{'id':f'gid://shopify/Order/{i+1}'} for i in range(n)],rows)
    print(json.dumps({'n':n,'line_records':2*n,'samples_seconds':samples,'median_seconds':statistics.median(samples),
        'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'cpu_seconds':cpu,'wall_seconds':wall,'one_core_cpu_percent':100*cpu/wall if wall>=.1 else None,
        'repeats':repeats,'p50_seconds':percentile(.5),'p95_seconds':percentile(.95),'p99_seconds':percentile(.99),
        'percentile_scope':'21 sequential full arithmetic batches; p99 is the observed maximum',
        'cpu_seconds_per_batch':cpu/repeats,'error_rate':0,'synthetic_false_positives':0,'synthetic_false_negatives':0,
        'input_sha256_unchanged':before,'compute_only_cost_per_invoice_usd':hourly*cpu/(3600*repeats*n),
        'cost_assumption_vcpu_hour_usd':hourly,
        'cost_scope':'illustrative CPU-only model, not billed cost; excludes API/auth/network/storage/idle/operations',
        'oracle':'PASS','expected_review':(n+9)//10,'batch_status':batch['status'],
        'external_api_calls':0,'scope':'local invoice arithmetic only; read adapters cap at 5 Shopify orders/100 QBO entities; engine window cap is 20 orders'}))
else:
    results=[]
    for n in (10,100,1000,10000,100000):
        p=subprocess.run([sys.executable,'-B',__file__,str(n)],capture_output=True,text=True,timeout=60)
        if p.returncode:results.append({'n':n,'failure':p.returncode});continue
        results.append(json.loads(p.stdout))
    print(json.dumps(results,indent=2))
    if any('failure' in result for result in results):
        raise SystemExit(1)
