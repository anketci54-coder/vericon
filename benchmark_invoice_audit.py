"""Isolated synthetic arithmetic benchmark; never calls a provider API.

Run: python3 -B benchmark_invoice_audit.py
Outputs JSON to stdout. Limits each worker to 1 GiB and 45 CPU seconds.
The full Shopify-QBO pipeline remains limited to 20 orders/100 invoices.
21 sequential batches per size; p95/p99 are empirical, not a capacity guarantee.
Cost uses VERICON_BENCHMARK_VCPU_HOUR_USD (default illustrative $0.05/vCPU-hour).
It excludes all providers, storage, network, auth, idle time and operations.
"""
import sys,os,pathlib,json,time,resource,statistics,subprocess,math,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
if len(sys.argv)>1:
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
        'external_api_calls':0,'scope':'local invoice arithmetic only; full Shopify-QBO pipeline has 20-order/100-invoice limits'}))
else:
    results=[]
    for n in (10,100,1000,10000,100000):
        p=subprocess.run([sys.executable,'-B',__file__,str(n)],capture_output=True,text=True,timeout=60)
        if p.returncode:results.append({'n':n,'failure':p.returncode});continue
        results.append(json.loads(p.stdout))
    print(json.dumps(results,indent=2))
    if any('failure' in result for result in results):
        raise SystemExit(1)
