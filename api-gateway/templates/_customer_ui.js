const ShopUI = (() => {
  const API_BASE = window.location.origin;
  const STAFF_ROLES = ['admin', 'manager', 'staff'];
  const notificationTypeLabels = {
    order: 'Đơn hàng',
    shipping: 'Vận chuyển',
    payment: 'Thanh toán',
    review: 'Đánh giá',
    system: 'Hệ thống'
  };
  let notificationItems = [];
  let notificationsLoaded = false;
  let notificationLoading = false;
  let notificationError = '';
  const images = {
    books: 'https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=700&q=80',
    fiction: 'https://images.unsplash.com/photo-1519682337058-a94d519337bc?auto=format&fit=crop&w=700&q=80',
    science: 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=700&q=80',
    phones: 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=700&q=80',
    electronics: 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=700&q=80',
    laptops: 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=700&q=80',
    fashion: 'https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=700&q=80',
    mens: 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=700&q=80',
    womens: 'https://images.unsplash.com/photo-1496747611176-843222e1e57c?auto=format&fit=crop&w=700&q=80',
    shoes: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=700&q=80',
    default: 'https://images.unsplash.com/photo-1472851294608-062f824d29cc?auto=format&fit=crop&w=700&q=80'
  };

  function token() { return localStorage.getItem('token') || ''; }
  function userId() { return localStorage.getItem('user_id') || ''; }
  function username() { return localStorage.getItem('username') || ''; }
  function role() { return localStorage.getItem('role') || ''; }

  function authHeaders(json = true) {
    const h = {};
    if (json) h['Content-Type'] = 'application/json';
    if (token()) h.Authorization = `Bearer ${token()}`;
    return h;
  }

  function safeList(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.results)) return payload.results;
    if (Array.isArray(payload?.products)) return payload.products;
    if (Array.isArray(payload?.items)) return payload.items;
    return [];
  }

  function money(value) {
    const n = Number(value || 0);
    return `${n.toLocaleString('vi-VN')}₫`;
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[ch]));
  }

  function decodeJwtPayload(jwt) {
    try {
      const raw = jwt.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      return JSON.parse(atob(raw));
    } catch (_) {
      return {};
    }
  }

  function saveSession(data, fallbackUsername = '') {
    const access = data.access || data.token;
    if (!access) throw new Error('missing access token');
    const payload = decodeJwtPayload(access);
    localStorage.setItem('token', access);
    localStorage.setItem('refresh', data.refresh || '');
    localStorage.setItem('user_id', String(data.user_id || payload.user_id || ''));
    localStorage.setItem('username', data.username || payload.username || fallbackUsername || '');
    localStorage.setItem('role', data.role || payload.role || 'customer');
    updateNav();
  }

  function clearSession() {
    ['token', 'refresh', 'user_id', 'username', 'role'].forEach(k => localStorage.removeItem(k));
    updateNav();
  }

  function logout(redirectTo = '/') {
    clearSession();
    window.location.href = redirectTo;
  }

  function updateNav() {
    document.querySelectorAll('[data-auth-user]').forEach(el => {
      el.textContent = token() ? `Xin chào ${username() || 'bạn'}` : 'Khách';
    });
    document.querySelectorAll('[data-auth-role]').forEach(el => {
      el.textContent = token() ? (role() || 'customer') : 'guest';
    });
    document.querySelectorAll('[data-auth-only]').forEach(el => {
      el.style.display = token() ? 'inline-flex' : 'none';
    });
    document.querySelectorAll('[data-guest-only]').forEach(el => {
      el.style.display = token() ? 'none' : 'inline-flex';
    });
    if (token()) {
      loadHeaderNotifications();
    } else {
      notificationsLoaded = false;
      notificationItems = [];
      notificationError = '';
      closeNotifications();
      renderHeaderNotifications();
    }
  }

  function isStaffRole() {
    return STAFF_ROLES.includes((role() || '').toLowerCase());
  }

  function isInternalNotification(notif) {
    return ['admin', 'manager', 'staff'].includes(String(notif?.recipient_type || '').toLowerCase());
  }

  function isHeaderVisibleNotification(notif) {
    if (isInternalNotification(notif)) return isStaffRole();
    return true;
  }

  function notificationRecipientLabel(notif) {
    const recipientType = String(notif?.recipient_type || '').toLowerCase();
    if (isInternalNotification(notif)) return 'Nội bộ';
    if (recipientType === 'all') return 'Hệ thống chung';
    return 'Khách hàng';
  }

  function notificationStatus(notif) {
    return String(notif?.status || 'unread').toLowerCase();
  }

  function formatTime(value) {
    const date = value ? new Date(value) : new Date();
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('vi-VN');
  }

  function headerNotificationNodes() {
    return {
      widget: document.querySelector('[data-notification-widget]'),
      trigger: document.querySelector('.notification-trigger'),
      badge: document.querySelector('[data-notification-badge]'),
      menu: document.querySelector('[data-notification-menu]'),
      list: document.querySelector('[data-notification-list]'),
      summary: document.querySelector('[data-notification-summary]')
    };
  }

  function renderHeaderNotifications() {
    const { trigger, badge, list, summary } = headerNotificationNodes();
    if (!list || !badge || !summary) return;
    const visible = token() ? notificationItems.filter(isHeaderVisibleNotification) : [];
    const unread = visible.filter(item => notificationStatus(item) === 'unread').length;
    if (!token()) {
      list.innerHTML = '<div class="notification-empty">Đăng nhập để xem thông báo.</div>';
      summary.textContent = 'Chưa đăng nhập';
    } else if (notificationLoading && !notificationsLoaded) {
      list.innerHTML = '<div class="notification-empty">Đang tải thông báo...</div>';
      summary.textContent = 'Đang tải';
    } else if (notificationError) {
      list.innerHTML = `<div class="notification-empty">${escapeHtml(notificationError)}</div>`;
      summary.textContent = 'Không tải được';
    } else if (!visible.length) {
      list.innerHTML = '<div class="notification-empty">Bạn chưa có thông báo mới.</div>';
      summary.textContent = 'Không có thông báo';
    } else {
      summary.textContent = unread ? `${unread} thông báo chưa đọc` : 'Tất cả đã đọc';
      list.innerHTML = visible.slice(0, 6).map(notif => {
        const type = String(notif.type || 'system').toLowerCase();
        const isUnread = notificationStatus(notif) === 'unread';
        return `
          <article class="notification-dropdown-item ${isUnread ? 'unread' : ''}">
            <a href="/notifications/" onclick="ShopUI.markNotificationRead(${Number(notif.id || 0)}, event)">
              <div class="notification-mini-type">
                <span>${escapeHtml(notificationTypeLabels[type] || type)}</span>
                <span class="recipient-pill">${escapeHtml(notificationRecipientLabel(notif))}</span>
              </div>
              <div class="notification-mini-title">${escapeHtml(notif.title || 'Thông báo')}</div>
              <div class="notification-mini-msg">${escapeHtml(notif.content || '')}</div>
              <div class="notification-mini-time">${escapeHtml(formatTime(notif.created_at))}</div>
            </a>
            ${isUnread ? '<span class="notification-mini-dot" aria-label="Chưa đọc"></span>' : ''}
          </article>
        `;
      }).join('');
    }
    const badgeText = unread > 99 ? '99+' : String(unread);
    badge.hidden = unread <= 0;
    badge.textContent = badgeText;
    if (trigger) {
      trigger.classList.toggle('has-unread', unread > 0);
      trigger.setAttribute('aria-label', unread > 0 ? `Thông báo, ${unread} chưa đọc` : 'Thông báo');
    }
  }

  async function loadHeaderNotifications(force = false) {
    if (!token()) {
      renderHeaderNotifications();
      return [];
    }
    if (notificationLoading || (notificationsLoaded && !force)) {
      renderHeaderNotifications();
      return notificationItems;
    }
    notificationLoading = true;
    notificationError = '';
    renderHeaderNotifications();
    try {
      const data = await fetchJson(`${API_BASE}/api/notifications/`, { headers: authHeaders(false) });
      notificationItems = safeList(data).sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
      notificationsLoaded = true;
    } catch (_) {
      notificationItems = [];
      notificationsLoaded = true;
      notificationError = 'Không tải được thông báo.';
    } finally {
      notificationLoading = false;
      renderHeaderNotifications();
    }
    return notificationItems;
  }

  function positionNotificationMenu() {
    const { trigger, menu } = headerNotificationNodes();
    if (!trigger || !menu) return;
    const rect = trigger.getBoundingClientRect();
    const top = Math.round(rect.bottom + 8);
    const right = Math.max(12, Math.round(window.innerWidth - rect.right));
    menu.style.setProperty('--notification-top', `${top}px`);
    menu.style.setProperty('--notification-right', `${right}px`);
  }

  function openNotifications() {
    if (!token()) return;
    const { widget, trigger, menu } = headerNotificationNodes();
    if (!widget || !trigger || !menu) return;
    positionNotificationMenu();
    widget.classList.add('open');
    trigger.setAttribute('aria-expanded', 'true');
    menu.setAttribute('aria-hidden', 'false');
    loadHeaderNotifications(true);
  }

  function closeNotifications() {
    const { widget, trigger, menu } = headerNotificationNodes();
    if (!widget || !trigger || !menu) return;
    widget.classList.remove('open');
    trigger.setAttribute('aria-expanded', 'false');
    menu.setAttribute('aria-hidden', 'true');
  }

  function toggleNotifications(event) {
    if (event) event.stopPropagation();
    if (!token()) {
      window.location.href = '/login/?next=/notifications/';
      return;
    }
    const { widget } = headerNotificationNodes();
    if (widget?.classList.contains('open')) {
      closeNotifications();
    } else {
      openNotifications();
    }
  }

  async function refreshNotifications(event) {
    if (event) event.stopPropagation();
    await loadHeaderNotifications(true);
  }

  async function markNotificationRead(notificationId, event) {
    if (!notificationId || !token()) return;
    if (event) event.preventDefault();
    try {
      await fetchJson(`${API_BASE}/api/notifications/${notificationId}/read/`, {
        method: 'PUT',
        headers: authHeaders(),
        body: '{}'
      });
      notificationItems = notificationItems.map(item => (
        Number(item.id) === Number(notificationId) ? { ...item, status: 'read' } : item
      ));
      renderHeaderNotifications();
    } catch (_) {
      toast('Không cập nhật được thông báo', 'err');
    }
    if (event?.currentTarget?.href) {
      window.location.href = event.currentTarget.href;
    }
  }

  async function markAllNotificationsRead(event) {
    if (event) event.stopPropagation();
    if (!token()) return;
    try {
      await fetchJson(`${API_BASE}/api/notifications/read-all/`, {
        method: 'PUT',
        headers: authHeaders(),
        body: '{}'
      });
      notificationItems = notificationItems.map(item => ({ ...item, status: 'read' }));
      renderHeaderNotifications();
    } catch (_) {
      toast('Không cập nhật được thông báo', 'err');
    }
  }

  function goSearch(inputId = 'globalSearch') {
    const input = document.getElementById(inputId);
    const q = input ? input.value.trim() : '';
    window.location.href = q ? `/products/?q=${encodeURIComponent(q)}` : '/products/';
  }

  function bindSearch(inputId = 'globalSearch') {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        goSearch(inputId);
      }
    });
    document.querySelectorAll('[data-header-search-button]').forEach(button => {
      button.addEventListener('click', () => goSearch(inputId));
    });
  }

  function imageFor(product) {
    if (product?.image_url || product?.image) return product.image_url || product.image;
    const text = `${product?.name || product?.title || ''} ${product?.category_name || product?.category || ''} ${product?.domain_name || product?.domain || ''}`.toLowerCase();
    if (text.includes('shoe')) return images.shoes;
    if (text.includes('shirt') || text.includes('mens')) return images.mens;
    if (text.includes('dress') || text.includes('womens')) return images.womens;
    if (text.includes('phone') || text.includes('iphone') || text.includes('samsung')) return images.phones;
    if (text.includes('macbook') || text.includes('laptop')) return images.laptops;
    if (text.includes('book') || text.includes('fiction') || text.includes('gatsby') || text.includes('mockingbird')) return images.books;
    if (text.includes('science') || text.includes('history of time')) return images.science;
    if (text.includes('fashion')) return images.fashion;
    if (text.includes('electronic')) return images.electronics;
    return images.default;
  }

  function fallbackImage() {
    return images.default;
  }

  function ratingMapFromReviews(reviews = []) {
    const stats = new Map();
    safeList(reviews).forEach(review => {
      const productId = Number(review.product_id || 0);
      const rating = Number(review.rating || 0);
      if (!productId || rating <= 0) return;
      const row = stats.get(productId) || { total: 0, count: 0 };
      row.total += rating;
      row.count += 1;
      stats.set(productId, row);
    });
    return stats;
  }

  function withRatings(products = [], reviews = []) {
    const stats = ratingMapFromReviews(reviews);
    return safeList(products).map(product => {
      const p = normalizeProduct(product);
      const row = stats.get(Number(p.id));
      if (!row) return { ...p, rating_avg: Number(p.rating_avg || 0), rating_count: Number(p.rating_count || 0) };
      return {
        ...p,
        rating_avg: Number((row.total / row.count).toFixed(1)),
        rating_count: row.count
      };
    });
  }

  function normalizeProduct(product) {
    const p = product || {};
    return {
      ...p,
      id: p.id || p.product_id,
      name: p.name || p.title || `Sản phẩm #${p.id || p.product_id || ''}`,
      description: p.description || p.reason || '',
      category_name: p.category_name || p.category || '',
      domain_name: p.domain_name || p.domain || '',
      price: p.price || p.unit_price || p.price_at_add || 0,
      stock: p.stock ?? p.stock_quantity ?? null,
      rating_avg: Number(p.rating_avg || p.average_rating || 0),
      rating_count: Number(p.rating_count || p.review_count || 0)
    };
  }

  function productCard(product, options = {}) {
    const p = normalizeProduct(product);
    const action = options.action || 'add';
    const secondary = options.secondary !== false;
    const status = String(p.status || 'active').toLowerCase();
    const canBuy = status === 'active' && (p.stock === null || Number(p.stock) > 0);
    const unavailableLabel = status === 'active' ? 'Hết hàng' : 'Ngưng bán';
    const stockText = p.stock === null ? (canBuy ? 'Có hàng' : unavailableLabel) : (canBuy ? `${p.stock} còn` : unavailableLabel);
    const addLabel = action === 'detail' ? 'Xem' : (canBuy ? 'Thêm giỏ' : unavailableLabel);
    const addClick = action === 'detail'
      ? `window.location.href='/products/${Number(p.id)}/'`
      : (canBuy ? `ShopUI.addToCart(${Number(p.id)})` : 'return false');
    const rating = Number(p.rating_avg || 0);
    const ratingCount = Number(p.rating_count || 0);
    const ratingHtml = ratingCount
      ? `<span class="pill amber">${rating.toFixed(1)}/5 (${ratingCount})</span>`
      : '<span class="pill">Chưa có đánh giá</span>';
    return `
      <article class="product-card" data-product-card="${escapeHtml(p.id)}">
        <a class="product-media" href="/products/${encodeURIComponent(p.id)}/" onclick="ShopUI.track('view_detail', ${Number(p.id)})" aria-label="${escapeHtml(p.name)}">
          <img src="${imageFor(p)}" alt="${escapeHtml(p.name)}" loading="lazy" onerror="this.onerror=null;this.src=ShopUI.fallbackImage()">
          <span class="product-badge">${escapeHtml(p.category_name || p.domain_name || 'Shop')}</span>
          <span class="product-stock">${escapeHtml(stockText)}</span>
        </a>
        <div class="product-body">
          <a href="/products/${encodeURIComponent(p.id)}/" onclick="ShopUI.track('view_detail', ${Number(p.id)})" class="product-title">${escapeHtml(p.name)}</a>
          <div class="product-desc">${escapeHtml(p.description || 'Sản phẩm đang có sẵn tại ShopSphere.')}</div>
          <div class="product-meta">
            ${p.domain_name ? `<span class="pill teal">${escapeHtml(p.domain_name)}</span>` : ''}
            ${ratingHtml}
            ${p.sku ? `<span class="pill">${escapeHtml(p.sku)}</span>` : ''}
          </div>
          <div class="product-foot">
            <div class="price">${money(p.price)}</div>
            <div class="product-actions">
              ${secondary ? `<button class="icon-btn" title="Yêu thích" aria-label="Lưu yêu thích" onclick="ShopUI.addWishlist(${Number(p.id)})">♡</button>` : ''}
              <button class="btn primary small" ${action === 'detail' || canBuy ? '' : 'disabled'} onclick="${addClick}">${addLabel}</button>
            </div>
          </div>
        </div>
      </article>
    `;
  }

  function toast(message, type = 'ok') {
    let el = document.getElementById('appToast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'appToast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.className = `toast ${type} show`;
    window.clearTimeout(el._timer);
    el._timer = window.setTimeout(() => el.classList.remove('show'), 2200);
  }

  function requireAuth() {
    if (token()) return true;
    toast('Vui lòng đăng nhập để tiếp tục', 'err');
    window.setTimeout(() => { window.location.href = '/login/'; }, 650);
    return false;
  }

  async function addToCart(productId, quantity = 1) {
    if (!requireAuth()) return false;
    try {
      const res = await fetch(`${API_BASE}/api/cart/add/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ product_id: productId, quantity })
      });
      if (!res.ok) throw new Error('add cart failed');
      track('add_to_cart', productId);
      toast('Đã thêm vào giỏ hàng');
      return true;
    } catch (_) {
      toast('Không thể thêm vào giỏ hàng', 'err');
      return false;
    }
  }

  async function addWishlist(productId) {
    if (!requireAuth()) return false;
    try {
      const res = await fetch(`${API_BASE}/api/wishlist/add/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ product_id: productId })
      });
      if (!res.ok) throw new Error('add wishlist failed');
      track('wishlist', productId);
      toast('Đã lưu vào yêu thích');
      return true;
    } catch (_) {
      toast('Không thể lưu yêu thích', 'err');
      return false;
    }
  }

  async function fetchJson(url, options = {}) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.detail || data.error || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }

  async function fetchAllPages(url, options = {}) {
    const items = [];
    const current = new URL(url, window.location.origin);
    let guard = 0;
    while (guard < 50) {
      const data = await fetchJson(current.toString(), options);
      const pageItems = safeList(data);
      items.push(...pageItems);
      if (!data.next || !pageItems.length) break;
      const page = Number(current.searchParams.get('page') || 1) + 1;
      current.searchParams.set('page', String(page));
      guard += 1;
    }
    return items;
  }

  function track(interactionType, productId = 0, extra = {}) {
    const uid = userId();
    if (!uid || !interactionType) return false;
    const payload = {
      customer_id: Number(uid),
      product_id: Number(productId || 0),
      interaction_type: interactionType,
      ...extra
    };
    const body = JSON.stringify(payload);
    try {
      if (navigator.sendBeacon) {
        const blob = new Blob([body], { type: 'application/json' });
        navigator.sendBeacon(`${API_BASE}/api/v1/track`, blob);
        return true;
      }
    } catch (_) {}
    fetch(`${API_BASE}/api/v1/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true
    }).catch(() => {});
    return true;
  }

  function trackMany(interactionType, productIds = [], extra = {}) {
    [...new Set(productIds.map(x => Number(x || 0)).filter(Boolean))]
      .slice(0, 5)
      .forEach(pid => track(interactionType, pid, extra));
  }

  function init() {
    updateNav();
    bindSearch();
    document.addEventListener('click', event => {
      const { widget } = headerNotificationNodes();
      if (widget && !widget.contains(event.target)) closeNotifications();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeNotifications();
    });
    window.addEventListener('resize', positionNotificationMenu);
  }

  return {
    API_BASE,
    token,
    userId,
    username,
    role,
    authHeaders,
    safeList,
    money,
    escapeHtml,
    saveSession,
    clearSession,
    logout,
    updateNav,
    goSearch,
    bindSearch,
    imageFor,
    fallbackImage,
    ratingMapFromReviews,
    withRatings,
    normalizeProduct,
    productCard,
    toast,
    requireAuth,
    addToCart,
    addWishlist,
    fetchJson,
    fetchAllPages,
    track,
    trackMany,
    toggleNotifications,
    refreshNotifications,
    markNotificationRead,
    markAllNotificationsRead,
    init
  };
})();

window.ShopUI = ShopUI;
document.addEventListener('DOMContentLoaded', ShopUI.init);
