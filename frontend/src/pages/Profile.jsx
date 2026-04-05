import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { apiFetch } from '../lib/api';
import { User, Shield, Package, Clock, Settings } from 'lucide-react';

export default function Profile() {
  const { user } = useAuth();
  const addToast = useToast();

  const [profile, setProfile] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: ''
  });
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) {
      fetchData();
    }
  }, [user]);

  const fetchData = async () => {
    setLoading(true);
    try {
      // 1. Fetch Profile
      const profRes = await apiFetch(`/customers/${user.service_user_id}/profile/`);
      if (profRes.ok) {
        const profData = await profRes.json();
        setProfile({
           first_name: profData.first_name || '',
           last_name: profData.last_name || '',
           email: profData.email || '',
           password: '' // never populate password back
        });
      }

      // 2. Fetch Orders
      const ordRes = await apiFetch(`/orders/by_customer/?customer_id=${user.service_user_id}`);
      if (ordRes.ok) {
        const ordData = await ordRes.json();
        setOrders(Array.isArray(ordData) ? ordData : (ordData?.orders || []));
      }
    } catch(err) {
      addToast('Lỗi tải dữ liệu cá nhân', 'err');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
       const payload = { ...profile };
       if(!payload.password) { delete payload.password; } // don't send empty pwd
       
       const res = await apiFetch(`/customers/${user.service_user_id}/updateCustomer/`, {
          method: 'PATCH',
          body: JSON.stringify(payload)
       });
       
       if(res.ok) {
          addToast('Cập nhật hồ sơ thành công!', 'ok');
          setProfile({...profile, password: ''}); // clear pwd field
       } else {
          addToast('Cập nhật thất bại', 'err');
       }
    } catch(err) {
      addToast('Lỗi mạng', 'err');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (status) => {
     switch(status) {
        case 'pending': return 'var(--warning)';
        case 'paid': return 'var(--success)';
        case 'shipped': return 'var(--primary)';
        case 'canceled': return 'var(--danger)';
        default: return 'var(--text-3)';
     }
  };

  if(!user) return null;

  return (
    <div className="container page-section fade-in">
       <h1 style={{ fontSize: '2.2rem', fontWeight: 800, marginBottom: '3rem' }}>Quản Trị Cá Nhân</h1>

       {loading ? (
          <div style={{ textAlign: 'center', padding: '6rem' }}><div className="spin spin-lg"></div></div>
       ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4rem' }}>
             
             {/* 1. Phần Hồ Sơ */}
             <div className="card" style={{ padding: '2.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '1.5rem', marginBottom: '2rem' }}>
                   <div style={{ width: '48px', height: '48px', background: 'var(--primary-light)', color: 'var(--primary)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <User size={24}/>
                   </div>
                   <div>
                      <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>Thông Tin Hồ Sơ</h2>
                      <p style={{ color: 'var(--text-3)', fontSize: '0.9rem' }}>Cập nhật tên, email và thiết lập bảo mật của bạn</p>
                   </div>
                </div>

                <form onSubmit={handleUpdateProfile} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem' }}>
                   <div>
                      <label className="field-label">Tên</label>
                      <input type="text" className="input" value={profile.first_name} onChange={e=>setProfile({...profile, first_name: e.target.value})} placeholder="Nguyễn Văn" />
                   </div>
                   <div>
                      <label className="field-label">Họ</label>
                      <input type="text" className="input" value={profile.last_name} onChange={e=>setProfile({...profile, last_name: e.target.value})} placeholder="A" />
                   </div>
                   <div>
                      <label className="field-label">Địa chỉ Email</label>
                      <input type="email" className="input" value={profile.email} onChange={e=>setProfile({...profile, email: e.target.value})} placeholder="email@example.com" required/>
                   </div>
                   <div>
                      <label className="field-label">Mật khẩu mới (Để trống nếu không đổi)</label>
                      <input type="password" className="input" value={profile.password} onChange={e=>setProfile({...profile, password: e.target.value})} placeholder="••••••••" />
                   </div>

                   <div style={{ gridColumn: '1 / -1', marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <button type="submit" disabled={submitting} className="btn-primary" style={{ padding: '0.85rem 2rem', borderRadius: '8px' }}>
                         {submitting ? <span className="spin spin-sm"></span> : 'Lưu Thay Đổi'}
                      </button>
                      <span style={{ color: 'var(--text-4)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                         <Shield size={16}/> Được bảo mật bởi Zenith Auth
                      </span>
                   </div>
                </form>
             </div>

             {/* 2. Lịch sử Đơn Hàng */}
             <div className="card" style={{ padding: '2.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '1.5rem', marginBottom: '2rem' }}>
                   <div style={{ width: '48px', height: '48px', background: 'rgba(56, 189, 248, 0.1)', color: '#0284c7', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Package size={24}/>
                   </div>
                   <div>
                      <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>Lịch Sử Đơn Hàng</h2>
                      <p style={{ color: 'var(--text-3)', fontSize: '0.9rem' }}>Theo dõi các sách bạn đã đặt mua</p>
                   </div>
                </div>

                {orders.length === 0 ? (
                   <div style={{ padding: '3rem', textAlign: 'center', background: 'var(--surface-2)', borderRadius: 'var(--radius)' }}>
                      <Package size={48} color="var(--border)" style={{ marginBottom: '1rem' }}/>
                      <h3 style={{ color: 'var(--text-2)' }}>Chưa có đơn hàng nào</h3>
                      <p style={{ color: 'var(--text-4)' }}>Bạn chưa thực hiện giao dịch nào trên hệ thống.</p>
                   </div>
                ) : (
                   <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                         <thead>
                            <tr style={{ borderBottom: '2px solid var(--surface-2)', color: 'var(--text-3)' }}>
                               <th style={{ padding: '1rem 0' }}>Mã Đơn</th>
                               <th style={{ padding: '1rem 0' }}>Ngày đặt</th>
                               <th style={{ padding: '1rem 0' }}>Địa chỉ nhận</th>
                               <th style={{ padding: '1rem 0' }}>Tổng cộng</th>
                               <th style={{ padding: '1rem 0', textAlign: 'right' }}>Trạng thái</th>
                            </tr>
                         </thead>
                         <tbody>
                            {orders.map(order => (
                               <tr key={order.id} style={{ borderBottom: '1px solid var(--surface-2)' }}>
                                  <td style={{ padding: '1.25rem 0', fontWeight: 700, color: 'var(--primary)' }}>#{order.id}</td>
                                  <td style={{ padding: '1.25rem 0', color: 'var(--text-2)' }}>
                                     <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                        <Clock size={14}/> {new Date(order.created_at).toLocaleDateString('vi-VN')}
                                     </div>
                                  </td>
                                  <td style={{ padding: '1.25rem 0', color: 'var(--text-2)', maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                     {order.shipping_address || '—'}
                                  </td>
                                  <td style={{ padding: '1.25rem 0', fontWeight: 700 }}>
                                     {Number(order.total_amount).toLocaleString()} ₫
                                  </td>
                                  <td style={{ padding: '1.25rem 0', textAlign: 'right' }}>
                                     <span style={{ padding: '0.4rem 0.8rem', borderRadius: '30px', fontSize: '0.8rem', fontWeight: 700, background: 'var(--surface-2)', color: getStatusColor(order.status) }}>
                                        {order.status.toUpperCase()}
                                     </span>
                                  </td>
                               </tr>
                            ))}
                         </tbody>
                      </table>
                   </div>
                )}
             </div>

          </div>
       )}
    </div>
  );
}
