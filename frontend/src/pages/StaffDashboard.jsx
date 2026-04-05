import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useSearchParams } from 'react-router-dom';
import { Truck, PackageSearch, Clock, PackageCheck } from 'lucide-react';

export default function StaffDashboard() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'attendance';

  const [shiftStatus, setShiftStatus] = useState('off'); // 'off' | 'on'
  const [loading, setLoading] = useState(false);

  const toggleShift = () => {
    setLoading(true);
    setTimeout(() => {
      setShiftStatus(s => s === 'off' ? 'on' : 'off');
      setLoading(false);
    }, 600);
  };

  return (
    <div className="fade-in">
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#1E293B', marginBottom: '0.5rem' }}>Bảng Điểu Khiển Nhân Viên</h1>
        <p style={{ color: '#64748B' }}>Phiên đăng nhập hiện tại: <strong>{user?.username}</strong> - Nhóm Quyền: <span className="badge badge-primary">{user?.role}</span></p>
      </div>

      {activeTab === 'attendance' && (
         <div className="card" style={{ padding: '2rem' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
               <Clock size={20} className="text-primary" /> Điểm danh Ca làm việc
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '2rem', padding: '2rem', background: '#F8FAFC', borderRadius: '12px', border: '1px dashed #CBD5E1' }}>
               <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: shiftStatus === 'on' ? 'var(--success)' : '#64748B', marginBottom: '0.5rem' }}>
                     Trang thái: {shiftStatus === 'on' ? 'Đang trong ca' : 'Đã kết thúc ca'}
                  </div>
                  <p style={{ color: '#64748B' }}>Hệ thống Staff Service sẽ ghi nhận giờ vào ca của bạn bắt đầu từ thời điểm bạn chấm công.</p>
               </div>
               <button onClick={toggleShift} disabled={loading} className={`btn ${shiftStatus === 'on' ? 'btn-danger' : 'btn-primary'}`} style={{ padding: '1rem 2rem', fontSize: '1.1rem' }}>
                  {loading ? <span className="spin spin-sm"></span> : (shiftStatus === 'on' ? 'Kết thúc Ca' : 'Bắt đầu Ca làm')}
               </button>
            </div>
         </div>
      )}

      {activeTab === 'inventory' && (
         <div className="card" style={{ padding: '2rem' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
               <PackageSearch size={20} className="text-secondary" /> Quản lý Tồn Kho (Inventory)
            </h2>
            <p style={{ color: '#64748B', marginBottom: '1.5rem' }}>Dành riêng cho nhân sự kho bãi. Cập nhật số lượng sản phẩm vật lý trên hệ thống.</p>
            <table className="table">
               <thead>
                 <tr>
                    <th>Mã SKU</th>
                    <th>Tên Sách</th>
                    <th>Tồn Hiện Tại</th>
                    <th>Hành Động</th>
                 </tr>
               </thead>
               <tbody>
                 <tr>
                    <td>BK-1002</td>
                    <td style={{ fontWeight: 600 }}>Tâm Lý Học Tội Phạm</td>
                    <td><span className="badge badge-success">45</span></td>
                    <td><button className="btn btn-sm btn-outline">Nhập Kho</button></td>
                 </tr>
                 <tr>
                    <td>BK-1003</td>
                    <td style={{ fontWeight: 600 }}>Lập trình thuật toán cơ bản</td>
                    <td><span className="badge badge-warning">8</span></td>
                    <td><button className="btn btn-sm btn-outline">Nhập Kho</button></td>
                 </tr>
                 <tr>
                    <td>BK-1004</td>
                    <td style={{ fontWeight: 600 }}>Cây Cam Ngọt Của Tôi</td>
                    <td><span className="badge badge-danger">0</span></td>
                    <td><button className="btn btn-sm btn-outline">Nhập Kho</button></td>
                 </tr>
               </tbody>
            </table>
         </div>
      )}

      {activeTab === 'shipping' && (
         <div className="card" style={{ padding: '2rem' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
               <Truck size={20} style={{ color: 'var(--warning)' }} /> Trung Tâm Vận Chuyển
            </h2>
            <p style={{ color: '#64748B', marginBottom: '1.5rem' }}>Xác nhận điều phối xe lấy hàng và cập nhật hệ thống Ship Service.</p>
            <table className="table">
               <thead>
                 <tr>
                    <th>Mã Đơn (Order ID)</th>
                    <th>Địa Chỉ Nhận</th>
                    <th>Trạng Thái</th>
                    <th>Hành Lệnh</th>
                 </tr>
               </thead>
               <tbody>
                 <tr>
                    <td>#ORD-7719</td>
                    <td>123 Nguyễn Văn Linh, Đà Nẵng</td>
                    <td><span className="badge badge-secondary">Pending</span></td>
                    <td><button className="btn btn-sm btn-primary"><PackageCheck size={14}/> Dispatch</button></td>
                 </tr>
                 <tr>
                    <td>#ORD-7718</td>
                    <td>45 Lê Lợi, Q1, HC</td>
                    <td><span className="badge badge-warning">Shipped</span></td>
                    <td><button className="btn btn-sm btn-success">Đã Giao</button></td>
                 </tr>
               </tbody>
            </table>
         </div>
      )}
    </div>
  );
}
