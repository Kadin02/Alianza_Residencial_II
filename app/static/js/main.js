/* ════════════════════════════════════════════════════════════════
   main.js  — Alianza Residencial
   CAMBIOS:
   · Auth.role() ahora expone el rol del token JWT
   · Auth.isGarita() para detectar rol GARITA
   · renderSidebar() filtra menú según rol:
       ADMIN  → todo el menú
       USER   → todo excepto Administración
       GARITA → solo Garita (sin acceso a nada más)
   · Protección de páginas: si el rol no tiene acceso, redirige a garita.html
   · rolLabel muestra "Seguridad Garita" para el rol GARITA
   · Protección de rutas en cada página sensible
   · FIX: conflicto de git resuelto en NAV_PAGES (Agenda)
   · FIX: GARITA ahora solo ve el ítem "Garita / Visitas" en el sidebar
════════════════════════════════════════════════════════════════ */

/* ─── Auth ────────────────────────────────────────────────── */
const Auth = {
  _key: 'alianza_token',
  _user: 'alianza_user',
  _role: 'alianza_role',

  save(token, username, role) {
    localStorage.setItem(this._key,  token);
    localStorage.setItem(this._user, username);
    localStorage.setItem(this._role, role || 'USER');
  },

  token()   { return localStorage.getItem(this._key);  },
  user()    { return localStorage.getItem(this._user) || ''; },
  role()    { return localStorage.getItem(this._role) || 'USER'; },

  isAdmin()  { return this.role() === 'ADMIN';  },
  isGarita() { return this.role() === 'GARITA'; },

  clear() {
    localStorage.removeItem(this._key);
    localStorage.removeItem(this._user);
    localStorage.removeItem(this._role);
  },

  // Requiere sesión activa — redirige a login si no hay token
  require() {
    if (!this.token()) {
      window.location.href = '/login';
      return false;
    }
    return true;
  },

  // Requiere que el rol tenga acceso a esta área
  // Si es GARITA y está en una página que no es garita.html → redirige
  requireNotGarita() {
    if (this.isGarita()) {
      window.location.href = '/static/garita.html';
      return false;
    }
    return true;
  },
};

/* ─── API ─────────────────────────────────────────────────── */
async function apiRequest(endpoint, method = 'GET', body = null) {
  const token = Auth.token();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  try {
    const res = await fetch(`/api${endpoint}`, opts);

    if (res.status === 401) {
      Auth.clear();
      window.location.href = '/login';
      return null;
    }

    if (res.status === 403) {
      showToast('No tienes permiso para realizar esta acción', 'error');
      return null;
    }

    if (!res.ok) {
      let detail = `Error ${res.status}`;
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      showToast(detail, 'error');
      return null;
    }

    if (res.status === 204) return {};
    return await res.json();
  } catch (e) {
    showToast('Error de conexión con el servidor', 'error');
    return null;
  }
}

/* ─── Toasts ─────────────────────────────────────────────── */
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

/* ─── Formato ────────────────────────────────────────────── */
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

/* ─── Sidebar ────────────────────────────────────────────── */

// Definición de páginas del menú
// roles: array de roles que pueden ver este ítem
//   ['ADMIN', 'USER', 'GARITA'] = todos
//   ['ADMIN', 'USER']           = no garita
//   ['ADMIN']                   = solo admin
//
// GARITA solo aparece en el ítem 'garita' — no puede ver ningún otro módulo.
const NAV_PAGES = [
  { href: '/static/index.html',      label: 'Inicio',           icon: 'fa-home',         id: 'index',      roles: ['ADMIN', 'USER'] },
  { href: '/static/properties.html', label: 'Propiedades',      icon: 'fa-building',     id: 'properties', roles: ['ADMIN', 'USER'] },
  { href: '/static/units.html',      label: 'Unidades',         icon: 'fa-door-open',    id: 'units',      roles: ['ADMIN', 'USER'] },
  { href: '/static/owners.html',     label: 'Propietarios',     icon: 'fa-users',        id: 'owners',     roles: ['ADMIN', 'USER'] },
  { href: '/static/finances.html',   label: 'Financiero',       icon: 'fa-chart-line',   id: 'finances',   roles: ['ADMIN', 'USER'] },
  { href: '/static/suppliers.html',  label: 'Proveedores',      icon: 'fa-truck',        id: 'suppliers',  roles: ['ADMIN', 'USER'] },
  // FIX: conflicto git resuelto — Agenda solo para ADMIN y USER (no GARITA)
  { href: '/static/agenda.html',     label: 'Agenda',           icon: 'fa-calendar-alt', id: 'agenda',     roles: ['ADMIN', 'USER'] },
  { href: '/static/imports.html',    label: 'Importar/Exp.',    icon: 'fa-file-import',  id: 'imports',    roles: ['ADMIN', 'USER'] },
  // Administración: solo ADMIN
  { href: '/static/admin.html',      label: 'Administración',   icon: 'fa-shield-alt',   id: 'admin',      roles: ['ADMIN'] },
  // Garita: visible para ADMIN, USER y GARITA
  // GARITA solo verá este ítem en su menú
  { href: '/static/garita.html',     label: 'Garita / Visitas', icon: 'fa-car',          id: 'garita',     roles: ['ADMIN', 'USER', 'GARITA'] },
];

// Etiquetas de rol para mostrar al usuario
const ROLE_LABELS = {
  'ADMIN':  'Administrador',
  'USER':   'Usuario',
  'GARITA': 'Seguridad Garita',
};

function renderSidebar(activePage) {
  if (!Auth.require()) return;

  const role    = Auth.role();
  const isAdmin = Auth.isAdmin();

  // ── Protección de ruta ────────────────────────────────────────
  // Si la página actual no está permitida para este rol → redirigir
  // (activePage puede ser un id de subpágina, ej: 'finances-historial')
  const currentPage = NAV_PAGES.find(p => p.id === activePage)
    || NAV_PAGES.find(p => (p.children || []).some(c => c.id === activePage));
  if (currentPage && !currentPage.roles.includes(role)) {
    // GARITA intentando acceder a cualquier página que no sea garita → redirigir
    if (Auth.isGarita()) {
      window.location.href = '/static/garita.html';
      return;
    }
    // USER intentando llegar a página de admin → redirigir a inicio
    window.location.href = '/static/index.html';
    return;
  }

  // Si no hay página definida en NAV_PAGES y es GARITA → redirigir
  // (protege rutas no listadas, ej: index.html no está en roles de GARITA)
  if (!currentPage && Auth.isGarita()) {
    window.location.href = '/static/garita.html';
    return;
  }

  if (!document.getElementById('_sidebar')) {
    const oldHeader = document.querySelector('header.main-header');
    if (oldHeader) oldHeader.remove();

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
        <i class="fas fa-angles-left" id="_sb_toggle_icon"></i>
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

  // Llenar nav — filtrar según el rol del usuario
  // GARITA solo verá los ítems donde su rol está incluido → únicamente "Garita / Visitas"
  const nav = document.getElementById('_sidebar_nav');
  nav.innerHTML = NAV_PAGES
    .filter(p => p.roles.includes(role))
    .map(p => {
      if (!p.children) {
        return `
          <a href="${p.href}" class="${activePage === p.id ? 'active' : ''}">
            <i class="fas ${p.icon}"></i>
            <span>${p.label}</span>
          </a>`;
      }
      const childActive = p.children.some(c => c.id === activePage);
      const groupOpen = childActive || activePage === p.id;
      return `
        <div class="nav-group ${groupOpen ? 'open' : ''}">
          <a href="#" class="nav-group-toggle ${childActive ? 'active' : ''}" onclick="_toggleNavGroup(event, this)">
            <i class="fas ${p.icon}"></i>
            <span>${p.label}</span>
            <i class="fas fa-chevron-down nav-group-arrow"></i>
          </a>
          <div class="nav-group-children">
            ${p.children.map(c => `
              <a href="${c.href}" class="nav-child ${activePage === c.id ? 'active' : ''}">
                <i class="fas ${c.icon}"></i>
                <span>${c.label}</span>
              </a>`).join('')}
          </div>
        </div>`;
    }).join('');

  // Usuario, rol y avatar
  const u        = Auth.user();
  const rolLabel = ROLE_LABELS[role] || role;
  const elU = document.getElementById('_sb_username');
  const elR = document.getElementById('_sb_role_label');
  const av  = document.getElementById('_sb_avatar');
  if (elU) elU.textContent = u;
  if (elR) elR.textContent = rolLabel;
  if (av)  av.textContent  = u.charAt(0).toUpperCase();

  // Color del avatar según rol
  if (av) {
    if (role === 'ADMIN')  av.style.background = '#fbbf24'; // amarillo admin
    if (role === 'GARITA') av.style.background = '#34d399'; // verde garita
  }

  // Título y fecha en topbar (busca en páginas de primer nivel y en subpáginas)
  const page = NAV_PAGES.find(p => p.id === activePage)
    || NAV_PAGES.flatMap(p => p.children || []).find(c => c.id === activePage);
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

/* Expandir/colapsar un grupo de subpáginas en el sidebar */
function _toggleNavGroup(e, el) {
  e.preventDefault();
  el.parentElement.classList.toggle('open');
}

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
    if (icon) { icon.classList.remove('fa-angles-left'); icon.classList.add('fa-angles-right'); }
  } else {
    sb.classList.remove('collapsed');
    document.body.classList.remove('sidebar-collapsed');
    if (icon) { icon.classList.remove('fa-angles-right'); icon.classList.add('fa-angles-left'); }
  }
  if (save) localStorage.setItem('sidebar_collapsed', collapse ? '1' : '0');
}

function logout() { Auth.clear(); window.location.href = '/login'; }

/* ─── Loaders de selects ─────────────────────────────────── */
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
