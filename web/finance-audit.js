(() => {
  const button = document.getElementById('finance-audit-run');
  const output = document.getElementById('finance-audit-result');
  if (!button || !output) return;
  const ROW_FIELDS = ['order', 'status', 'order_invoice', 'test_payment', 'refund_credit',
    'credit_application', 'verified', 'cash_received_verified', 'difference_amount', 'expected_balance'];
  const failure = (response) => {
    if (response.status === 401) return 'Oturum gerekli';
    if (response.status === 403) return 'Erişim yok';
    const delay = response.headers.get('Retry-After');
    if ((response.status === 429 || response.status === 503) && /^\d+$/.test(delay || '')) {
      return 'Denetim geçici olarak beklemede. ' + delay + ' saniye sonra yeniden deneyin.';
    }
    return 'Denetim şu an yapılamadı';
  };
  const text = (value) => (value === undefined || value === null) ? '—' : String(value);
  const line = (label, value) => {
    const p = document.createElement('p');
    p.textContent = label + ': ' + value;
    return p;
  };
  const message = (value) => output.replaceChildren(line('DENETİM TAMAMLANAMADI', value));
  const sessionToken = () => {
    const keys = Object.keys(localStorage).filter(k => /^sb-[a-z0-9]+-auth-token$/.test(k));
    if (keys.length !== 1) return null;
    try { return JSON.parse(localStorage.getItem(keys[0]))?.access_token || null; } catch (e) { return null; }
  };
  const valid = (data, store) => data && typeof data === 'object' && data.store === store &&
    data.read_only === true && Array.isArray(data.results) && Array.isArray(data.blocked) &&
    typeof data.status === 'string' && typeof data.adapter_status === 'string' &&
    Number.isInteger(data.orders_checked) && Number.isInteger(data.orders_verified) &&
    data.results.every(row => row && typeof row === 'object') &&
    data.blocked.every(row => row && typeof row === 'object');
  const render = (data) => {
    const nodes = [
      line('Mağaza', data.store),
      line('Adaptör durumu', data.adapter_status),
      line('Genel durum', data.status),
      line('Kontrol edilen sipariş', data.orders_checked),
      line('Doğrulanan sipariş', data.orders_verified),
      line('Banka mutabakatı', 'doğrulanmadı'),
      line('Erişim', 'Salt-okunur')
    ];
    if (data.results.length) {
      const table = document.createElement('table');
      const head = table.createTHead().insertRow();
      ROW_FIELDS.forEach(field => {
        const th = document.createElement('th');
        th.textContent = field;
        head.appendChild(th);
      });
      const body = table.createTBody();
      data.results.forEach(row => {
        const tr = body.insertRow();
        ROW_FIELDS.forEach(field => {
          tr.insertCell().textContent = text(row[field]);
        });
      });
      nodes.push(table);
    }
    if (data.blocked.length) {
      nodes.push(line('Engellenen sipariş sayısı', data.blocked.length));
      const list = document.createElement('ul');
      data.blocked.forEach(item => {
        const li = document.createElement('li');
        li.textContent = text(item.order) + ' · ' + text(item.status);
        list.appendChild(li);
      });
      nodes.push(list);
    }
    if (!data.results.length && !data.blocked.length) nodes.push(line('Sipariş', 'yanıtta sipariş yok'));
    output.replaceChildren(...nodes);
  };
  button.addEventListener('click', async () => {
    button.disabled = true;
    output.hidden = false;
    output.replaceChildren(line('Durum', 'Salt-okunur denetim çalışıyor…'));
    try {
      const token = sessionToken();
      if (!token) return message('Oturum gerekli');
      const headers = {Authorization: 'Bearer ' + token};
      const identity = await fetch('/tenant/finance/access-check', {method: 'GET', headers, cache: 'no-store'});
      if (!identity.ok) return message(failure(identity));
      const own = await identity.json();
      const store = own?.shop_domain;
      if (!/^[a-z0-9-]+\.myshopify\.com$/.test(store || '')) return message('Mağaza bağlantısı bulunamadı');
      const response = await fetch('/tenant/finance/audit?store=' + encodeURIComponent(store),
        {method: 'GET', headers, cache: 'no-store'});
      if (!response.ok) return message(failure(response));
      const data = await response.json();
      if (!valid(data, store)) return message('Denetim yanıtı geçersiz');
      render(data);
    } catch (e) { message('Denetim şu an yapılamadı'); }
    finally { button.disabled = false; }
  });
})();
