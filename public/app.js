const notice = document.querySelector('#notice');
const forms = [...document.querySelectorAll('form')];
let calendarEvents = [];
let calendarMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let savedRecords = {};
let activeRecordCategory = 'inventories';

document.querySelector('#logout').addEventListener('click', async () => {
  await fetch('/api/logout', {method: 'POST'});
  window.location.assign('/login');
});

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function clearEdit(form) {
  delete form.dataset.editId;
  const titles = {schedule: 'Schedule inventory', complete: 'Complete inventory', 'inventory-edit': 'Edit inventory', client: 'Group', user: 'Create user'};
  const buttons = {schedule: 'Schedule inventory', complete: 'Complete inventory', 'inventory-edit': 'Save inventory changes', client: 'Save group', user: 'Create user'};
  form.querySelector('h2').textContent = titles[form.id] || form.id[0].toUpperCase() + form.id.slice(1);
  form.querySelector('[type="submit"]').textContent = buttons[form.id] || `Save ${form.id}`;
  if (form.id === 'user') form.querySelectorAll('[name="password"], [name="confirmPassword"]').forEach(field => field.required = true);
}

function fillSelect(selector, items, placeholder) {
  const select = document.querySelector(selector);
  select.innerHTML = `<option value="">${placeholder}</option>` + items.map(item => `<option value="${item.id}">${item.name}</option>`).join('');
}

async function refreshOptions() {
  const response = await fetch('/api/options');
  const data = await response.json();
  if (!response.ok) throw new Error(data.error);
  fillSelect('#schedule [name="storeId"]', data.stores, 'Select a store');
  fillSelect('#complete [name="inventoryLeadId"]', data.employees, 'Select lead (optional)');
  fillSelect('#inventory-edit [name="storeId"]', data.stores, 'Select a store');
  fillSelect('#inventory-edit [name="inventoryLeadId"]', data.employees, 'Select lead (optional)');
  fillSelect('#store [name="clientId"]', data.clients, 'No group assigned');
  fillSelect('#chart-store', data.stores, 'Select a store');
  const scheduledResponse = await fetch('/api/scheduled-inventories');
  const scheduled = await scheduledResponse.json();
  if (!scheduledResponse.ok) throw new Error(scheduled.error);
  fillSelect('#complete [name="scheduledInventoryId"]', scheduled, 'Select a scheduled inventory');
}

function renderRecordCategory() {
  const container = document.querySelector('#record-tables');
  const labels = {clients: 'Groups', stores: 'Stores', employees: 'Employees', inventories: 'Inventories', users: 'User accounts'};
  const editable = {clients: 'client', stores: 'store', employees: 'employee', inventories: 'inventory', users: 'user'};
  const records = savedRecords[activeRecordCategory] || [];
  const headers = records[0] ? Object.keys(records[0]) : [];
  const actionHeader = editable[activeRecordCategory] ? '<th>Actions</th>' : '';
  const table = records.length ? `<table><thead><tr>${headers.map(header => `<th>${escapeHtml(header)}</th>`).join('')}${actionHeader}</tr></thead><tbody>${records.map(record => `<tr>${headers.map(header => `<td>${escapeHtml(record[header])}</td>`).join('')}${editable[activeRecordCategory] ? `<td><button class="edit-record" type="button" data-type="${editable[activeRecordCategory]}" data-id="${escapeHtml(record.ID)}">Edit</button></td>` : ''}</tr>`).join('')}</tbody></table>` : '<p class="empty">No records saved yet.</p>';
  container.innerHTML = `<h3 class="record-category-title">${labels[activeRecordCategory]} <span>${records.length}</span></h3><div class="table-wrap">${table}</div>`;
}

async function loadRecords() {
  const container = document.querySelector('#record-tables');
  container.innerHTML = '<p>Loading saved data…</p>';
  try {
    const response = await fetch('/api/records');
    savedRecords = await response.json();
    if (!response.ok) throw new Error(savedRecords.error || 'Could not load records.');
    renderRecordCategory();
  } catch (error) { container.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`; }
}

function renderCalendar() {
  const grid = document.querySelector('#calendar-grid');
  const title = document.querySelector('#calendar-title');
  const year = calendarMonth.getFullYear();
  const month = calendarMonth.getMonth();
  title.textContent = calendarMonth.toLocaleDateString(undefined, {month: 'long', year: 'numeric'});
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const eventsByDate = calendarEvents.reduce((dates, event) => {
    (dates[event.date] ||= []).push(event);
    return dates;
  }, {});
  const cells = [];
  for (let index = 0; index < firstWeekday + daysInMonth; index += 1) {
    const day = index - firstWeekday + 1;
    if (day < 1) { cells.push('<div class="calendar-day empty-day"></div>'); continue; }
    const isoDate = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const events = eventsByDate[isoDate] || [];
    const blocks = events.map(event => {
      const scheduled = event.status === 'Scheduled';
      const duration = Math.max(1, Math.min(12, Number(event.estimatedDuration) || 1));
      const time = scheduled && event.estimatedStartTime ? event.estimatedStartTime.slice(0, 5) : '';
      const label = scheduled ? `${time ? `${time} · ` : ''}${event.store}${event.estimatedDuration ? ` (${event.estimatedDuration}h)` : ''}` : event.store;
      const size = scheduled ? ` style="min-height:${Math.max(26, 20 + duration * 5)}px"` : '';
      return `<button class="calendar-event ${scheduled ? 'scheduled-event' : 'completed-event'}" type="button" data-id="${escapeHtml(event.id)}" title="${escapeHtml(event.status)}: ${escapeHtml(label)}"${size}>${escapeHtml(label)}</button>`;
    }).join('');
    cells.push(`<div class="calendar-day"><span class="calendar-date">${day}</span>${blocks}</div>`);
  }
  grid.innerHTML = cells.join('');
}

async function loadCalendar() {
  const grid = document.querySelector('#calendar-grid');
  grid.innerHTML = '<p class="calendar-loading">Loading inventories…</p>';
  try {
    const response = await fetch('/api/calendar');
    calendarEvents = await response.json();
    if (!response.ok) throw new Error(calendarEvents.error || 'Could not load inventories.');
    renderCalendar();
  } catch (error) { grid.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`; }
}

function formatChartValue(value, metric) {
  return metric === 'totalValue' || metric === 'inventoryCost' ? `$${Number(value).toLocaleString(undefined, {maximumFractionDigits: 0})}` : Number(value).toLocaleString();
}

function drawStoreChart(result, style) {
  const canvas = document.querySelector('#store-chart');
  const legend = document.querySelector('#chart-legend');
  const empty = document.querySelector('#chart-empty');
  const data = result.data || [];
  empty.textContent = data.length ? '' : 'No inventory results are available for this store.';
  empty.hidden = Boolean(data.length);
  legend.innerHTML = '';
  const ctx = canvas.getContext('2d');
  const width = canvas.clientWidth || 900;
  const height = 420;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  if (!data.length) return;

  const years = [...new Set(data.map(point => point.year))];
  const colors = ['#0b5f72', '#d17027', '#5b8a3c', '#9057a1', '#ba4d65', '#4165a8'];
  const series = new Map(years.map(year => [year, new Map()]));
  data.forEach(point => series.get(point.year).set(Number(point.month), Number(point.value)));
  const max = Math.max(...data.map(point => Number(point.value)), 1);
  const left = 72, right = 20, top = 24, bottom = 52;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const x = month => left + ((month - 1) / 11) * plotWidth;
  const y = value => top + plotHeight - (value / max) * plotHeight;

  ctx.font = '12px ui-sans-serif, system-ui, sans-serif';
  ctx.fillStyle = '#536671';
  ctx.strokeStyle = '#dce5e8';
  ctx.lineWidth = 1;
  for (let tick = 0; tick <= 4; tick += 1) {
    const value = (max * tick) / 4;
    const lineY = y(value);
    ctx.beginPath(); ctx.moveTo(left, lineY); ctx.lineTo(width - right, lineY); ctx.stroke();
    ctx.textAlign = 'right'; ctx.fillText(formatChartValue(value, result.metric), left - 10, lineY + 4);
  }
  ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].forEach((month, index) => {
    ctx.textAlign = 'center'; ctx.fillStyle = '#536671'; ctx.fillText(month, x(index + 1), height - 20);
  });
  years.forEach((year, seriesIndex) => {
    const color = colors[seriesIndex % colors.length];
    const points = series.get(year);
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2;
    if (style === 'bar') {
      const barWidth = Math.max(3, plotWidth / 12 / years.length - 3);
      points.forEach((value, month) => {
        const offset = (seriesIndex - (years.length - 1) / 2) * (barWidth + 3);
        ctx.fillRect(x(month) + offset - barWidth / 2, y(value), barWidth, top + plotHeight - y(value));
      });
    } else {
      let started = false;
      [...points.entries()].sort((a, b) => a[0] - b[0]).forEach(([month, value]) => {
        if (!started) { ctx.beginPath(); ctx.moveTo(x(month), y(value)); started = true; }
        else ctx.lineTo(x(month), y(value));
      });
      ctx.stroke();
      points.forEach((value, month) => { ctx.beginPath(); ctx.arc(x(month), y(value), 3, 0, Math.PI * 2); ctx.fill(); });
    }
    legend.insertAdjacentHTML('beforeend', `<span><i style="background:${color}"></i>${escapeHtml(year)}</span>`);
  });
}

async function loadStoreChart() {
  const store = document.querySelector('#chart-store').value;
  const metric = document.querySelector('#chart-metric').value;
  if (!store) {
    drawStoreChart({data: [], metric}, 'line');
    return;
  }
  const empty = document.querySelector('#chart-empty');
  empty.hidden = false; empty.textContent = 'Loading store trend…';
  try {
    const response = await fetch(`/api/store-chart?${new URLSearchParams({storeId: store, metric})}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not load the chart.');
    drawStoreChart(result, document.querySelector('#chart-style').value);
  } catch (error) { empty.hidden = false; empty.textContent = error.message; }
}

async function editRecord(type, id) {
  try {
    const response = await fetch(`/api/edit/${type}/${id}`);
    const values = await response.json();
    if (!response.ok) throw new Error(values.error || 'Could not load this record.');
    await refreshOptions();
    const formType = type === 'inventory' ? 'inventory-edit' : type;
    const form = document.querySelector(`#${formType}`);
    form.reset();
    Object.entries(values).forEach(([name, value]) => {
      const field = form.elements.namedItem(name);
      if (field) field.value = value === 'NULL' ? '' : value;
    });
    form.dataset.editId = id;
    const displayType = type === 'client' ? 'group' : type === 'inventory' ? 'inventory' : type;
    form.querySelector('h2').textContent = `Edit ${displayType} #${id}`;
    form.querySelector('[type="submit"]').textContent = 'Save changes';
    if (type === 'user') form.querySelectorAll('[name="password"], [name="confirmPassword"]').forEach(field => field.required = false);
    document.querySelectorAll('main > nav button, form, section.form-card').forEach(el => el.classList.remove('active'));
    const navButton = document.querySelector(`nav button[data-form="${formType}"]`);
    if (navButton) navButton.classList.add('active');
    form.classList.add('active');
    notice.textContent = `Editing ${displayType} #${id}.`;
    notice.className = '';
  } catch (error) { notice.textContent = error.message; notice.className = 'error'; }
}

document.querySelectorAll('main > nav button').forEach(button => button.addEventListener('click', async () => {
  document.querySelectorAll('main > nav button, form, section.form-card').forEach(el => el.classList.remove('active'));
  button.classList.add('active');
  document.querySelector(`#${button.dataset.form}`).classList.add('active');
  const target = document.querySelector(`#${button.dataset.form}`);
  if (target?.tagName === 'FORM') {
    clearEdit(target);
    if (target.id === 'schedule' || target.id === 'complete') target.reset();
    if (target.id === 'schedule') target.querySelector('[name="inventoryDate"]').value = new Date().toISOString().slice(0, 10);
  }
  notice.textContent = '';
  if (button.dataset.form === 'records') await loadRecords();
  if (button.dataset.form === 'calendar') await loadCalendar();
  if (button.dataset.form === 'chart') await loadStoreChart();
}));

document.querySelector('#refresh-records').addEventListener('click', loadRecords);

document.querySelector('#records-tabs').addEventListener('click', event => {
  const tab = event.target.closest('button[data-category]');
  if (!tab) return;
  activeRecordCategory = tab.dataset.category;
  document.querySelectorAll('#records-tabs button').forEach(button => button.classList.toggle('active', button === tab));
  renderRecordCategory();
});

document.querySelector('#record-tables').addEventListener('click', event => {
  const button = event.target.closest('.edit-record');
  if (button) editRecord(button.dataset.type, button.dataset.id);
});

document.querySelector('#complete [name="scheduledInventoryId"]').addEventListener('change', async event => {
  const id = event.target.value;
  const form = document.querySelector('#complete');
  if (!id) { delete form.dataset.editId; return; }
  try {
    const response = await fetch(`/api/edit/inventory/${id}`);
    const values = await response.json();
    if (!response.ok) throw new Error(values.error || 'Could not load this scheduled inventory.');
    const selectedId = id;
    form.reset();
    form.elements.namedItem('scheduledInventoryId').value = selectedId;
    Object.entries(values).forEach(([name, value]) => {
      const field = form.elements.namedItem(name);
      if (field) field.value = value === 'NULL' ? '' : value;
    });
    form.dataset.editId = selectedId;
    notice.textContent = 'Scheduled inventory loaded.';
    notice.className = '';
  } catch (error) { notice.textContent = error.message; notice.className = 'error'; }
});

document.querySelector('#previous-month').addEventListener('click', () => {
  calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1);
  renderCalendar();
});
document.querySelector('#next-month').addEventListener('click', () => {
  calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1);
  renderCalendar();
});
document.querySelector('#calendar-grid').addEventListener('click', event => {
  const button = event.target.closest('.calendar-event');
  if (!button) return;
  const inventory = calendarEvents.find(item => item.id === button.dataset.id);
  if (!inventory) return;
  const schedule = inventory.status === 'Scheduled' ? `${inventory.estimatedStartTime ? ` · Starts ${inventory.estimatedStartTime.slice(0, 5)}` : ''}${inventory.estimatedDuration ? ` · Estimated ${inventory.estimatedDuration} hours` : ''}` : '';
  document.querySelector('#calendar-detail').textContent = `${inventory.date} · ${inventory.store} · ${inventory.status}${schedule} · ${inventory.pieceCount || 0} pieces · $${inventory.totalValue || '0.00'} · Discount: ${inventory.discount || 0}${inventory.lead ? ` · Lead: ${inventory.lead}` : ''}`;
});

document.querySelector('#update-chart').addEventListener('click', loadStoreChart);

forms.forEach(form => form.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = true;
  notice.textContent = 'Saving…';
  try {
    const payload = Object.fromEntries(new FormData(form));
    if (form.id === 'user' && payload.password !== payload.confirmPassword) throw new Error('Passwords do not match.');
    const editId = form.dataset.editId;
    if (form.id === 'complete' && !editId) throw new Error('Select a scheduled inventory first.');
    const endpoint = form.id === 'schedule' ? '/api/schedule-inventory' : form.id === 'complete' ? `/api/complete-inventory/${editId}` : form.id === 'inventory-edit' ? `/api/inventory/${editId}` : `/api/${form.id}${editId ? `/${editId}` : ''}`;
    const method = form.id === 'schedule' ? 'POST' : form.id === 'complete' || form.id === 'inventory-edit' ? 'PUT' : editId ? 'PUT' : 'POST';
    const response = await fetch(endpoint, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not save this record.');
    notice.textContent = data.message;
    notice.className = 'success';
    form.reset();
    clearEdit(form);
    if (form.id === 'schedule') form.querySelector('[name="inventoryDate"]').value = new Date().toISOString().slice(0, 10);
    await refreshOptions();
  } catch (error) { notice.textContent = error.message; notice.className = 'error'; }
  finally { submit.disabled = false; }
}));

document.querySelector('#schedule [name="inventoryDate"]').value = new Date().toISOString().slice(0, 10);
refreshOptions().catch(error => { notice.textContent = `Database connection failed: ${error.message}`; notice.className = 'error'; });
