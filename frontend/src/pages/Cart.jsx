import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { apiFetch } from '../lib/api';
import { Link, useNavigate } from 'react-router-dom';
import { Trash2, ShieldCheck, ArrowRight } from 'lucide-react';

export default function Cart() {
  const { user } = useAuth();
  const { cartItems, refreshCart } = useCart();
  const addToast = useToast();
  const navigate = useNavigate();

  const total = cartItems.reduce((acc, i) => acc + (i.price * i.quantity), 0);

  const updateQuantity = async (bookId, newQty) => {
    if(newQty < 1) return;
    try {
      const res = await apiFetch(`/customers/${user.service_user_id}/updateCart/`, {
        method: 'POST',
        body: JSON.stringify({ book_id: bookId, quantity: newQty - (cartItems.find(x => x.book_id === bookId)?.quantity || 1) })
      });
      if(res.ok) {
        refreshCart();
      } else {
        addToast("Không thể cập nhật số lượng", "err");
      }
    } catch(e) { addToast("Lỗi kết nối mạng", "err"); }
  };

  const removeItem = async (bookId, currentQty) => {
    try {
       const res = await apiFetch(`/customers/${user.service_user_id}/updateCart/`, {
         method: 'POST',
         body: JSON.stringify({ book_id: bookId, quantity: -currentQty })
       });
       if(res.ok) {
          addToast("Đã xóa khỏi giỏ hàng", "ok");
          refreshCart();
       }
    } catch(e) { addToast("Lỗi xóa mặt hàng", "err"); }
  };

  if(!user) {
    return (
      <div className="container page-section" style={{ textAlign: 'center', padding: '6rem 2rem' }}>
        <h2 style={{ marginBottom: '1rem' }}>Vui lòng đăng nhập</h2>
        <p style={{ color: 'var(--text-3)', marginBottom: '2rem' }}>Giỏ hàng chỉ có thể được xem khi bạn đã xác thực với hệ thống.</p>
        <Link to="/customer-login" className="btn btn-primary">Tới trang Đăng Nhập</Link>
      </div>
    );
  }

  return (
    <div className="container page-section">
      <h1 style={{ fontSize: '2.2rem', fontWeight: 800, marginBottom: '2.5rem', letterSpacing: '-0.02em' }}>Giỏ hàng của bạn</h1>
      
      {cartItems.length === 0 ? (
        <div className="empty-state" style={{ background: 'var(--surface)', borderRadius: 'var(--radius-lg)', padding: '5rem 2rem', border: '1px dashed var(--border)' }}>
          <h3 style={{ fontSize: '1.4rem' }}>Chưa có gì trong giỏ</h3>
          <p style={{ marginBottom: '2rem' }}>Hãy tiếp tục mua sắm và lấp đầy giỏ sách yêu thích của bạn.</p>
          <Link to="/" className="btn btn-primary btn-pill">Bắt đầu mua sắm</Link>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '3rem', alignItems: 'start' }}>
          <div>
            <div style={{ background: 'var(--surface)', borderRadius: 'var(--radius-lg)', padding: '1rem', border: '1px solid var(--border)' }}>
              {cartItems.map(item => (
                <div key={item.id} style={{ display: 'flex', gap: '1.5rem', padding: '1.5rem', borderBottom: '1px solid var(--surface-2)' }}>
                  <img src={item.cover_image_url || 'https://via.placeholder.com/100x140'} alt={item.title} style={{ width: '100px', height: '140px', objectFit: 'cover', borderRadius: '8px', border: '1px solid var(--border)' }} />
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.2rem' }}>{item.title}</div>
                    <div style={{ color: 'var(--text-4)', fontSize: '0.9rem', marginBottom: '1rem' }}>Mã Sách: {item.book_id}</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--primary)', marginTop: 'auto' }}>
                       {Number(item.price).toLocaleString()} ₫
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', justifyContent: 'space-between' }}>
                    <button onClick={() => removeItem(item.book_id, item.quantity)} style={{ background: 'none', border: 'none', color: 'var(--text-4)', cursor: 'pointer', padding: '0.5rem', borderRadius: '50%', transition: '0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onMouseOver={e=>{e.currentTarget.style.color='var(--danger)'; e.currentTarget.style.background='var(--danger-light)'}} onMouseOut={e=>{e.currentTarget.style.color='var(--text-4)'; e.currentTarget.style.background='transparent'}}>
                      <Trash2 size={18} />
                    </button>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', border: '1px solid var(--border)', borderRadius: '30px', padding: '0.2rem 0.5rem' }}>
                       <button onClick={()=>updateQuantity(item.book_id, item.quantity - 1)} style={{ background: 'transparent', border:'none', fontSize: '1.2rem', cursor: 'pointer', padding: '0 0.5rem' }}>-</button>
                       <span style={{ fontWeight: 600, width: '20px', textAlign: 'center' }}>{item.quantity}</span>
                       <button onClick={()=>updateQuantity(item.book_id, item.quantity + 1)} style={{ background: 'transparent', border:'none', fontSize: '1.2rem', cursor: 'pointer', padding: '0 0.5rem' }}>+</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          <div style={{ background: 'var(--surface)', borderRadius: 'var(--radius-lg)', padding: '2rem', border: '1px solid var(--border)', position: 'sticky', top: '100px', boxShadow: 'var(--shadow-sm)' }}>
             <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>Tổng Quan Đơn Hàng</h3>
             <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem', color: 'var(--text-2)', fontSize: '0.95rem' }}>
                <span>Giá trị giỏ ({cartItems.length} sản phẩm)</span>
                <span>{total.toLocaleString()} ₫</span>
             </div>
             <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem', color: 'var(--text-2)', fontSize: '0.95rem' }}>
                <span>Phí vận chuyển</span>
                <span style={{ color: 'var(--success)', fontWeight: 600 }}>Miễn phí</span>
             </div>
             
             <div style={{ display: 'flex', justifyContent: 'space-between', padding: '1.5rem 0', borderTop: '2px dashed var(--border)', marginBottom: '1.5rem' }}>
                <span style={{ fontSize: '1.1rem', fontWeight: 800 }}>TỔNG THANH TOÁN</span>
                <span style={{ fontSize: '1.5rem', fontWeight: 900, color: 'var(--primary)' }}>{total.toLocaleString()} ₫</span>
             </div>
             
             <button onClick={()=>navigate('/checkout')} className="btn btn-primary" style={{ width: '100%', padding: '1rem', borderRadius: '12px', fontSize: '1.05rem', gap: '0.5rem' }}>
                Tiến Hành Thanh Toán <ArrowRight size={18} />
             </button>
             
             <div style={{ marginTop: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-4)', justifyContent: 'center' }}>
                <ShieldCheck size={16} /> Giao dịch được bảo mật và an toàn 100%
             </div>
          </div>
        </div>
      )}
    </div>
  );
}
