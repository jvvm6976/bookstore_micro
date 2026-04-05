import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { apiFetch } from '../lib/api';

export default function LoginCustomer() {
  const { login } = useAuth();
  const addToast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isReg = searchParams.get('tab') === 'register';

  const [tab, setTab] = useState(isReg ? 'register' : 'login');
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ username: '', password: '', email: '' });

  const doAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const endpoint = tab === 'login' ? '/auth/login/' : '/auth/register/';
      const payload = { username: form.username, password: form.password };
      if (tab === 'register') {
        payload.email = form.email;
        payload.role = 'customer';
      }
      
      const r = await apiFetch(endpoint, {
        method: 'POST', 
        body: JSON.stringify(payload)
      });
      
      const d = await r.json();
      
      if(r.ok && d.access_token) {
        if(d.user?.role !== 'customer') {
          addToast('Tài khoản nội bộ. Vui lòng đăng nhập qua Internal Portal.', 'err');
          return;
        }
        login({
          access_token: d.access_token,
          username: d.user.username,
          service_user_id: d.user.service_user_id,
          cart_id: d.user.cart_id,
          role: d.user.role
        });
        setTimeout(() => navigate('/'), 800);
      } else {
        addToast(d.error || 'Thông tin đăng nhập không hợp lệ.', 'err');
      }
    } catch(err) {
      addToast('Lỗi kết nối máy chủ.', 'err');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', padding: '4rem 1rem' }}>
      <div className="card fade-in" style={{ width: '100%', maxWidth: '420px', padding: '2.5rem', borderRadius: 'var(--radius-xl)', border: '1px solid var(--border)', background: 'var(--glass)', backdropFilter: 'blur(20px)' }}>
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '0.5rem', color: 'var(--text-1)' }}>
            {tab === 'login' ? 'Đăng nhập vào ZenithReads' : 'Tạo tài khoản mới'}
          </h2>
          <p style={{ color: 'var(--text-3)', fontSize: '0.95rem' }}>
            {tab === 'login' ? 'Chào mừng bạn quay trở lại.' : 'Tham gia cộng đồng đọc sách hiện đại.'}
          </p>
        </div>

        <form onSubmit={doAuth} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
             <label className="field-label">Tên bộ gõ (Username)</label>
             <input type="text" className="input" required value={form.username} onChange={e=>setForm({...form, username: e.target.value})} placeholder="Nhập username" />
          </div>
          {tab === 'register' && (
            <div className="fade-in">
               <label className="field-label">Địa chỉ Email</label>
               <input type="email" className="input" required value={form.email} onChange={e=>setForm({...form, email: e.target.value})} placeholder="Nhập email" />
            </div>
          )}
          <div>
             <label className="field-label">Mật khẩu</label>
             <input type="password" className="input" required value={form.password} onChange={e=>setForm({...form, password: e.target.value})} placeholder="Nhập mật khẩu" />
          </div>
          
          <button type="submit" disabled={loading} className="btn btn-primary" style={{ width: '100%', padding: '0.9rem', marginTop: '1rem', borderRadius: '12px' }}>
            {loading ? <span className="spin spin-sm"></span> : (tab === 'login' ? 'Đăng Nhập' : 'Tạo Tài Khoản')}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '2rem', fontSize: '0.9rem', color: 'var(--text-3)' }}>
           {tab === 'login' ? (
             <>Thành viên mới? <span onClick={()=>setTab('register')} style={{color: 'var(--primary)', cursor:'pointer', fontWeight: 700, transition: 'var(--transition)'}} onMouseOver={e=>e.currentTarget.style.color='var(--primary-hover)'} onMouseOut={e=>e.currentTarget.style.color='var(--primary)'}>Tạo tài khoản</span></>
           ) : (
             <>Đã có tài khoản? <span onClick={()=>setTab('login')} style={{color: 'var(--primary)', cursor:'pointer', fontWeight: 700, transition: 'var(--transition)'}} onMouseOver={e=>e.currentTarget.style.color='var(--primary-hover)'} onMouseOut={e=>e.currentTarget.style.color='var(--primary)'}>Đăng nhập</span></>
           )}
        </div>
      </div>
    </div>
  );
}
