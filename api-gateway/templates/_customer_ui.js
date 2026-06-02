const ShopUI = (() => {
  const API_BASE = window.location.origin;
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
      stock: p.stock ?? p.stock_quantity ?? null
    };
  }

  function productCard(product, options = {}) {
    const p = normalizeProduct(product);
    const action = options.action || 'add';
    const secondary = options.secondary !== false;
    const stockText = p.stock === null ? 'Kho' : `${p.stock} còn`;
    const addLabel = action === 'detail' ? 'Xem' : 'Thêm';
    return `
      <article class="product-card" data-product-card="${escapeHtml(p.id)}">
        <a class="product-media" href="/products/${encodeURIComponent(p.id)}/" onclick="ShopUI.track('view_detail', ${Number(p.id)})" aria-label="${escapeHtml(p.name)}">
          <img src="${imageFor(p)}" alt="${escapeHtml(p.name)}" loading="lazy">
          <span class="product-badge">${escapeHtml(p.category_name || p.domain_name || 'Shop')}</span>
          <span class="product-stock">${escapeHtml(stockText)}</span>
        </a>
        <div class="product-body">
          <a href="/products/${encodeURIComponent(p.id)}/" onclick="ShopUI.track('view_detail', ${Number(p.id)})" class="product-title">${escapeHtml(p.name)}</a>
          <div class="product-desc">${escapeHtml(p.description || 'Sản phẩm đang có sẵn tại ShopSphere.')}</div>
          <div class="product-meta">
            ${p.domain_name ? `<span class="pill teal">${escapeHtml(p.domain_name)}</span>` : ''}
            ${p.sku ? `<span class="pill">${escapeHtml(p.sku)}</span>` : ''}
          </div>
          <div class="product-foot">
            <div class="price">${money(p.price)}</div>
            <div style="display:flex;gap:.35rem">
              ${secondary ? `<button class="icon-btn" title="Yêu thích" onclick="ShopUI.addWishlist(${Number(p.id)})">♡</button>` : ''}
              <button class="btn primary small" onclick="${action === 'detail' ? `window.location.href='/products/${Number(p.id)}/'` : `ShopUI.addToCart(${Number(p.id)})`}">${addLabel}</button>
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
    init
  };
})();

document.addEventListener('DOMContentLoaded', ShopUI.init);
