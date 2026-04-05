import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { ShoppingCart, Search, LogOut, LayoutDashboard, ShieldAlert } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';

const Navbar = () => {
  const { user, logout } = useAuth();
  const { cartCount } = useCart();
  const [search, setSearch] = useState('');
  const [dropdown, setDropdown] = useState(false);
  const navigate = useNavigate();

  const doSearch = (e) => {
    if (e.key === 'Enter' && search.trim()) {
      navigate('/catalog?search=' + encodeURIComponent(search.trim()));
      setSearch('');
    }
  };

  return (
    <nav style={{ position: 'sticky', top: 0, zIndex: 1000, background: 'var(--glass)', backdropFilter: 'blur(16px)', borderBottom: '1px solid rgba(255,255,255,0.4)', boxShadow: 'var(--shadow-sm)' }}>
      <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '76px' }}>
        <Link to="/" style={{ fontSize: '1.6rem', fontWeight: 800, letterSpacing: '-0.5px' }}>
          Zenith<span style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Reads</span>
        </Link>
        <div style={{ flex: 1, maxWidth: '500px', margin: '0 2rem', position: 'relative' }}>
          <input type="text" className="input" placeholder="Khám phá sách hay..." 
                 value={search} onChange={e => setSearch(e.target.value)} onKeyDown={doSearch}
                 style={{ borderRadius: '30px', paddingRight: '3rem' }}/>
          <button style={{ position: 'absolute', right: '0.5rem', top: '50%', transform: 'translateY(-50%)', background: 'var(--text-main)', color: '#fff', border: 'none', borderRadius: '50%', width: '36px', height: '36px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: '0.2s' }}
                  onMouseOver={e=>e.currentTarget.style.transform='translateY(-50%) scale(1.1)'} onMouseOut={e=>e.currentTarget.style.transform='translateY(-50%) scale(1)'}
                  onClick={() => search.trim() && navigate('/catalog?search='+encodeURIComponent(search.trim()))}>
            <Search size={18}/>
          </button>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {user ? (
            <>
              <Link to="/cart" style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '44px', height: '44px', background: '#F3F4F6', borderRadius: '50%', color: 'var(--text-main)', transition: '0.2s' }} onMouseOver={e=>e.currentTarget.style.background='#E5E7EB'} onMouseOut={e=>e.currentTarget.style.background='#F3F4F6'}>
                <ShoppingCart size={22} strokeWidth={1.5}/>
                <span style={{ position: 'absolute', top: '0px', right: '-4px', background: 'var(--primary)', color: '#fff', fontSize: '0.75rem', fontWeight: 800, minWidth: '20px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '10px', boxShadow: '0 2px 4px rgba(124,58,237,0.4)' }}>{cartCount}</span>
              </Link>
              <div style={{ position: 'relative' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', cursor: 'pointer', background: 'var(--surface)', border: '2px solid var(--border)', padding: '0.3rem 1.25rem 0.3rem 0.3rem', borderRadius: '30px', fontWeight: 700, transition: '0.2s' }}
                     onClick={() => setDropdown(!dropdown)} onMouseOver={e=>e.currentTarget.style.borderColor='var(--primary)'} onMouseOut={e=>e.currentTarget.style.borderColor='var(--border)'}>
                  <div style={{ width: '36px', height: '36px', background: 'linear-gradient(135deg, var(--primary), var(--secondary))', borderRadius: '50%', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1rem', fontWeight: 800 }}>
                    {(user.username||user.email||'U').charAt(0).toUpperCase()}
                  </div>
                  <span>{user.username || 'Khách'}</span>
                </div>
                {dropdown && (
                  <>
                    <div style={{position:'fixed', inset:0, zIndex:99}} onClick={()=>setDropdown(false)}></div>
                    <div className="fade-in" style={{ position: 'absolute', top: '120%', right: 0, width: '220px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '16px', boxShadow: 'var(--shadow-lg)', overflow: 'hidden', zIndex: 100 }}>
                      <Link to={`/profile`} onClick={()=>setDropdown(false)} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem 1.25rem', fontWeight: 600, borderBottom: '1px solid var(--border)', transition: '0.2s' }} onMouseOver={e=>e.currentTarget.style.background='#F9FAFB'} onMouseOut={e=>e.currentTarget.style.background='transparent'}>
                         Hồ sơ của tôi
                      </Link>
                      {['staff', 'manager'].includes(user.role) && (
                        <Link to={`/${user.role}`} onClick={()=>setDropdown(false)} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem 1.25rem', fontWeight: 600, borderBottom: '1px solid var(--border)', transition: '0.2s' }} onMouseOver={e=>e.currentTarget.style.background='#F9FAFB'} onMouseOut={e=>e.currentTarget.style.background='transparent'}>
                           <LayoutDashboard size={18} color="var(--primary)"/> Bảng hệ thống
                        </Link>
                      )}
                      <button onClick={()=>{logout();setDropdown(false);}} style={{ width: '100%', padding: '1rem 1.25rem', textAlign: 'left', background: 'none', border: 'none', color: 'var(--danger)', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.75rem', transition: '0.2s' }} onMouseOver={e=>e.currentTarget.style.background='#FEF2F2'} onMouseOut={e=>e.currentTarget.style.background='transparent'}>
                        <LogOut size={18}/> Đăng xuất
                      </button>
                    </div>
                  </>
                )}
              </div>
            </>
          ) : (
            <>
              <Link to="/customer-login" className="btn btn-outline" style={{ borderRadius: '30px' }}>Đăng nhập</Link>
              <Link to="/customer-login?tab=register" className="btn btn-primary" style={{ borderRadius: '30px' }}>Đăng ký ngay</Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};

const Footer = () => (
  <footer style={{ background: 'var(--text-1)', color: '#fff', padding: '5rem 0 2rem', marginTop: 'auto' }}>
    <div className="container">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '3rem', marginBottom: '4rem' }}>
        <div style={{ gridColumn: 'span 2' }}>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, marginBottom: '1rem', letterSpacing: '-0.5px' }}>Zenith<span style={{color:'var(--secondary)'}}>Reads</span></div>
          <p style={{ color: 'var(--text-4)', fontSize: '0.95rem', lineHeight: 1.7, maxWidth: '350px' }}>Hệ sinh thái phân phối tri thức với trải nghiệm nhà sách vi mô siêu mượt, dựa trên kiến trúc Microservices tối ưu nhất.</p>
        </div>
        <div>
           <h4 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '1.5rem', color: '#F3F4F6' }}>Khám phá</h4>
           <div style={{display:'flex', flexDirection:'column', gap:'1rem'}}>
             <Link to="/catalog?category=programming" style={{ color: 'var(--text-4)', transition: '0.2s' }} onMouseOver={e=>e.currentTarget.style.color='#fff'} onMouseOut={e=>e.currentTarget.style.color='var(--text-4)'}>Lập trình & Công nghệ</Link>
             <Link to="/catalog?category=science" style={{ color: 'var(--text-4)', transition: '0.2s' }} onMouseOver={e=>e.currentTarget.style.color='#fff'} onMouseOut={e=>e.currentTarget.style.color='var(--text-4)'}>Khoa học Phổ thông</Link>
             <Link to="/catalog?category=fiction" style={{ color: 'var(--text-4)', transition: '0.2s' }} onMouseOver={e=>e.currentTarget.style.color='#fff'} onMouseOut={e=>e.currentTarget.style.color='var(--text-4)'}>Văn học Cổ điển</Link>
           </div>
        </div>
        <div>
           <h4 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '1.5rem', color: '#F3F4F6' }}>Hệ thống</h4>
           <div style={{display:'flex', flexDirection:'column', gap:'1rem'}}>
             <Link to="/login" style={{ color: 'var(--text-4)', transition: '0.2s', display: 'flex', alignItems: 'center', gap: '0.5rem' }} onMouseOver={e=>e.currentTarget.style.color='#fff'} onMouseOut={e=>e.currentTarget.style.color='var(--text-4)'}><ShieldAlert size={16}/> Đăng nhập Nội bộ</Link>
           </div>
        </div>
      </div>
      <div style={{ paddingTop: '2rem', borderTop: '1px solid #374151', textAlign: 'center', color: 'var(--text-3)', fontSize: '0.9rem' }}>
        &copy; 2026 ZenithReads. Được phát triển để tuân thủ kiến trúc Microservices cấp độ cao.
      </div>
    </div>
  </footer>
);

export default function CustomerLayout() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-color)' }}>
      <Navbar />
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Nơi chứa Pages Khách hàng */}
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
