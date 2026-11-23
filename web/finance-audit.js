(() => {
  const button = document.getElementById('finance-audit-run');
  const output = document.getElementById('finance-audit-result');
  if (!button || !output) return;

  // All user-visible text lives here. Codes are always shown raw; descriptions never claim more than the check does.
  const TEXT = {
    failed: 'AUDIT NOT COMPLETED',
    sessionRequired: 'Session required',
    accessDenied: 'Access denied',
    onHold: (s) => 'The audit is temporarily on hold. Try again in ' + s + ' seconds.',
    unavailable: 'The audit is unavailable right now',
    noStore: 'Store connection not found',
    invalidResponse: 'The audit response is invalid',
    running: 'Read-only audit running…',
    notAvailable: 'not available',
    none: '—',
    yes: 'yes',
    no: 'no',
    label: {
      status: 'Status', store: 'Store', adapter: 'Adapter status', overall: 'Overall status',
      checked: 'Orders checked', verifiedCount: 'Orders verified', bank: 'Bank reconciliation',
      bankValue: 'not verified', access: 'Access', accessValue: 'Read-only',
      blocked: 'Blocked orders', orders: 'Orders', noOrders: 'none in the response',
      profile: 'Binding method', unbound: 'Defective documents (unbound)', conflicts: 'Conflicting orders',
      unmatchedCount: 'Documents no order claims', truncated: 'Unmatched list truncated'
    },
    title: {
      results: 'Order checks', receipts: 'Receipts matched by document number',
      marker: 'Receipts matched by marker', conflicts: 'Conflicts between the two matching methods',
      unmatched: 'Documents no order claims', refunds: 'Refund documents',
      unmatchedList: 'Unmatched documents', unboundList: 'Defective documents'
    },
    receiptNote: 'A receipt record found means a matching QuickBooks document record exists. ' +
      'It does not mean verified, cash received, or bank settlement.',
    listCaps: 'Lists are capped: at most 50 defective and 20 unmatched documents per method.',
    column: {
      order: 'Order', status: 'Status', order_invoice: 'Order ↔ invoice', test_payment: 'Test payment',
      refund_credit: 'Refund credit', credit_application: 'Credit application', verified: 'Verified',
      cash_received_verified: 'Cash received verified', bank_settlement_verified: 'Bank settlement verified',
      difference_amount: 'Difference amount', expected_balance: 'Expected balance',
      document_id: 'Document ID', document_kind: 'Document kind', document_record_found: 'Record found',
      refund: 'Refund', docnumber_status: 'By document number', marker_status: 'By marker',
      docnumber_document_id: 'Document ID (number)', marker_document_id: 'Document ID (marker)',
      reason: 'Reason'
    },
    prefix: {
      blocked: 'Cannot verify: required evidence is missing, ambiguous or unsupported.',
      review: 'Needs your review: a difference or open question was found.',
      notChecked: 'Out of scope for this check.',
      found: 'Record found. This is not verification, cash received or bank settlement.',
      verified: 'Passed this check. Cash received and bank settlement are not verified.',
      unknown: 'Unrecognized code, shown as returned.'
    },
    code: {
      // Overall status / adapter status
      READY: 'Orders and QuickBooks documents were read completely and the checks ran.',
      FINANCIAL_BATCH_VERIFIED: 'Every checked order passed the order, invoice, refund and credit checks. Cash received and bank settlement are not verified.',
      REVIEW_FINANCIAL_BATCH_INCOMPLETE: 'At least one order is not verified. See the order checks below.',
      BLOCKED_FINANCIAL_BATCH_INPUT: 'The input was incomplete or inconsistent, so nothing was verified.',
      BLOCKED_FINANCIAL_BATCH_LIMIT: 'There are more documents than the check supports, so nothing was verified.',
      BLOCKED_FINANCIAL_BATCH_DUPLICATE: 'A payment or credit has a missing or duplicate ID, so nothing was verified.',
      // Order check rows
      ORDER_REFUND_OFFSET_VERIFIED: 'The refund credit and its offsetting payment are consistent with this order\'s invoice. Cash received and bank settlement are not verified.',
      BLOCKED_ORDER_INVOICE_LINK: 'This order could not be verified against exactly one invoice.',
      NOT_CHECKED_REFUND_COUNT_UNSUPPORTED: 'The order\'s refund list is missing or its refund count is outside the supported range of 1 to 20.',
      BLOCKED_REFUND_CREDIT_LINK: 'The refunds could not be matched to credit memos.',
      BLOCKED_INVALID_CREDIT_SOURCE_REFERENCE: 'A credit memo has an invalid source reference.',
      BLOCKED_CREDIT_APPLICATION_LINK: 'The credit memos and payments linked to the invoice do not match the refunds.',
      BLOCKED_CROSS_ORDER_PAYMENT_LINK: 'A payment linked to the invoice is repeated, already used by another order, or not found among the payments read.',
      // Order to invoice
      PILOT_ORDER_INVOICE_VERIFIED: 'The order matches one invoice (reference, lines, tax and total) under the controlled pilot rules.',
      REFERENCE_AND_TOTAL_MATCH_LINE_ITEMS_NOT_VERIFIED: 'Reference and total match, but line items were not verified.',
      BLOCKED_NO_VERIFIED_ORDER_REFERENCE: 'No invoice carries a verified reference to this order.',
      BLOCKED_MULTIPLE_LINKED_INVOICES: 'More than one invoice is linked to this order.',
      REVIEW_LINKED_TOTAL_MISMATCH: 'The order total and the invoice total differ.',
      REVIEW_ORDER_INVOICE_LINE_MISMATCH: 'The order lines and the invoice lines differ.',
      REVIEW_ORDER_INVOICE_TAX_MISMATCH: 'The order tax and the invoice tax differ.',
      REVIEW_ORDER_INVOICE_COMPONENT_TOTAL: 'The order\'s subtotal plus shipping plus tax does not equal the invoice total.',
      // Receipts
      OK: 'Receipts were matched to orders. See each order below.',
      BLOCKED_BINDING_PROFILE: 'The matching method is not supported, so no receipt was matched.',
      DOCUMENT_RECORD_FOUND: 'A matching receipt record exists with the same currency and total. This is not verification, cash received or bank settlement.',
      REFUND_RECORD_FOUND: 'A matching refund document record exists with the same total. This is not verification, cash returned or bank settlement.',
      REVIEW_NO_DOCUMENT: 'No receipt record was found for this order.',
      REVIEW_CURRENCY_OR_TOTAL_UNKNOWN: 'A receipt was matched, but its currency differs from the order\'s, or the currency or total is missing.',
      REVIEW_AMOUNT_MISMATCH: 'A receipt was matched, but its total differs from the order total.',
      REVIEW_NO_REFUND_DOCUMENT: 'No refund document was found for this refund.',
      REVIEW_REFUND_AMOUNT_MISMATCH: 'A refund document was matched, but its total differs from the refund total.',
      BLOCKED_NO_ORDER_NUMBER: 'The order has no number to match against.',
      BLOCKED_DUPLICATE_DOCUMENT_NUMBER: 'More than one receipt has this order\'s number.',
      BLOCKED_DUPLICATE_DOCUMENT_REFERENCE: 'More than one receipt carries this order\'s marker.',
      BLOCKED_UNBOUND_DOCUMENTS: 'No receipt was matched, and some documents are defective, so a match may be hidden.',
      BLOCKED_DUPLICATE_REFUND_DOCUMENT: 'More than one document carries this refund\'s marker.',
      BLOCKED_REFUND_MARKER_REQUIRED: 'Refund documents without a refund marker are never matched by number.',
      // Conflicts
      NO_CONFLICT: 'The two matching methods do not contradict each other. This includes orders with no document under either method.',
      REVIEW_PROFILE_CONFLICT: 'The two matching methods point to different documents for this order.',
      REVIEW_PROFILE_AMBIGUOUS: 'One method matched a document and the other found duplicates.',
      REVIEW_CONFLICT_UNKNOWN: 'The two methods could not be compared.',
      // Unmatched
      NO_ORDER_MATCH: 'The document matches none of the orders read.',
      NO_MARKER: 'The document has no order marker.',
      BLOCKED_INVALID_DOCUMENT: 'The document is malformed and was not matched.',
      BLOCKED_INVALID_DOCUMENT_REFERENCE: 'The document\'s order reference is invalid.',
      BLOCKED_NO_DOCUMENT_NUMBER: 'The document has no document number.'
    }
  };

  const ROW_FIELDS = ['order', 'status', 'order_invoice', 'test_payment', 'refund_credit',
    'credit_application', 'verified', 'cash_received_verified', 'difference_amount', 'expected_balance'];
  const CODE_FIELDS = new Set(['status', 'order_invoice', 'test_payment', 'refund_credit', 'credit_application',
    'docnumber_status', 'marker_status', 'reason']);

  const describe = (code) => {
    if (typeof code !== 'string' || !code) return null;
    if (Object.prototype.hasOwnProperty.call(TEXT.code, code)) return TEXT.code[code];
    if (code.startsWith('BLOCKED_')) return TEXT.prefix.blocked;
    if (code.startsWith('REVIEW_')) return TEXT.prefix.review;
    if (code.startsWith('NOT_CHECKED_')) return TEXT.prefix.notChecked;
    if (code.endsWith('_FOUND')) return TEXT.prefix.found;
    if (code.endsWith('_VERIFIED') && !code.endsWith('NOT_VERIFIED')) return TEXT.prefix.verified;
    return TEXT.prefix.unknown;
  };
  const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
  const text = (value) => {
    if (value === undefined || value === null) return TEXT.none;
    if (value === true) return TEXT.yes;
    if (value === false) return TEXT.no;
    return String(value);
  };
  const el = (tag, content, className) => {
    const node = document.createElement(tag);
    if (content !== undefined) node.textContent = content;
    if (className) node.className = className;
    return node;
  };
  const line = (label, value) => el('p', label + ': ' + value);
  const codeLine = (label, code) => {
    const p = el('p', label + ': ' + text(code));
    const note = describe(code);
    if (note) p.appendChild(el('small', note, 'audit-note'));
    return p;
  };
  const heading = (title) => el('h4', title);

  const failure = (response) => {
    if (response.status === 401) return TEXT.sessionRequired;
    if (response.status === 403) return TEXT.accessDenied;
    const delay = response.headers.get('Retry-After');
    if ((response.status === 429 || response.status === 503) && /^\d+$/.test(delay || '')) {
      return TEXT.onHold(delay);
    }
    return TEXT.unavailable;
  };
  const message = (value) => output.replaceChildren(line(TEXT.failed, value));
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

  const table = (fields, rows) => {
    const t = document.createElement('table');
    const head = t.createTHead().insertRow();
    fields.forEach(field => head.appendChild(el('th', TEXT.column[field] || field)));
    const body = t.createTBody();
    rows.forEach(row => {
      const tr = body.insertRow();
      fields.forEach(field => {
        const cell = tr.insertCell();
        const value = isObject(row) ? row[field] : undefined;
        cell.appendChild(el('span', text(value)));
        const note = CODE_FIELDS.has(field) ? describe(value) : null;
        if (note) cell.appendChild(el('small', note, 'audit-note'));
      });
    });
    const scroll = el('div', undefined, 'audit-scroll');
    scroll.tabIndex = 0;
    scroll.appendChild(t);
    return scroll;
  };
  const objectRows = (list) => (Array.isArray(list) ? list.filter(isObject) : []);

  // Each section renders defensively: a missing or malformed block shows "not available" and never throws.
  const section = (title, build) => {
    const nodes = [heading(title)];
    try {
      const built = build();
      if (built) nodes.push(...built); else nodes.push(line(TEXT.label.status, TEXT.notAvailable));
    } catch (e) {
      nodes.length = 1;
      nodes.push(line(TEXT.label.status, TEXT.notAvailable));
    }
    return nodes;
  };

  const receiptSection = (title, block) => section(title, () => {
    if (!isObject(block) || !Array.isArray(block.results)) return null;
    const nodes = [
      line(TEXT.label.profile, text(block.profile)),
      codeLine(TEXT.label.status, block.status),
      line(TEXT.label.unbound, text(block.unbound_count))
    ];
    const rows = objectRows(block.results);
    if (rows.length) {
      nodes.push(table(['order', 'status', 'document_id', 'document_kind', 'document_record_found',
        'cash_received_verified', 'bank_settlement_verified'], rows));
      const refunds = [];
      rows.forEach(r => objectRows(r.refunds).forEach(f => refunds.push({...f, order: r.order})));
      if (refunds.length) {
        nodes.push(heading(TEXT.title.refunds));
        nodes.push(table(['order', 'refund', 'status', 'document_id'], refunds));
      }
    }
    return nodes;
  });

  const conflictSection = (block) => section(TEXT.title.conflicts, () => {
    if (!isObject(block) || !Array.isArray(block.results)) return null;
    const nodes = [line(TEXT.label.conflicts, text(block.conflict_count))];
    const rows = objectRows(block.results);
    if (rows.length) {
      nodes.push(table(['order', 'status', 'docnumber_status', 'marker_status',
        'docnumber_document_id', 'marker_document_id'], rows));
    }
    return nodes;
  });

  const unmatchedSection = (block) => section(TEXT.title.unmatched, () => {
    if (!isObject(block)) return null;
    const nodes = [];
    [['docnumber', TEXT.title.receipts], ['marker', TEXT.title.marker]].forEach(([key, name]) => {
      const part = block[key];
      nodes.push(el('h5', name));
      if (!isObject(part)) { nodes.push(line(TEXT.label.status, TEXT.notAvailable)); return; }
      nodes.push(line(TEXT.label.unmatchedCount, text(part.unmatched_count)));
      nodes.push(line(TEXT.label.truncated, text(part.unmatched_truncated)));
      const unmatched = objectRows(part.unmatched);
      if (unmatched.length) {
        nodes.push(el('p', TEXT.title.unmatchedList));
        nodes.push(table(['document_id', 'document_kind', 'reason'], unmatched));
      }
      const unbound = objectRows(part.unbound);
      if (unbound.length) {
        nodes.push(el('p', TEXT.title.unboundList + ' (' + unbound.length + ')'));
        nodes.push(table(['document_id', 'document_kind', 'reason'], unbound));
      }
    });
    nodes.push(el('p', TEXT.listCaps));
    return nodes;
  });

  const render = (data) => {
    const nodes = [
      line(TEXT.label.store, data.store),
      codeLine(TEXT.label.adapter, data.adapter_status),
      codeLine(TEXT.label.overall, data.status),
      line(TEXT.label.checked, data.orders_checked),
      line(TEXT.label.verifiedCount, data.orders_verified),
      line(TEXT.label.bank, TEXT.label.bankValue),
      line(TEXT.label.access, TEXT.label.accessValue)
    ];
    if (data.results.length) {
      nodes.push(heading(TEXT.title.results));
      nodes.push(table(ROW_FIELDS, data.results));
    }
    if (data.blocked.length) {
      nodes.push(line(TEXT.label.blocked, data.blocked.length));
      const list = document.createElement('ul');
      data.blocked.forEach(item => {
        const li = el('li', text(item.order) + ' · ' + text(item.status));
        const note = describe(item.status);
        if (note) li.appendChild(el('small', note, 'audit-note'));
        list.appendChild(li);
      });
      nodes.push(list);
    }
    if (!data.results.length && !data.blocked.length) nodes.push(line(TEXT.label.orders, TEXT.label.noOrders));
    nodes.push(el('p', TEXT.receiptNote, 'audit-warning'));
    nodes.push(...receiptSection(TEXT.title.receipts, data.receipts));
    nodes.push(...receiptSection(TEXT.title.marker, data.receipts_marker));
    nodes.push(...conflictSection(data.receipts_conflicts));
    nodes.push(...unmatchedSection(data.receipts_unmatched));
    output.replaceChildren(...nodes);
  };

  button.addEventListener('click', async () => {
    button.disabled = true;
    output.hidden = false;
    output.replaceChildren(line(TEXT.label.status, TEXT.running));
    try {
      const token = sessionToken();
      if (!token) return message(TEXT.sessionRequired);
      const headers = {Authorization: 'Bearer ' + token};
      const identity = await fetch('/tenant/finance/access-check', {method: 'GET', headers, cache: 'no-store'});
      if (!identity.ok) return message(failure(identity));
      const own = await identity.json();
      const store = own?.shop_domain;
      if (!/^[a-z0-9-]+\.myshopify\.com$/.test(store || '')) return message(TEXT.noStore);
      const response = await fetch('/tenant/finance/audit?store=' + encodeURIComponent(store),
        {method: 'GET', headers, cache: 'no-store'});
      if (!response.ok) return message(failure(response));
      const data = await response.json();
      if (!valid(data, store)) return message(TEXT.invalidResponse);
      render(data);
    } catch (e) { message(TEXT.unavailable); }
    finally { button.disabled = false; }
  });
})();
