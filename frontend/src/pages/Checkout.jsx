import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { apiFetch } from '../lib/api';
import { MapPin, CreditCard, CheckCircle, ShieldCheck } from 'lucide-react';

export default function Checkout() {
  const { user } = useAuth();
  const { cartItems, refreshCart } = useCart();
  const addToast = useToast();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    shipping_address: '',
    payment_method: 'credit_card'
  });
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [savedAddresses, setSavedAddresses] = useState([]);
  const [useNewAddress, setUseNewAddress] = useState(false);

  useEffect(() => {
     if(user) {
        // Fetch past orders to extract previously used addresses
        apiFetch(`/orders/by_customer/?customer_id=${user.service_user_id}`)
         .then(res => res.json())
         .then(data => {
            const orders = Array.isArray(data) ? data : (data?.orders || []);
            if(orders.length > 0) {
               // Extract unique addresses and filter falsy ones
               const addrs = [...new Set(orders.map(o => o.shipping_address).filter(Boolean))];
               setSavedAddresses(addrs);
               if(addrs.length > 0) {
                  setForm(f => ({ ...f, shipping_address: addrs[0] }));
                  setUseNewAddress(false);
               } else {
                  setUseNewAddress(true);
               }
            } else {
               setUseNewAddress(true);
            }
         }).catch(()=>setUseNewAddress(true));
     }
  }, [user]);

  const total = cartItems.reduce((acc, i) => acc + ((i.price || 0) * i.quantity), 0);

  const handleCheckout = async (e) => {
    e.preventDefault();
    if (!user) { addToast('Vui lòng đăng nhập', 'err'); return; }
    if (cartItems.length === 0) { addToast('Giỏ hàng trống', 'err'); return; }

    setSubmitting(true);
    try {
      const payload = {
        customer_id: user.service_user_id,
        cart_id: user.cart_id,
        shipping_address: form.shipping_address,
        payment_method: form.payment_method
      };

      const res = await apiFetch(`/orders/checkout/`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      
      if (res.ok && data.success) {
        addToast('Đặt hàng thành công!', 'ok');
        refreshCart(); // clear logic automatically fetches emptiness if deleted on backend or we wait for Saga
        setSuccess(true);
      } else {
        addToast(data.message || data.error || 'Lỗi thanh toán', 'err');
      }
    } catch (err) {
      addToast('Lỗi kết nối khi thanh toán', 'err');
    } finally {
      setSubmitting(false);
    }
  };

  if(!user) {
    return (
       <div className="container page-section" style={{ textAlign: 'center', padding: '6rem 2rem' }}>
          <h2>Vui lòng đăng nhập để thanh toán</h2>
          <button onClick={()=>navigate('/customer-login')} className="btn-primary" style={{marginTop:'1rem'}}>Đăng nhập</button>
       </div>
    );
  }

  if (success) {
    return (
      <div className="container page-section fade-in" style={{ textAlign: 'center', padding: '6rem 2rem' }}>
         <CheckCircle size={80} color="var(--success)" style={{ marginBottom: '1.5rem' }} />
         <h1 style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '1rem' }}>Thanh toán Thành công!</h1>
         <p style={{ color: 'var(--text-3)', fontSize: '1.1rem', marginBottom: '2.5rem' }}>
            Cảm ơn bạn đã tin tưởng ZenithReads. Đơn hàng đang được hệ thống xử lý (Saga).
         </p>
         <button onClick={() => navigate('/')} className="btn-primary" style={{ padding: '0.85rem 1.5rem', borderRadius: '8px' }}>Tiếp tục mua sách</button>
      </div>
    );
  }

  if (cartItems.length === 0) {
    return (
       <div className="container page-section fade-in" style={{ textAlign: 'center', padding: '6rem 2rem' }}>
          <h2 style={{ marginBottom: '1rem' }}>Chưa có sản phẩm để thanh toán</h2>
          <button onClick={()=>navigate('/')} className="btn-primary" style={{marginTop:'1rem'}}>Khám phá thêm</button>
       </div>
    );
  }

  return (
    <div className="container page-section fade-in">
       <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '2rem' }}>Thanh Toán Xác Nhận</h1>

       <div style={{ display: 'grid', gridTemplateColumns: 'minmax(400px, 1fr) 380px', gap: '3rem', alignItems: 'start' }}>
          {/* Cột Form Thông tin */}
          <form onSubmit={handleCheckout} style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
             
             {/* Card Nhập địa chỉ */}
             <div className="card" style={{ padding: '2rem' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                   <MapPin size={20} color="var(--primary)"/> Địa chỉ giao hàng
                </h3>
                
                {savedAddresses.length > 0 && (
                   <div style={{ marginBottom: '1.5rem', display: 'flex', gap: '1rem' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                         <input type="radio" checked={!useNewAddress} onChange={() => { setUseNewAddress(false); setForm({...form, shipping_address: savedAddresses[0]}); }} />
                         Dùng địa chỉ đã lưu
                      </label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                         <input type="radio" checked={useNewAddress} onChange={() => { setUseNewAddress(true); setForm({...form, shipping_address: ''}); }} />
                         Nhập địa chỉ mới
                      </label>
                   </div>
                )}

                {!useNewAddress && savedAddresses.length > 0 ? (
                   <div>
                      <label className="field-label">Chọn địa chỉ của bạn</label>
                      <select className="input" value={form.shipping_address} onChange={(e) => setForm({...form, shipping_address: e.target.value})} required>
                         {savedAddresses.map((addr, idx) => (
                            <option key={idx} value={addr}>{addr}</option>
                         ))}
                      </select>
                   </div>
                ) : (
                   <div>
                      <label className="field-label">Địa chỉ nhà / Căn hộ</label>
                      <textarea className="textarea" rows="3" required placeholder="Nhập địa chỉ nhận hàng chi tiết..." value={form.shipping_address} onChange={(e) => setForm({...form, shipping_address: e.target.value})}></textarea>
                   </div>
                )}
             </div>

             {/* Card Tùy chọn thanh toán */}
             <div className="card" style={{ padding: '2rem' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                   <CreditCard size={20} color="var(--primary)"/> Hình thức thanh toán
                </h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                   <label style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem', border: '1px solid var(--border)', borderRadius: '8px', cursor: 'pointer', background: form.payment_method === 'credit_card' ? 'var(--primary-light)' : 'transparent', borderColor: form.payment_method === 'credit_card' ? 'var(--primary)' : 'var(--border)' }}>
                      <input type="radio" value="credit_card" checked={form.payment_method === 'credit_card'} onChange={(e)=>setForm({...form, payment_method: e.target.value})} name="payment" />
                      <span style={{ fontWeight: 600 }}>Thẻ Tín Dụng / Ghi Nợ (Credit Card)</span>
                   </label>
                   
                   <label style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem', border: '1px solid var(--border)', borderRadius: '8px', cursor: 'pointer', background: form.payment_method === 'cod' ? 'var(--primary-light)' : 'transparent', borderColor: form.payment_method === 'cod' ? 'var(--primary)' : 'var(--border)' }}>
                      <input type="radio" value="cod" checked={form.payment_method === 'cod'} onChange={(e)=>setForm({...form, payment_method: e.target.value})} name="payment" />
                      <span style={{ fontWeight: 600 }}>Thanh toán khi nhận hàng (COD)</span>
                   </label>
                </div>
             </div>

             <button type="submit" disabled={submitting} className="btn-primary" style={{ padding: '1.25rem', fontSize: '1.1rem', fontWeight: 700, borderRadius: '12px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
                {submitting ? <span className="spin spin-sm"></span> : 'Xác Nhận Đặt Hàng & Thanh Toán'}
             </button>
             
             <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', color: 'var(--success)', fontSize: '0.9rem', fontWeight: 600 }}>
                <ShieldCheck size={18}/> Mọi luồng giao dịch được mã hóa và trung chuyển bảo mật.
             </div>
          </form>

          {/* Cột Tổng quan Giỏ hàng (Bên phải) */}
          <div className="card" style={{ padding: '2rem', position: 'sticky', top: '100px' }}>
             <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>Tổng Quan</h3>
             
             <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
                {cartItems.map(item => (
                   <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.95rem' }}>
                      <div style={{ color: 'var(--text-3)', display: 'flex', gap: '0.5rem' }}>
                         <span style={{ fontWeight: 600, color: 'var(--text-1)' }}>{item.quantity}x</span>
                         <span style={{ maxWidth: '150px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.title}</span>
                      </div>
                      <div style={{ fontWeight: 600 }}>{(item.price * item.quantity).toLocaleString()} ₫</div>
                   </div>
                ))}
             </div>

             <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem', color: 'var(--text-2)' }}>
                <span>Giá trị giỏ</span>
                <span>{total.toLocaleString()} ₫</span>
             </div>
             <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem', color: 'var(--text-2)' }}>
                <span>Thuế & Phí giao hàng</span>
                <span style={{ color: 'var(--success)', fontWeight: 600 }}>Miễn phí</span>
             </div>
             
             <div style={{ display: 'flex', justifyContent: 'space-between', padding: '1.5rem 0 0', borderTop: '2px dashed var(--border)' }}>
                <span style={{ fontSize: '1.1rem', fontWeight: 800 }}>TỔNG THANH TOÁN</span>
                <span style={{ fontSize: '1.5rem', fontWeight: 900, color: 'var(--primary)' }}>{total.toLocaleString()} ₫</span>
             </div>
          </div>
       </div>
    </div>
  );
}
