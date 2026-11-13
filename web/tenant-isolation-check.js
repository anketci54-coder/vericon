(() => {
  const button = document.getElementById('tenant-isolation-check');
  const output = document.getElementById('tenant-isolation-result');
  if (!button || !output) return;
  const disconnect = document.getElementById('qbo-disconnect');
  const disconnectResult = document.getElementById('qbo-disconnect-result');
  if (disconnect && disconnectResult) {
    disconnect.hidden = false;
    disconnect.addEventListener('click', async () => {
      if (!confirm('QuickBooks yetkisi iptal edilecek. Yeniden bağlanmak için QuickBooks hesabını tekrar yetkilendirmeniz gerekir. Devam?')) return;
      disconnect.disabled = true;
      disconnectResult.hidden = false;
      try {
        const keys = Object.keys(localStorage).filter(k => /^sb-[a-z0-9]+-auth-token$/.test(k));
        if (keys.length !== 1) throw Error('Aktif oturum bulunamadı');
        const session = JSON.parse(localStorage.getItem(keys[0]));
        if (!session?.access_token) throw Error('Aktif oturum bulunamadı');
        const r = await fetch('/tenant/quickbooks/disconnect', {method:'POST', headers:{Authorization:'Bearer ' + session.access_token}, cache:'no-store'});
        if (!r.ok) throw Error('Yetki iptali doğrulanamadı: HTTP ' + r.status);
        disconnectResult.textContent = 'QuickBooks yetkisi iptal edildi. Yeniden bağlanmak için QuickBooks Sandbox hesabını yetkilendir düğmesini kullanın.';
      } catch(e) { disconnectResult.textContent = e.message; }
      finally { disconnect.disabled = false; }
    });
  }
  button.addEventListener('click', async () => {
    button.disabled = true;
    output.hidden = false;
    output.textContent = 'Gerçek oturum ve finansal erişim kontrol ediliyor…';
    try {
      const keys = Object.keys(localStorage).filter(k => /^sb-[a-z0-9]+-auth-token$/.test(k));
      if (keys.length !== 1) throw Error('Aktif oturum bulunamadı');
      const session = JSON.parse(localStorage.getItem(keys[0]));
      if (!session?.access_token) throw Error('Aktif oturum bulunamadı');
      const headers = {Authorization: 'Bearer ' + session.access_token};
      const identity = await fetch('/tenant/finance/access-check', {headers, cache:'no-store'});
      if (!identity.ok) throw Error('Oturum yetkisi reddedildi: HTTP ' + identity.status);
      const own = await identity.json();
      const known = ['9341458613758425', '9341458641399133'];
      if (!known.includes(own.qbo_realm_id)) throw Error('Tanımsız pilot şirket');
      const other = known.find(x => x !== own.qbo_realm_id);
      const ownResponse = await fetch('/tenant/finance/invoice-count?realm=' + encodeURIComponent(own.qbo_realm_id), {headers,cache:'no-store'});
      const ownData = ownResponse.ok ? await ownResponse.json() : null;
      const otherResponse = await fetch('/tenant/finance/invoice-count?realm=' + encodeURIComponent(other), {headers,cache:'no-store'});
      const pass = ownResponse.status === 200 && ownData?.realm === own.qbo_realm_id && Number.isInteger(ownData?.invoice_count) && otherResponse.status === 403;
      output.textContent = (pass ? 'PASS' : 'FAIL') + ' | Kendi şirketi HTTP ' + ownResponse.status + (ownData ? ', fatura ' + ownData.invoice_count : '') + ' | Diğer şirket HTTP ' + otherResponse.status + ' | ' + own.qbo_realm_id;
    } catch(e) { output.textContent = 'TEST TAMAMLANAMADI: ' + e.message; }
    finally { button.disabled = false; }
  });
})();

(() => {
  const button = document.getElementById('pdf42-check');
  const output = document.getElementById('pdf42-result');
  if (!button || !output) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    output.hidden = false;
    output.textContent = 'Salt-okunur kontroller çalışıyor…';
    try {
      const keys = Object.keys(localStorage).filter(k => /^sb-[a-z0-9]+-auth-token$/.test(k));
      if (keys.length !== 1) throw Error('Tek aktif Supabase oturumu bulunamadı');
      const session = JSON.parse(localStorage.getItem(keys[0]));
      if (!session?.access_token) throw Error('Aktif oturum bulunamadı');
      const headers = {Authorization: 'Bearer ' + session.access_token};
      const [own, anonymous] = await Promise.all([
        fetch('/tenant/finance/access-check', {headers, cache:'no-store'}),
        fetch('/tenant/finance/access-check', {cache:'no-store'})
      ]);
      const data = own.ok ? await own.json() : null;
      const pass = own.status === 200 && data?.authenticated_tenant === true &&
        data?.financial_access_enabled === false &&
        /^[a-z0-9-]+\.myshopify\.com$/.test(data?.shop_domain || '') &&
        /^\d+$/.test(data?.qbo_realm_id || '') && anonymous.status === 401;
      output.textContent = (pass ? 'PASS' : 'FAIL') + ' | access-check: ' + own.status +
        ' | anonim: ' + anonymous.status +
        ' | mağaza: ' + (data?.shop_domain || '-') +
        ' | realm: ' + (data?.qbo_realm_id || '-') +
        ' | Not: Diğer tenant endpointlerinin çapraz izolasyonu bu testle doğrulanmaz.';
    } catch (e) { output.textContent = 'TEST TAMAMLANAMADI: ' + e.message; }
    finally { button.disabled = false; }
  });
})();
