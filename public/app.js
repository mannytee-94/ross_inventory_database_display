const notice = document.querySelector('#notice');
const forms = [...document.querySelectorAll('form')];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function clearEdit(form) {
  delete form.dataset.editId;
  const titles = {inventory: 'Inventory details', user: 'Create user'};
  const buttons = {user: 'Create user'};
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
  fillSelect('#inventory [name="storeId"]', data.stores, 'Select a store');
  fillSelect('#inventory [name="inventoryLeadId"]', data.employees, 'Select lead (optional)');
  fillSelect('#store [name="clientId"]', data.clients, 'No client assigned');
}

async function loadRecords() {
  const container = document.querySelector('#record-tables');
  container.innerHTML = '<p>Loading saved data…</p>';
  try {
    const response = await fetch('/api/records');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load records.');
    const labels = {clients: 'Clients', stores: 'Stores', employees: 'Employees', inventories: 'Inventories', users: 'User accounts'};
    const editable = {clients: 'client', stores: 'store', employees: 'employee', inventories: 'inventory', users: 'user'};
    container.innerHTML = Object.entries(data).map(([key, records]) => {
      const headers = records[0] ? Object.keys(records[0]) : [];
      const actionHeader = editable[key] ? '<th>Actions</th>' : '';
      const table = records.length ? `<table><thead><tr>${headers.map(header => `<th>${escapeHtml(header)}</th>`).join('')}${actionHeader}</tr></thead><tbody>${records.map(record => `<tr>${headers.map(header => `<td>${escapeHtml(record[header])}</td>`).join('')}${editable[key] ? `<td><button class="edit-record" type="button" data-type="${editable[key]}" data-id="${escapeHtml(record.ID)}">Edit</button></td>` : ''}</tr>`).join('')}</tbody></table>` : '<p class="empty">No records saved yet.</p>';
      return `<details open><summary>${labels[key]} <span>${records.length}</span></summary><div class="table-wrap">${table}</div></details>`;
    }).join('');
  } catch (error) { container.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`; }
}

async function editRecord(type, id) {
  try {
    const response = await fetch(`/api/edit/${type}/${id}`);
    const values = await response.json();
    if (!response.ok) throw new Error(values.error || 'Could not load this record.');
    await refreshOptions();
    const form = document.querySelector(`#${type}`);
    form.reset();
    Object.entries(values).forEach(([name, value]) => {
      const field = form.elements.namedItem(name);
      if (field) field.value = value === 'NULL' ? '' : value;
    });
    form.dataset.editId = id;
    form.querySelector('h2').textContent = `Edit ${type} #${id}`;
    form.querySelector('[type="submit"]').textContent = 'Save changes';
    if (type === 'user') form.querySelectorAll('[name="password"], [name="confirmPassword"]').forEach(field => field.required = false);
    document.querySelectorAll('nav button, form, section.form-card').forEach(el => el.classList.remove('active'));
    document.querySelector(`nav button[data-form="${type}"]`).classList.add('active');
    form.classList.add('active');
    notice.textContent = `Editing ${type} #${id}.`;
    notice.className = '';
  } catch (error) { notice.textContent = error.message; notice.className = 'error'; }
}

document.querySelectorAll('nav button').forEach(button => button.addEventListener('click', async () => {
  document.querySelectorAll('nav button, form, section.form-card').forEach(el => el.classList.remove('active'));
  button.classList.add('active');
  document.querySelector(`#${button.dataset.form}`).classList.add('active');
  const target = document.querySelector(`#${button.dataset.form}`);
  if (target?.tagName === 'FORM') clearEdit(target);
  notice.textContent = '';
  if (button.dataset.form === 'records') await loadRecords();
}));

document.querySelector('#refresh-records').addEventListener('click', loadRecords);

document.querySelector('#record-tables').addEventListener('click', event => {
  const button = event.target.closest('.edit-record');
  if (button) editRecord(button.dataset.type, button.dataset.id);
});

forms.forEach(form => form.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = true;
  notice.textContent = 'Saving…';
  try {
    const payload = Object.fromEntries(new FormData(form));
    if (form.id === 'user' && payload.password !== payload.confirmPassword) throw new Error('Passwords do not match.');
    const editId = form.dataset.editId;
    const response = await fetch(`/api/${form.id}${editId ? `/${editId}` : ''}`, {method: editId ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not save this record.');
    notice.textContent = data.message;
    notice.className = 'success';
    form.reset();
    clearEdit(form);
    if (form.id === 'inventory') form.querySelector('[name="inventoryDate"]').value = new Date().toISOString().slice(0, 10);
    await refreshOptions();
  } catch (error) { notice.textContent = error.message; notice.className = 'error'; }
  finally { submit.disabled = false; }
}));

document.querySelector('#inventory [name="inventoryDate"]').value = new Date().toISOString().slice(0, 10);
refreshOptions().catch(error => { notice.textContent = `Database connection failed: ${error.message}`; notice.className = 'error'; });
