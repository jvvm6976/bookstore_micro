const Portal = (() => {
  const state = {
    users: [], roles: [], domains: [], categories: [], products: [],
    orders: [], shipments: [], reviews: [], notifications: [], payments: new Map()
  };
  let modalSubmit = null;

  const page = document.body.dataset.portalPage || 'dashboard';
  const kind = document.body.dataset.portalKind || 'staff';
  const esc = value => ShopUI.escapeHtml(value ?? '');
  const money = value => ShopUI.money(value || 0);
  const date = value => value ? new Date(value).toLocaleString('vi-VN') : '-';
  const safeList = payload => Array.isArray(payload) ? payload : (payload?.results || payload?.items || payload?.orders || payload?.recommendations || []);
  const auth = (json = true) => ShopUI.authHeaders(json);

  function statusLabel(value) {
    const labels = {
      pending: 'Chờ xử lý', paid: 'Đã xác nhận', processing: 'Đang chuẩn bị',
      shipping: 'Đang giao', delivered: 'Đã giao', completed: 'Hoàn tất',
      cancelled: 'Đã hủy', failed: 'Thất bại', success: 'Thành công',
      refunded: 'Đã hoàn tiền', approved: 'Đã duyệt', rejected: 'Từ chối',
      active: 'Đang hoạt động', inactive: 'Ngừng hoạt động', unread: 'Chưa đọc', read: 'Đã đọc',
      admin: 'Quản trị viên', manager: 'Quản lý', staff: 'Nhân viên', customer: 'Khách hàng', guest: 'Chưa đăng nhập',
      all: 'Tất cả', new: 'Khách hàng mới', casual: 'Mua sắm thỉnh thoảng',
      engaged: 'Quan tâm thường xuyên', loyal: 'Khách hàng gắn bó', champion: 'Khách hàng nổi bật'
    };
    return labels[String(value || '').toLowerCase()] || value || '-';
  }

  function status(value) {
    const key = String(value || '').toLowerCase();
    return `<span class="portal-status ${esc(key)}">${esc(statusLabel(key))}</span>`;
  }

  function icon(name) {
    return `<i data-lucide="${name}"></i>`;
  }

  function refreshIcons() {
    if (window.lucide) window.lucide.createIcons({ attrs: { 'stroke-width': 1.8 } });
  }

  async function api(route, options = {}) {
    const config = { ...options, headers: options.headers || auth(options.body !== undefined) };
    if (options.body !== undefined && typeof options.body !== 'string') config.body = JSON.stringify(options.body);
    return ShopUI.fetchJson(`${ShopUI.API_BASE}${route}`, config);
  }

  async function apiForm(route, formData, method = 'POST') {
    return ShopUI.fetchJson(`${ShopUI.API_BASE}${route}`, {
      method,
      headers: auth(false),
      body: formData
    });
  }

  async function all(route) {
    return ShopUI.fetchAllPages(`${ShopUI.API_BASE}${route}`, { headers: auth(false) });
  }

  function toast(message, type = 'ok') {
    const node = document.getElementById('portalToast');
    node.textContent = message;
    node.className = `portal-toast ${type === 'error' ? 'error' : ''} show`;
    clearTimeout(node._timer);
    node._timer = setTimeout(() => node.classList.remove('show'), 2400);
  }

  function empty(title, text = '') {
    return `<div class="portal-empty">${icon('inbox')}<strong>${esc(title)}</strong><span>${esc(text)}</span></div>`;
  }

  function loading() {
    return '<div class="portal-loading"><div>Đang tải dữ liệu</div></div>';
  }

  function openModal({ title, eyebrow = 'Thao tác', body, submitLabel = 'Lưu', onSubmit }) {
    document.getElementById('portalModalTitle').textContent = title;
    document.getElementById('portalModalEyebrow').textContent = eyebrow;
    document.getElementById('portalModalBody').innerHTML = body;
    document.getElementById('portalModalSubmit').textContent = submitLabel;
    document.getElementById('portalModalLayer').classList.add('open');
    document.getElementById('portalModalLayer').setAttribute('aria-hidden', 'false');
    modalSubmit = onSubmit;
    refreshIcons();
    setTimeout(() => document.querySelector('#portalModalBody input, #portalModalBody select')?.focus(), 40);
  }

  function closeModal() {
    document.getElementById('portalModalLayer').classList.remove('open');
    document.getElementById('portalModalLayer').setAttribute('aria-hidden', 'true');
    modalSubmit = null;
  }

  async function handleModalSubmit(event) {
    event.preventDefault();
    if (!modalSubmit) return;
    const button = document.getElementById('portalModalSubmit');
    button.disabled = true;
    try {
      await modalSubmit(new FormData(event.currentTarget));
      closeModal();
    } catch (error) {
      toast(error.message || 'Không thể lưu thay đổi', 'error');
    } finally {
      button.disabled = false;
    }
  }

  function field(label, name, value = '', options = {}) {
    const type = options.type || 'text';
    const full = options.full ? ' full' : '';
    const required = options.required === false ? '' : ' required';
    const placeholder = options.placeholder ? ` placeholder="${esc(options.placeholder)}"` : '';
    const accept = options.accept ? ` accept="${esc(options.accept)}"` : '';
    if (type === 'textarea') {
      return `<label class="portal-field${full}"><span>${esc(label)}</span><textarea class="portal-textarea" name="${esc(name)}"${required}${placeholder}>${esc(value)}</textarea></label>`;
    }
    if (type === 'select') {
      const choices = (options.choices || []).map(item => {
        const itemValue = typeof item === 'object' ? item.value : item;
        const itemLabel = typeof item === 'object' ? item.label : item;
        return `<option value="${esc(itemValue)}" ${String(itemValue) === String(value) ? 'selected' : ''}>${esc(itemLabel)}</option>`;
      }).join('');
      return `<label class="portal-field${full}"><span>${esc(label)}</span><select class="portal-select" name="${esc(name)}"${required}>${choices}</select></label>`;
    }
    if (type === 'file') {
      return `<label class="portal-field${full}"><span>${esc(label)}</span><input class="portal-input" type="file" name="${esc(name)}"${required}${accept}></label>`;
    }
    return `<label class="portal-field${full}"><span>${esc(label)}</span><input class="portal-input" type="${esc(type)}" name="${esc(name)}" value="${esc(value)}"${required}${placeholder}></label>`;
  }

  function formGrid(...fields) {
    return `<div class="form-grid">${fields.join('')}</div>`;
  }

  function currentProductImageField(item = {}) {
    if (!item?.image_url) return '';
    const image = ShopUI.imageFor(item);
    const src = esc(image);
    const note = item.image_url === image ? item.image_url : 'Ảnh cũ không nằm trong kho local, đang dùng ảnh dự phòng.';
    const fallback = esc(ShopUI.fallbackImage(item));
    return `<div class="portal-field full product-image-preview"><span>Ảnh đang lưu</span><div class="product-image-preview-box"><img src="${src}" data-fallback-src="${fallback}" onerror="this.onerror=null;this.src=this.dataset.fallbackSrc||ShopUI.fallbackImage()"><code>${esc(note)}</code></div></div>`;
  }

  function roleAllowed() {
    const role = String(ShopUI.role() || '').toLowerCase();
    return kind === 'admin' ? ['admin', 'manager'].includes(role) : ['admin', 'manager', 'staff'].includes(role);
  }

  function setupShell() {
    const sidebar = document.getElementById('portalSidebar');
    if (localStorage.getItem('portal_sidebar_collapsed') === '1') sidebar.classList.add('collapsed');
    document.getElementById('sidebarToggle').addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      localStorage.setItem('portal_sidebar_collapsed', sidebar.classList.contains('collapsed') ? '1' : '0');
      document.getElementById('sidebarToggle').title = sidebar.classList.contains('collapsed') ? 'Mở rộng menu' : 'Thu gọn menu';
    });
    const portalUserNode = document.querySelector('[data-portal-user]');
    portalUserNode.textContent = ShopUI.displayName() || 'Tài khoản vận hành';
    ShopUI.loadDisplayName().then(name => {
      if (name) portalUserNode.textContent = name;
    });
    document.querySelector('[data-portal-role]').textContent = statusLabel(ShopUI.role() || 'guest');
    document.getElementById('portalModalForm').addEventListener('submit', handleModalSubmit);
    document.getElementById('portalModalLayer').addEventListener('click', event => {
      if (event.target.id === 'portalModalLayer') closeModal();
    });
    if (!roleAllowed()) {
      document.getElementById('portalPageContent').hidden = true;
      document.getElementById('portalAccessDenied').hidden = false;
    }
    refreshIcons();
  }

  async function loadDashboard() {
    const statsNode = document.getElementById('dashboardStats');
    const activityNode = document.getElementById('dashboardActivity');
    statsNode.innerHTML = loading();
    try {
      const requests = [all('/api/orders/'), all('/api/shipping/'), all('/api/reviews/'), all('/api/notifications/')];
      if (kind === 'admin') requests.push(all('/api/users/'), all('/api/products/'));
      const [orders, shipments, reviews, notifications, users = [], products = []] = await Promise.all(requests);
      Object.assign(state, { orders, shipments, reviews, notifications, users, products });
      const pendingReviews = reviews.filter(item => item.status === 'pending').length;
      const activeShipping = shipments.filter(item => ['processing', 'shipping'].includes(item.current_status)).length;
      const unread = notifications.filter(item => item.status === 'unread').length;
      const cards = kind === 'admin'
        ? [
            ['Người dùng', users.length, 'users', 'blue'],
            ['Sản phẩm', products.length, 'package-search', 'teal'],
            ['Đơn hàng', orders.length, 'receipt-text', 'amber'],
            ['Đánh giá chờ duyệt', pendingReviews, 'message-square-more', '']
          ]
        : [
            ['Đơn cần hỗ trợ', orders.filter(item => !['completed', 'cancelled'].includes(item.current_status)).length, 'clipboard-list', 'blue'],
            ['Vận đơn đang xử lý', activeShipping, 'truck', 'teal'],
            ['Đánh giá chờ duyệt', pendingReviews, 'star', 'amber'],
            ['Thông báo chưa đọc', unread, 'bell-ring', '']
          ];
      statsNode.innerHTML = cards.map(([label, value, iconName, tone]) => `<div class="stat-tile"><div><div class="stat-label">${esc(label)}</div><div class="stat-value">${value}</div></div><div class="stat-icon ${tone}">${icon(iconName)}</div></div>`).join('');
      const rows = [
        ...orders.slice(0, 4).map(item => ({ icon: 'receipt-text', title: `Đơn hàng #${item.id}`, meta: `${money(item.total_price)} · ${statusLabel(item.current_status)}`, time: date(item.updated_at) })),
        ...reviews.slice(0, 3).map(item => ({ icon: 'star', title: `Đánh giá ${item.rating}/5`, meta: item.comment || 'Không có bình luận', time: date(item.updated_at || item.created_at) })),
        ...notifications.slice(0, 3).map(item => ({ icon: 'bell', title: item.title, meta: item.content, time: date(item.created_at) }))
      ].slice(0, 9);
      activityNode.innerHTML = rows.length ? rows.map(row => `<div class="activity-row"><div class="activity-icon">${icon(row.icon)}</div><div><div class="activity-title">${esc(row.title)}</div><div class="activity-meta">${esc(row.meta)}</div></div><div class="activity-meta">${esc(row.time)}</div></div>`).join('') : empty('Chưa có hoạt động');
      renderDashboardChart(orders);
    } catch (error) {
      statsNode.innerHTML = empty('Không tải được tổng quan', error.message);
    }
    refreshIcons();
  }

  function renderDashboardChart(orders) {
    const node = document.getElementById('dashboardChart');
    if (!node) return;
    const days = Array.from({ length: 7 }, (_, index) => {
      const day = new Date(); day.setDate(day.getDate() - (6 - index));
      const key = day.toISOString().slice(0, 10);
      return { key, label: day.toLocaleDateString('vi-VN', { weekday: 'short' }), count: orders.filter(order => String(order.created_at || '').slice(0, 10) === key).length };
    });
    const max = Math.max(1, ...days.map(day => day.count));
    node.innerHTML = `<div class="chart-bars">${days.map(day => `<div style="flex:1"><div class="chart-bar" style="height:${Math.max(8, day.count / max * 130)}px" title="${day.count} đơn"></div><div class="chart-label">${esc(day.label)}</div></div>`).join('')}</div>`;
  }

  async function loadOrders() {
    const node = document.getElementById('ordersTable');
    node.innerHTML = loading();
    try {
      const [orders, users] = await Promise.all([all('/api/orders/'), all('/api/users/')]);
      state.orders = orders; state.users = users;
      await Promise.all(orders.slice(0, 40).map(async order => {
        try { state.payments.set(Number(order.id), await api(`/api/payments/${order.id}/`, { headers: auth(false) })); } catch (_) {}
      }));
      renderOrders();
    } catch (error) { node.innerHTML = empty('Không tải được đơn hàng', error.message); }
  }

  function customerName(userId) {
    const user = state.users.find(item => Number(item.id) === Number(userId));
    if (!user) return `Khách hàng #${userId}`;
    return `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username;
  }

  function renderOrders() {
    const query = String(document.getElementById('orderSearch')?.value || '').toLowerCase();
    const filter = document.getElementById('orderStatusFilter')?.value || '';
    const rows = state.orders.filter(order => {
      const haystack = `${order.id} ${order.user_id} ${customerName(order.user_id)}`.toLowerCase();
      return (!query || haystack.includes(query)) && (!filter || order.current_status === filter);
    });
    const node = document.getElementById('ordersTable');
    node.innerHTML = rows.length ? `<div class="table-wrap"><table class="portal-table"><thead><tr><th>Đơn</th><th>Khách hàng</th><th>Tổng tiền</th><th>Đơn hàng</th><th>Thanh toán</th><th>Cập nhật</th><th>Thao tác</th></tr></thead><tbody>${rows.map(order => {
      const payment = state.payments.get(Number(order.id));
      return `<tr><td><strong>#${order.id}</strong></td><td><strong>${esc(customerName(order.user_id))}</strong><div class="muted">ID ${order.user_id}</div></td><td>${money(order.total_price)}</td><td>${status(order.current_status)}</td><td>${payment ? status(payment.overall_status) : '<span class="muted">Chưa có</span>'}</td><td>${esc(date(order.updated_at))}</td><td><div class="actions"><button class="portal-btn" onclick="Portal.openOrder(${order.id})">${icon('eye')} Chi tiết</button></div></td></tr>`;
    }).join('')}</tbody></table></div>` : empty('Không có đơn phù hợp');
    refreshIcons();
  }

  async function openOrder(orderId) {
    const order = await api(`/api/orders/${orderId}/`, { headers: auth(false) });
    const payment = state.payments.get(Number(orderId)) || await api(`/api/payments/${orderId}/`, { headers: auth(false) }).catch(() => null);
    const shipment = await api(`/api/shipping/${orderId}/`, { headers: auth(false) }).catch(() => null);
    const body = `<div class="detail-list">
      <div class="detail-item"><span>Khách hàng</span><strong>${esc(customerName(order.user_id))}</strong></div>
      <div class="detail-item"><span>Tổng tiền</span><strong>${money(order.total_price)}</strong></div>
      <div class="detail-item"><span>Trạng thái đơn</span><strong>${status(order.current_status)}</strong></div>
      <div class="detail-item"><span>Thanh toán</span><strong>${payment ? status(payment.overall_status) : 'Chưa có'}</strong></div>
      <div class="detail-item"><span>Vận chuyển</span><strong>${shipment ? status(shipment.current_status) : 'Chưa có'}</strong></div>
      <div class="detail-item"><span>Người nhận</span><strong>${esc(order.address?.receiver_name || shipment?.receiver_name || '-')}</strong></div>
      <div class="detail-item" style="grid-column:1/-1"><span>Địa chỉ</span><strong>${esc(order.address?.full_address || shipment?.full_address || '-')}</strong></div>
    </div>
    <div class="portal-section" style="margin-top:14px"><div class="portal-section-head"><div><h2>Sản phẩm</h2></div></div>
      <div class="table-wrap"><table class="portal-table"><thead><tr><th>Mã sản phẩm</th><th>Số lượng</th><th>Đơn giá</th><th>Thành tiền</th></tr></thead><tbody>${safeList(order.items).map(item => `<tr><td>#${item.product_id}</td><td>${item.quantity}</td><td>${money(item.unit_price)}</td><td>${money(Number(item.unit_price) * Number(item.quantity))}</td></tr>`).join('')}</tbody></table></div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px">
      ${payment ? `<button class="portal-btn" type="button" onclick="Portal.editPayment(${order.id}, '${esc(payment.overall_status)}')">${icon('credit-card')} Cập nhật thanh toán</button>` : ''}
      ${order.current_status === 'pending' ? `<button class="portal-btn success" type="button" onclick="Portal.advanceOrder(${order.id}, 'paid')">${icon('circle-check')} Xác nhận đã thanh toán</button>` : ''}
      ${['pending','paid'].includes(order.current_status) ? `<button class="portal-btn danger" type="button" onclick="Portal.cancelOrder(${order.id})">${icon('ban')} Hủy đơn</button>` : ''}
      <a class="portal-btn" href="/orders/${order.id}/tracking/">${icon('external-link')} Mở theo dõi</a>
    </div>`;
    openModal({ title: `Đơn hàng #${order.id}`, eyebrow: 'Chi tiết vận hành', body, submitLabel: 'Đóng', onSubmit: async () => closeModal() });
  }

  function editPayment(orderId, current) {
    openModal({
      title: `Thanh toán đơn #${orderId}`,
      body: formGrid(field('Trạng thái', 'overall_status', current, { type: 'select', choices: ['pending','success','failed','refunded'] })),
      onSubmit: async data => {
        const payment = await api(`/api/payments/${orderId}/status/`, { method: 'PUT', body: { overall_status: data.get('overall_status') } });
        state.payments.set(Number(orderId), payment); toast('Đã cập nhật thanh toán'); renderOrders();
      }
    });
  }

  async function advanceOrder(orderId, nextStatus) {
    if (!confirm(`Chuyển đơn #${orderId} sang ${statusLabel(nextStatus)}?`)) return;
    try { await api(`/api/orders/${orderId}/status/`, { method: 'PUT', body: { status: nextStatus } }); toast('Đã cập nhật đơn hàng'); closeModal(); await loadOrders(); }
    catch (error) { toast(error.message, 'error'); }
  }

  async function cancelOrder(orderId) {
    if (!confirm(`Hủy đơn #${orderId}? Tồn kho và thanh toán sẽ được xử lý theo nghiệp vụ.`)) return;
    try { await api(`/api/orders/${orderId}/cancel/`, { method: 'PUT', body: {} }); toast('Đã hủy đơn hàng'); closeModal(); await loadOrders(); }
    catch (error) { toast(error.message, 'error'); }
  }

  async function loadShipping() {
    const node = document.getElementById('shippingTable'); node.innerHTML = loading();
    try { state.shipments = await all('/api/shipping/'); renderShipping(); }
    catch (error) { node.innerHTML = empty('Không tải được vận đơn', error.message); }
  }

  function renderShipping() {
    const filter = document.getElementById('shippingStatusFilter')?.value || '';
    const query = String(document.getElementById('shippingSearch')?.value || '').toLowerCase();
    const rows = state.shipments.filter(item => (!filter || item.current_status === filter) && (!query || `${item.order_id} ${item.receiver_name} ${item.phone} ${item.full_address}`.toLowerCase().includes(query)));
    document.getElementById('shippingTable').innerHTML = rows.length ? `<div class="table-wrap"><table class="portal-table"><thead><tr><th>Đơn</th><th>Người nhận</th><th>Địa chỉ</th><th>Trạng thái vận đơn</th><th>Cập nhật gần nhất</th><th>Thao tác</th></tr></thead><tbody>${rows.map(item => `<tr><td><strong>#${item.order_id}</strong></td><td><strong>${esc(item.receiver_name)}</strong><div class="muted">${esc(item.phone)}</div></td><td>${esc(item.full_address)}</td><td>${status(item.current_status)}</td><td>${esc(date(item.updated_at))}</td><td><div class="actions">${item.current_status === 'processing' ? `<button class="portal-btn success" onclick="Portal.advanceShipment(${item.order_id}, 'shipping')">${icon('truck')} Bắt đầu giao</button>` : ''}${item.current_status === 'shipping' ? `<button class="portal-btn success" onclick="Portal.advanceShipment(${item.order_id}, 'delivered')">${icon('package-check')} Xác nhận đã giao</button>` : ''}<button class="portal-btn" onclick="Portal.addTracking(${item.order_id}, '${esc(item.current_status)}')">${icon('map-pin-plus')} Thêm mốc</button>${item.current_status === 'processing' ? `<button class="portal-btn danger" onclick="Portal.deleteShipment(${item.order_id})">${icon('trash-2')}</button>` : ''}</div></td></tr>`).join('')}</tbody></table></div>` : empty('Không có vận đơn phù hợp');
    refreshIcons();
  }

  function addTracking(orderId, currentStatus) {
    openModal({ title: `Thêm mốc vận chuyển đơn #${orderId}`, body: formGrid(
      field('Trạng thái mốc', 'status', currentStatus, { type: 'select', choices: ['processing','shipping','delivered','cancelled'] }),
      field('Vị trí', 'location', '', { full: true, placeholder: 'Ví dụ: Trung tâm phân loại Hà Nội' })
    ), onSubmit: async data => { await api(`/api/shipping/${orderId}/tracking/`, { method: 'POST', body: { status: data.get('status'), location: data.get('location') } }); toast('Đã thêm mốc vận chuyển'); await loadShipping(); } });
  }

  async function advanceShipment(orderId, nextStatus) {
    if (!confirm(`Cập nhật vận đơn #${orderId} sang ${statusLabel(nextStatus)}?`)) return;
    try { await api(`/api/shipping/${orderId}/status/`, { method: 'PUT', body: { current_status: nextStatus, location: document.getElementById('shippingLocation')?.value || 'Kho ShopSphere' } }); toast('Đã cập nhật vận chuyển'); await loadShipping(); }
    catch (error) { toast(error.message, 'error'); }
  }

  async function deleteShipment(orderId) {
    if (!confirm(`Hủy vận đơn của đơn #${orderId}?`)) return;
    try { await api(`/api/shipping/${orderId}/delete/`, { method: 'DELETE', headers: auth(false) }); toast('Đã hủy vận đơn'); await loadShipping(); }
    catch (error) { toast(error.message, 'error'); }
  }

  async function loadReviews() {
    const node = document.getElementById('reviewsTable'); node.innerHTML = loading();
    try { state.reviews = await all('/api/reviews/'); renderReviews(); }
    catch (error) { node.innerHTML = empty('Không tải được đánh giá', error.message); }
  }

  function renderReviews() {
    const filter = document.getElementById('reviewStatusFilter')?.value || '';
    const query = String(document.getElementById('reviewSearch')?.value || '').toLowerCase();
    const rows = state.reviews.filter(item => (!filter || item.status === filter) && (!query || `${item.id} ${item.order_id} ${item.product_id} ${item.comment}`.toLowerCase().includes(query)));
    document.getElementById('reviewsTable').innerHTML = rows.length ? `<div class="table-wrap"><table class="portal-table"><thead><tr><th>Đánh giá</th><th>Đơn / sản phẩm</th><th>Số sao</th><th>Nội dung</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${rows.map(item => `<tr><td><strong>#${item.id}</strong><div class="muted">${esc(date(item.created_at))}</div></td><td>Đơn #${item.order_id}<div class="muted">Sản phẩm #${item.product_id}</div></td><td><strong>${item.rating}/5</strong></td><td>${esc(item.comment || 'Không có nội dung')} ${safeList(item.replies).length ? `<div class="muted">Phản hồi: ${esc(safeList(item.replies)[0].content)}</div>` : ''}</td><td>${status(item.status)}</td><td><div class="actions"><button class="portal-btn" onclick="Portal.replyReview(${item.id})">${icon('reply')} Phản hồi</button>${item.status !== 'approved' ? `<button class="portal-btn success" onclick="Portal.setReviewStatus(${item.id}, 'approved')">Duyệt</button>` : ''}${item.status !== 'rejected' ? `<button class="portal-btn" onclick="Portal.setReviewStatus(${item.id}, 'rejected')">Từ chối</button>` : ''}<button class="portal-btn danger" onclick="Portal.deleteReview(${item.id})">${icon('trash-2')}</button></div></td></tr>`).join('')}</tbody></table></div>` : empty('Không có đánh giá phù hợp');
    refreshIcons();
  }

  function replyReview(reviewId) {
    openModal({ title: `Phản hồi đánh giá #${reviewId}`, body: formGrid(field('Nội dung phản hồi', 'content', '', { type: 'textarea', full: true })), onSubmit: async data => { await api(`/api/reviews/${reviewId}/reply/`, { method: 'POST', body: { content: data.get('content') } }); toast('Đã gửi phản hồi từ cửa hàng'); await loadReviews(); } });
  }

  async function setReviewStatus(reviewId, nextStatus) {
    try { await api(`/api/reviews/${reviewId}/`, { method: 'PATCH', body: { status: nextStatus } }); toast('Đã cập nhật đánh giá'); await loadReviews(); }
    catch (error) { toast(error.message, 'error'); }
  }

  async function deleteReview(reviewId) {
    if (!confirm(`Xóa đánh giá #${reviewId}?`)) return;
    try { await api(`/api/reviews/${reviewId}/`, { method: 'DELETE', headers: auth(false) }); toast('Đã xóa đánh giá'); await loadReviews(); }
    catch (error) { toast(error.message, 'error'); }
  }

  async function loadNotifications() {
    const node = document.getElementById('notificationsTable'); node.innerHTML = loading();
    try { state.notifications = await all('/api/notifications/?scope=manage'); renderNotifications(); }
    catch (error) { node.innerHTML = empty('Không tải được thông báo', error.message); }
  }

  function renderNotifications() {
    const filter = document.getElementById('notificationTypeFilter')?.value || '';
    const query = String(document.getElementById('notificationSearch')?.value || '').toLowerCase();
    const rows = state.notifications.filter(item => (!filter || item.type === filter) && (!query || `${item.title} ${item.content} ${item.user_id || ''}`.toLowerCase().includes(query)));
    document.getElementById('notificationsTable').innerHTML = rows.length ? `<div class="table-wrap"><table class="portal-table"><thead><tr><th>ID</th><th>Người nhận</th><th>Loại</th><th>Nội dung</th><th>Ưu tiên</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${rows.map(item => `<tr><td>#${item.id}</td><td>${esc(item.recipient_type)}${item.user_id ? `<div class="muted">User #${item.user_id}</div>` : ''}</td><td>${esc(statusLabel(item.type))}</td><td><strong>${esc(item.title)}</strong><div class="muted">${esc(item.content)}</div></td><td>${esc(item.priority)}</td><td>${status(item.status)}</td><td><div class="actions"><button class="portal-btn" onclick="Portal.openNotificationForm(${item.id})">${icon('pencil')} Sửa</button><button class="portal-btn danger" onclick="Portal.deleteNotification(${item.id})">${icon('trash-2')}</button></div></td></tr>`).join('')}</tbody></table></div>` : empty('Không có thông báo phù hợp');
    refreshIcons();
  }

  function notificationForm(item = {}) {
    openModal({
      title: item.id ? `Sửa thông báo #${item.id}` : 'Tạo thông báo vận hành',
      body: formGrid(
        field('Người nhận', 'recipient_type', item.recipient_type || 'customer', { type: 'select', choices: [
          { value: 'customer', label: 'Một khách hàng' },
          { value: 'staff', label: 'Nhân viên' },
          { value: 'manager', label: 'Quản lý' },
          { value: 'admin', label: 'Quản trị viên' },
          { value: 'all', label: 'Tất cả người dùng' }
        ] }),
        field('Mã khách hàng', 'user_id', item.user_id || '', { type: 'number', required: false }),
        field('Loại', 'type', item.type || 'system', { type: 'select', choices: [
          { value: 'system', label: 'Thông báo chung' },
          { value: 'order', label: 'Đơn hàng' },
          { value: 'payment', label: 'Thanh toán' },
          { value: 'shipping', label: 'Vận chuyển' },
          { value: 'review', label: 'Đánh giá' }
        ] }),
        field('Ưu tiên', 'priority', item.priority || 'normal', { type: 'select', choices: [
          { value: 'low', label: 'Thấp' },
          { value: 'normal', label: 'Bình thường' },
          { value: 'high', label: 'Cao' }
        ] }),
        field('Tiêu đề', 'title', item.title || '', { full: true }),
        field('Nội dung', 'content', item.content || '', { type: 'textarea', full: true })
      ),
      submitLabel: item.id ? 'Cập nhật' : 'Gửi thông báo',
      onSubmit: async data => {
        const payload = Object.fromEntries(data.entries());
        if (!payload.user_id) delete payload.user_id; else payload.user_id = Number(payload.user_id);
        if (item.id) await api(`/api/notifications/${item.id}/manage/`, { method: 'PATCH', body: payload });
        else await api('/api/notifications/create/', { method: 'POST', body: payload });
        toast(item.id ? 'Đã cập nhật thông báo' : 'Đã gửi thông báo'); await loadNotifications();
      }
    });
  }

  function openNotificationForm(id = null) {
    notificationForm(id ? state.notifications.find(item => Number(item.id) === Number(id)) || {} : {});
  }

  async function deleteNotification(id) {
    if (!confirm(`Xóa thông báo #${id}?`)) return;
    try { await api(`/api/notifications/${id}/manage/`, { method: 'DELETE', headers: auth(false) }); toast('Đã xóa thông báo'); await loadNotifications(); }
    catch (error) { toast(error.message, 'error'); }
  }

  async function markAllNotificationsRead() {
    try { await api('/api/notifications/read-all/', { method: 'PUT', body: {} }); toast('Đã đánh dấu tất cả là đã đọc'); await loadNotifications(); }
    catch (error) { toast(error.message, 'error'); }
  }

  async function loadUsersRoles() {
    document.getElementById('usersTable').innerHTML = loading();
    try { [state.users, state.roles] = await Promise.all([all('/api/users/'), all('/api/roles/')]); renderUsers(); renderRoles(); }
    catch (error) { document.getElementById('usersTable').innerHTML = empty('Không tải được người dùng', error.message); }
  }

  function renderUsers() {
    const query = String(document.getElementById('userSearch')?.value || '').toLowerCase();
    const role = document.getElementById('userRoleFilter')?.value || '';
    const rows = state.users.filter(item => (!role || item.role_name === role) && (!query || `${item.username} ${item.email} ${item.phone || ''} ${item.first_name} ${item.last_name}`.toLowerCase().includes(query)));
    document.getElementById('usersTable').innerHTML = rows.length ? `<div class="table-wrap"><table class="portal-table"><thead><tr><th>Tài khoản</th><th>Họ tên</th><th>Liên hệ</th><th>Vai trò</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${rows.map(item => `<tr><td><strong>${esc(item.username)}</strong><div class="muted">#${item.id}</div></td><td>${esc(`${item.first_name || ''} ${item.last_name || ''}`.trim() || '-')}</td><td>${esc(item.email)}<div class="muted">${esc(item.phone || '-')}</div></td><td>${esc(item.role_name || '-')}</td><td>${status(item.is_active ? 'active' : 'inactive')}</td><td><div class="actions"><button class="portal-btn" onclick="Portal.openUserForm(${item.id})">${icon('pencil')} Sửa</button><button class="portal-btn danger" onclick="Portal.deleteUser(${item.id})">${icon('trash-2')}</button></div></td></tr>`).join('')}</tbody></table></div>` : empty('Không có người dùng phù hợp');
    const roleFilter = document.getElementById('userRoleFilter');
    if (roleFilter && roleFilter.options.length <= 1) roleFilter.innerHTML += state.roles.map(item => `<option value="${esc(item.role_name)}">${esc(item.role_name)}</option>`).join('');
    refreshIcons();
  }

  function renderRoles() {
    document.getElementById('rolesList').innerHTML = state.roles.length ? state.roles.map(item => `<div class="catalog-item"><div class="catalog-item-head"><div><h3>${esc(item.role_name)}</h3><div class="muted">Mã vai trò #${item.id}</div></div>${icon('shield')}</div><div class="catalog-item-actions"><button class="portal-btn" onclick="Portal.openRoleForm(${item.id})">Sửa</button><button class="portal-btn danger" onclick="Portal.deleteRole(${item.id})">Xóa</button></div></div>`).join('') : empty('Chưa có vai trò');
    refreshIcons();
  }

  function openUserForm(id = null) {
    const item = id ? state.users.find(row => Number(row.id) === Number(id)) : {};
    openModal({ title: id ? `Sửa người dùng #${id}` : 'Tạo người dùng', body: formGrid(
      field('Tên đăng nhập', 'username', item?.username || ''),
      field('Email', 'email', item?.email || '', { type: 'email' }),
      field('Họ', 'first_name', item?.first_name || '', { required: false }),
      field('Tên', 'last_name', item?.last_name || '', { required: false }),
      field('Điện thoại', 'phone', item?.phone || '', { required: false }),
      field('Vai trò', 'role', item?.role || state.roles[0]?.id || '', { type: 'select', choices: state.roles.map(role => ({ value: role.id, label: role.role_name })) }),
      field('Trạng thái', 'is_active', String(item?.is_active ?? true), { type: 'select', choices: [{value:'true',label:'Đang hoạt động'},{value:'false',label:'Ngừng hoạt động'}] }),
      field(id ? 'Mật khẩu mới (để trống nếu giữ nguyên)' : 'Mật khẩu', 'password', '', { type: 'password', required: !id })
    ), onSubmit: async data => {
      const payload = Object.fromEntries(data.entries()); payload.role = Number(payload.role); payload.is_active = payload.is_active === 'true'; if (!payload.password) delete payload.password;
      await api(id ? `/api/users/${id}/` : '/api/users/', { method: id ? 'PATCH' : 'POST', body: payload }); toast(id ? 'Đã cập nhật người dùng' : 'Đã tạo người dùng'); await loadUsersRoles();
    } });
  }

  async function deleteUser(id) { if (!confirm(`Xóa người dùng #${id}?`)) return; try { await api(`/api/users/${id}/`, { method:'DELETE', headers:auth(false) }); toast('Đã xóa người dùng'); await loadUsersRoles(); } catch(error){ toast(error.message,'error'); } }
  function openRoleForm(id = null) { const item = id ? state.roles.find(row => Number(row.id) === Number(id)) : {}; openModal({ title: id ? 'Sửa vai trò' : 'Tạo vai trò', body: formGrid(field('Tên vai trò','role_name',item?.role_name||'',{full:true})), onSubmit: async data => { await api(id ? `/api/roles/${id}/` : '/api/roles/', { method:id?'PATCH':'POST', body:{role_name:data.get('role_name')} }); toast('Đã lưu vai trò'); await loadUsersRoles(); } }); }
  async function deleteRole(id) { if(!confirm('Xóa vai trò này?')) return; try{ await api(`/api/roles/${id}/`,{method:'DELETE',headers:auth(false)}); toast('Đã xóa vai trò'); await loadUsersRoles(); }catch(error){toast(error.message,'error');} }

  async function loadCatalog() {
    document.getElementById('catalogContent').innerHTML = loading();
    try { [state.domains, state.categories, state.products] = await Promise.all([all('/api/domains/'), all('/api/categories/'), all('/api/products/?status=')]); renderCatalog(); }
    catch(error){ document.getElementById('catalogContent').innerHTML = empty('Không tải được dữ liệu sản phẩm',error.message); }
  }

  function setCatalogTab(tab) { document.querySelectorAll('.portal-tab').forEach(node=>node.classList.toggle('active',node.dataset.tab===tab)); document.body.dataset.catalogTab=tab; renderCatalog(); }
  function renderCatalog() {
    const tab = document.body.dataset.catalogTab || 'products';
    const query = String(document.getElementById('catalogSearch')?.value || '').toLowerCase();
    let html = '';
    if(tab==='domains') html = state.domains.filter(item=>!query||`${item.name} ${item.description||''}`.toLowerCase().includes(query)).map(item=>`<div class="catalog-item"><div class="catalog-item-head"><div><h3>${esc(item.name)}</h3><div class="muted">#${item.id}</div></div>${icon('layers-3')}</div><p>${esc(item.description||'Chưa có mô tả')}</p><div class="catalog-item-actions"><button class="portal-btn" onclick="Portal.openDomainForm(${item.id})">Sửa</button><button class="portal-btn danger" onclick="Portal.deleteDomain(${item.id})">Xóa</button></div></div>`).join('');
    else if(tab==='categories') html = state.categories.filter(item=>!query||`${item.name} ${item.domain_name} ${item.description||''}`.toLowerCase().includes(query)).map(item=>`<div class="catalog-item"><div class="catalog-item-head"><div><h3>${esc(item.name)}</h3><div class="muted">${esc(item.domain_name)}</div></div>${icon('tags')}</div><p>${esc(item.description||'Chưa có mô tả')}</p><div class="catalog-item-actions"><button class="portal-btn" onclick="Portal.openCategoryForm(${item.id})">Sửa</button><button class="portal-btn danger" onclick="Portal.deleteCategory(${item.id})">Xóa</button></div></div>`).join('');
    else html = `<div class="table-wrap"><table class="portal-table"><thead><tr><th>Sản phẩm</th><th>SKU</th><th>Danh mục</th><th>Giá</th><th>Tồn kho</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${state.products.filter(item=>!query||`${item.name} ${item.sku} ${item.category_name} ${item.domain_name}`.toLowerCase().includes(query)).map(item=>{const primary=esc(ShopUI.imageFor(item));const fallback=esc(ShopUI.fallbackImage(item));return `<tr><td><div class="inline-product"><img class="product-thumb" src="${primary}" data-fallback-src="${fallback}" onerror="this.onerror=null;this.src=this.dataset.fallbackSrc||ShopUI.fallbackImage()"><div><strong>${esc(item.name)}</strong><div class="muted">#${item.id}</div></div></div></td><td class="portal-code">${esc(item.sku)}</td><td>${esc(item.category_name)}<div class="muted">${esc(item.domain_name)}</div></td><td>${money(item.price)}</td><td>${item.stock}</td><td>${status(item.status)}</td><td><div class="actions"><button class="portal-btn" onclick="Portal.openProductForm(${item.id})">${icon('pencil')} Sửa</button><button class="portal-btn danger" onclick="Portal.deleteProduct(${item.id})">Ngưng bán</button></div></td></tr>`;}).join('')}</tbody></table></div>`;
    document.getElementById('catalogContent').innerHTML = html || empty('Chưa có dữ liệu sản phẩm'); refreshIcons();
  }

  function openDomainForm(id=null){ const item=id?state.domains.find(row=>Number(row.id)===Number(id)):{}; openModal({title:id?'Sửa ngành hàng':'Tạo ngành hàng',body:formGrid(field('Tên','name',item?.name||''),field('Mô tả','description',item?.description||'',{type:'textarea',full:true,required:false})),onSubmit:async data=>{await api(id?`/api/domains/${id}/`:'/api/domains/',{method:id?'PATCH':'POST',body:Object.fromEntries(data.entries())});toast('Đã lưu ngành hàng');await loadCatalog();}});}
  async function deleteDomain(id){if(!confirm('Xóa ngành hàng này? Chỉ xóa được khi không còn danh mục.'))return;try{await api(`/api/domains/${id}/`,{method:'DELETE',headers:auth(false)});toast('Đã xóa ngành hàng');await loadCatalog();}catch(error){toast(error.message,'error');}}
  function openCategoryForm(id=null){const item=id?state.categories.find(row=>Number(row.id)===Number(id)):{};openModal({title:id?'Sửa danh mục':'Tạo danh mục',body:formGrid(field('Tên','name',item?.name||''),field('Ngành hàng','domain_id',item?.domain_id||state.domains[0]?.id||'',{type:'select',choices:state.domains.map(row=>({value:row.id,label:row.name}))}),field('Mô tả','description',item?.description||'',{type:'textarea',full:true,required:false})),onSubmit:async data=>{const payload=Object.fromEntries(data.entries());payload.domain_id=Number(payload.domain_id);await api(id?`/api/categories/${id}/`:'/api/categories/',{method:id?'PATCH':'POST',body:payload});toast('Đã lưu danh mục');await loadCatalog();}});}
  async function deleteCategory(id){if(!confirm('Xóa danh mục này? Chỉ xóa được khi không còn sản phẩm.'))return;try{await api(`/api/categories/${id}/`,{method:'DELETE',headers:auth(false)});toast('Đã xóa danh mục');await loadCatalog();}catch(error){toast(error.message,'error');}}
  function openProductForm(id=null){const item=id?state.products.find(row=>Number(row.id)===Number(id)):{};openModal({title:id?`Sửa sản phẩm #${id}`:'Tạo sản phẩm',body:formGrid(field('Tên sản phẩm','name',item?.name||''),field('SKU','sku',item?.sku||''),field('Danh mục','category_id',item?.category_id||state.categories[0]?.id||'',{type:'select',choices:state.categories.map(row=>({value:row.id,label:`${row.domain_name} / ${row.name}`}))}),field('Trạng thái','status',item?.status||'active',{type:'select',choices:['active','inactive']}),field('Giá','price',item?.price||'',{type:'number'}),field('Tồn kho','stock',item?.stock??0,{type:'number'}),currentProductImageField(item),field(id?'Thay ảnh từ máy tính':'Ảnh sản phẩm từ máy tính','image_file','',{type:'file',full:true,required:false,accept:'image/jpeg,image/png,image/webp'}),field('Mô tả','description',item?.description||'',{type:'textarea',full:true,required:false})),onSubmit:async data=>{const imageFile=data.get('image_file');if(!imageFile||!imageFile.name)data.delete('image_file');await apiForm(id?`/api/products/${id}/`:'/api/products/',data,id?'PATCH':'POST');toast('Đã lưu sản phẩm');await loadCatalog();}});}
  async function deleteProduct(id){if(!confirm('Ngưng bán sản phẩm này?'))return;try{await api(`/api/products/${id}/`,{method:'DELETE',headers:auth(false)});toast('Đã ngưng bán sản phẩm');await loadCatalog();}catch(error){toast(error.message,'error');}}

  async function initPage() {
    if (!roleAllowed()) return;
    const loaders = { dashboard:loadDashboard, orders:loadOrders, shipping:loadShipping, reviews:loadReviews, notifications:loadNotifications, users:loadUsersRoles, catalog:loadCatalog };
    if (loaders[page]) await loaders[page]();
  }

  function reloadPage(){initPage();}
  document.addEventListener('DOMContentLoaded', async()=>{setupShell();await initPage();});

  return { state, page, kind, esc, money, date, status, statusLabel, icon, refreshIcons, toast, empty, loading, api, all, openModal, closeModal, reloadPage,
    loadDashboard,loadOrders,renderOrders,openOrder,editPayment,advanceOrder,cancelOrder,
    loadShipping,renderShipping,advanceShipment,addTracking,deleteShipment,
    loadReviews,renderReviews,replyReview,setReviewStatus,deleteReview,
    loadNotifications,renderNotifications,openNotificationForm,deleteNotification,markAllNotificationsRead,
    loadUsersRoles,renderUsers,openUserForm,deleteUser,openRoleForm,deleteRole,
    loadCatalog,setCatalogTab,renderCatalog,openDomainForm,deleteDomain,openCategoryForm,deleteCategory,openProductForm,deleteProduct };
})();
