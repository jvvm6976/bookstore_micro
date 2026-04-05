import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { apiFetch } from '../lib/api';
import { ShieldAlert } from 'lucide-react';

export default function LoginInternal() {
  const { user, login } = useAuth();
  const addToast = useToast();
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ username: '', password: '' });

  useEffect(() => {
    if (user && (user.role === 'staff' || user.role === 'manager' || user.role === 'admin')) {
      navigate(`/${user.role}`);
    }
  }, [user, navigate]);

  const doAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await apiFetch('/auth/login/', {
        method: 'POST', body: JSON.stringify(form)
      });
      const d = await r.json();
      
      if(r.ok && d.access_token) {
        if(d.user?.role === 'customer') {
          addToast('Quyền hạn quá thấp. Cổng này dành cho Quản trị viên.', 'err');
          return;
        }
        login({
          access_token: d.access_token,
          username: d.user.username,
          service_user_id: d.user.service_user_id,
          role: d.user.role
        });
        
        setTimeout(() => navigate(`/${d.user.role}`), 800);
      } else {
        addToast(d.error || 'Truy cập bị từ chối.', 'err');
      }
    } catch(err) {
      addToast('Lỗi kết nối máy chủ dữ liệu.', 'err');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: '#0F172A', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '3rem 1rem' }}>
      <div className="fade-in" style={{ width: '100%', maxWidth: '400px', padding: '3.5rem 2.5rem', borderRadius: 'var(--radius-lg)', background: '#1E293B', border: '1px solid #334155', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)' }}>
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(124,58,237,0.1)', color: 'var(--primary)', marginBottom: '1rem' }}>
             <ShieldAlert size={32} strokeWidth={1.5}/>
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em', marginBottom: '0.4rem' }}>
            Zenith<span style={{ color: 'var(--primary)' }}>Internal</span>
          </div>
          <div style={{ color: '#94A3B8', fontWeight: 500, fontSize: '0.8rem', letterSpacing: '0.1em' }}>HỆ THỐNG QUẢN LÝ TẬP TRUNG</div>
        </div>

        <form onSubmit={doAuth} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <label style={{ display: 'block', color: '#94A3B8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Mã nhân sự</label>
            <input type="text" style={{ padding: '0.85rem 1rem', borderRadius: '8px', border: '1px solid #334155', background: '#0F172A', width: '100%', fontSize: '0.95rem', outline: 'none', color: '#F8FAFC', transition: 'border-color 0.2s' }} required value={form.username} onChange={e=>setForm({...form, username: e.target.value})} placeholder="UID/Username" onFocus={e=>e.target.style.borderColor='var(--primary)'} onBlur={e=>e.target.style.borderColor='#334155'} />
          </div>
          <div>
            <label style={{ display: 'block', color: '#94A3B8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Mật khẩu bảo mật</label>
            <input type="password" style={{ padding: '0.85rem 1rem', borderRadius: '8px', border: '1px solid #334155', background: '#0F172A', width: '100%', fontSize: '0.95rem', outline: 'none', color: '#F8FAFC', transition: 'border-color 0.2s' }} required value={form.password} onChange={e=>setForm({...form, password: e.target.value})} placeholder="Passkey" onFocus={e=>e.target.style.borderColor='var(--primary)'} onBlur={e=>e.target.style.borderColor='#334155'} />
          </div>
          
          <button type="submit" disabled={loading} className="btn-primary" style={{ width: '100%', padding: '0.9rem', borderRadius: '8px', fontWeight: 600, fontSize: '0.95rem', border: 'none', cursor: 'pointer', marginTop: '1rem', transition: '0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
            {loading ? <span className="spin spin-sm"></span> : 'Xác Thực'}
          </button>
        </form>
      </div>
    </div>
  );
}
