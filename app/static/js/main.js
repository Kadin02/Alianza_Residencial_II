/* ═══════════════════════════════════════════════════════
   ALIANZA RESIDENCIAL — main.js  v4.1
   Fix: isAdmin() normaliza rol, renderSidebar compatible
   con páginas que tienen <header class="main-header">
   ═══════════════════════════════════════════════════════ */

const API_BASE = '/api';

/* ─── Auth ───────────────────────────────────── */
const Auth = {
  token()    { return localStorage.getItem('access_token'); },
  user()     { return localStorage.getItem('username') || 'admin'; },
  role()     { return (localStorage.getItem('role') || '').toUpperCase(); },
  isAdmin()  { return this.role() === 'ADMIN'; },
  loggedIn() { return !!this.token(); },
  save(token, username, role) {
    localStorage.setItem('access_token', token);
    localStorage.setItem('username',     username);
    localStorage.setItem('role',         (role || '').toUpperCase());
  },
  clear() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
  },
  require() {
    if (!this.loggedIn()) { window.location.href = '/login'; return false; }
    return true;
  }
};

/* ─── API Request ────────────────────────────── */
async function apiRequest(endpoint, method = 'GET', data = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (Auth.token()) headers['Authorization'] = `Bearer ${Auth.token()}`;
  try {
    const opts = { method, headers };
    if (data) opts.body = JSON.stringify(data);
    const res = await fetch(`${API_BASE}${endpoint}`, opts);
    if (res.status === 401) { Auth.clear(); window.location.href = '/login'; return null; }
    if (!res.ok) {
      let msg = `Error ${res.status}`;
      try { msg = (await res.json()).detail || msg; } catch (_) {}
      showToast(msg, 'error');
      return null;
    }
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? await res.json() : null;
  } catch (err) {
    showToast('Error de conexión con el servidor', 'error');
    return null;
  }
}

/* ─── Toasts ─────────────────────────────────── */
function showToast(msg, type = 'success') {
  const icons = { success: '✓', error: '✕', warning: '⚠' };
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span>${icons[type] || '·'}</span> ${msg}`;
  let box = document.getElementById('notification');
  if (!box) { box = document.createElement('div'); box.id = 'notification'; document.body.appendChild(box); }
  box.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .4s'; setTimeout(() => el.remove(), 400); }, 3500);
}

/* ─── Formato ────────────────────────────────── */
function formatMoney(v) {
  return parseFloat(v || 0).toLocaleString('es-PA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function formatDate(str) {
  if (!str) return '—';
  try { const [y, m, d] = str.split('T')[0].split('-'); return `${d}/${m}/${y}`; }
  catch (_) { return str; }
}
function todayISO() { return new Date().toISOString().split('T')[0]; }
function todayLong() {
  return new Date().toLocaleDateString('es-PA', { year: 'numeric', month: 'long', day: 'numeric' });
}

/* ─── Sidebar ────────────────────────────────── */
const NAV_PAGES = [
  { href: '/static/index.html',      label: 'Inicio',         icon: 'fa-home',         id: 'index'      },
  { href: '/static/properties.html', label: 'Propiedades',    icon: 'fa-building',     id: 'properties' },
  { href: '/static/units.html',      label: 'Unidades',       icon: 'fa-door-open',    id: 'units'      },
  { href: '/static/owners.html',     label: 'Propietarios',   icon: 'fa-users',        id: 'owners'     },
  { href: '/static/finances.html',   label: 'Finanzas',       icon: 'fa-chart-line',   id: 'finances'   },
  { href: '/static/suppliers.html',  label: 'Proveedores',    icon: 'fa-truck',        id: 'suppliers'  },
  { href: '/static/agenda.html',     label: 'Agenda',         icon: 'fa-calendar-alt', id: 'agenda'     },
  { href: '/static/reports.html',    label: 'Reportes',       icon: 'fa-chart-bar',    id: 'reports'    },
  { href: '/static/imports.html',    label: 'Importar/Exp.',  icon: 'fa-file-import',  id: 'imports'    },
  { href: '/static/historial.html',  label: 'Historial',      icon: 'fa-history',      id: 'historial'  },
  { href: '/static/admin.html',      label: 'Administración', icon: 'fa-shield-alt',   id: 'admin', adminOnly: true },
  { href: '/static/garita.html',     label: 'Garita',         icon: 'fa-shield-alt',   id: 'garita', garitaVisible: true },
];

function renderSidebar(activePage) {
  if (!Auth.require()) return;

  const isAdmin = Auth.isAdmin();

  if (!document.getElementById('_sidebar')) {
    // ── Obtener solo el contenido relevante ──────────────────────────
    // Algunas páginas tienen <header class="main-header" id="main-header">
    // que ya no se usa con el sidebar. Lo eliminamos antes de capturar.
    const oldHeader = document.querySelector('header.main-header');
    if (oldHeader) oldHeader.remove();

    // Capturar el contenido del body (sin el header viejo)
    const existingContent = document.body.innerHTML;

    document.body.innerHTML = `
      <aside class="sidebar" id="_sidebar">
        <div class="sidebar-brand">
          <div class="sidebar-logo" id="_sidebar_logo">AR</div>
          <div class="sidebar-brand-text">
            <h1>ALIANZA RESIDENCIAL</h1>
            <p>Administración de Propiedades</p>
          </div>
        </div>
        <nav class="sidebar-nav" id="_sidebar_nav"></nav>
        <div class="sidebar-footer">
          <div class="sidebar-user">
            <div class="sidebar-user-avatar" id="_sb_avatar">A</div>
            <div class="sidebar-user-info">
              <strong id="_sb_username"></strong>
              <span id="_sb_role_label">Usuario</span>
            </div>
            <div class="sidebar-user-actions">
              <button class="sidebar-icon-btn" onclick="logout()" title="Cerrar sesión">
                <i class="fas fa-sign-out-alt"></i>
              </button>
            </div>
          </div>
        </div>
      </aside>
      <button class="sidebar-toggle" id="_sb_toggle" onclick="toggleSidebar()" title="Colapsar menú">
        <i class="fas fa-chevron-left" id="_sb_toggle_icon"></i>
      </button>
      <div class="main-wrapper">
        <div class="topbar">
          <div class="topbar-left">
            <span class="topbar-title" id="_topbar_title"></span>
          </div>
          <div class="topbar-right">
            <span class="topbar-date" id="_topbar_date"></span>
          </div>
        </div>
        ${existingContent}
      </div>
      <div id="notification"></div>`;
  }

  // Llenar nav — filtrar páginas adminOnly si no es admin
  const nav = document.getElementById('_sidebar_nav');
  nav.innerHTML = NAV_PAGES
    filter(p => {
      if (p.adminOnly && !isAdmin) return false;
      // Garita: visible para ADMIN, USER y GARITA — no para otros roles que no existen aún
      return true;
    })
    .map(p => `
      <a href="${p.href}" class="${activePage === p.id ? 'active' : ''}">
        <i class="fas ${p.icon}"></i>
        <span>${p.label}</span>
      </a>`).join('');

  // Usuario y rol
  const u        = Auth.user();
  const rolLabel = isAdmin ? 'Administrador' : 'Usuario';
  const elU = document.getElementById('_sb_username');
  const elR = document.getElementById('_sb_role_label');
  const av  = document.getElementById('_sb_avatar');
  if (elU) elU.textContent = u;
  if (elR) elR.textContent = rolLabel;
  if (av)  av.textContent  = u.charAt(0).toUpperCase();

  // Título y fecha
  const page = NAV_PAGES.find(p => p.id === activePage);
  const tt   = document.getElementById('_topbar_title');
  const td   = document.getElementById('_topbar_date');
  if (tt && page) tt.textContent = page.label;
  if (td) td.textContent = todayLong();

  // Logo
  const logo = document.getElementById('_sidebar_logo');
  if (logo) {
    const img = new Image();
    img.onload  = () => { logo.innerHTML = `<img src="/static/logo.png" alt="Logo">`; };
    img.onerror = () => {};
    img.src = '/static/logo.png';
  }

  const collapsed = localStorage.getItem('sidebar_collapsed') === '1';
  if (collapsed) _applySidebarCollapse(true, false);
}

/* Alias para páginas que usan renderHeader */
function renderHeader(activePage) { renderSidebar(activePage); }

function toggleSidebar() {
  const collapsed = document.getElementById('_sidebar').classList.contains('collapsed');
  _applySidebarCollapse(!collapsed, true);
}

function _applySidebarCollapse(collapse, save) {
  const sb   = document.getElementById('_sidebar');
  const icon = document.getElementById('_sb_toggle_icon');
  if (!sb) return;
  if (collapse) {
    sb.classList.add('collapsed');
    document.body.classList.add('sidebar-collapsed');
    if (icon) { icon.classList.remove('fa-chevron-left'); icon.classList.add('fa-chevron-right'); }
  } else {
    sb.classList.remove('collapsed');
    document.body.classList.remove('sidebar-collapsed');
    if (icon) { icon.classList.remove('fa-chevron-right'); icon.classList.add('fa-chevron-left'); }
  }
  if (save) localStorage.setItem('sidebar_collapsed', collapse ? '1' : '0');
}

function logout() { Auth.clear(); window.location.href = '/login'; }

/* ─── Loaders de selects ─────────────────────── */
async function loadSelectOptions(selectId, endpoint, valFn, labelFn, ph = 'Seleccione...') {
  const sel = document.getElementById(selectId);
  if (!sel) return [];
  const items = await apiRequest(endpoint) || [];
  sel.innerHTML = `<option value="">${ph}</option>`;
  items.forEach(i => sel.innerHTML += `<option value="${valFn(i)}">${labelFn(i)}</option>`);
  return items;
}
async function loadPropertiesSelect(id = 'property-select') {
  return loadSelectOptions(id, '/properties', p => p.id, p => p.name, 'Seleccione propiedad');
}
async function loadOwnersSelect(id = 'owner-select') {
  return loadSelectOptions(id, '/owners', o => o.id, o => o.full_name, 'Seleccione propietario');
}
async function loadUnitsSelect(id = 'unit-select', propId = null) {
  const all = await apiRequest('/units') || [];
  const filtered = propId ? all.filter(u => u.property_id === parseInt(propId)) : all;
  const sel = document.getElementById(id);
  if (!sel) return filtered;
  sel.innerHTML = '<option value="">Seleccione unidad</option>';
  filtered.forEach(u => sel.innerHTML += `<option value="${u.id}">Apt. ${u.unit_number}</option>`);
  return filtered;
}
