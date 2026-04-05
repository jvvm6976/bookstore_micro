import { LineChart, LayoutTemplate, AlertTriangle, Users, BookOpen } from 'lucide-react';

export default function ManagerDashboard() {
  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '2rem' }}>
        <div>
           <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#1E293B', marginBottom: '0.5rem' }}>Trung Tâm Quyết Định (Executive Dashboard)</h1>
           <p style={{ color: '#64748B' }}>Dữ liệu tổng hợp từ 6 microservices backend.</p>
        </div>
        <button className="btn btn-primary"><LineChart size={18}/> Xuất Báo Cáo Tuần</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
        <div className="stat-card">
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
             <div>
               <div className="stat-label">Tổng Doanh Thu Phút</div>
               <div className="stat-value text-gradient">24.5M ₫</div>
             </div>
             <div className="stat-icon" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}>
               <LayoutTemplate size={24}/>
             </div>
           </div>
           <div className="stat-change" style={{ color: 'var(--success)' }}>+14.2% so với tháng trước</div>
        </div>

        <div className="stat-card">
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
             <div>
               <div className="stat-label">Đơn Hàng Đang Xử Lý</div>
               <div className="stat-value">128</div>
             </div>
             <div className="stat-icon" style={{ background: '#E0F2FE', color: '#0284C7' }}>
               <BookOpen size={24}/>
             </div>
           </div>
           <div className="stat-change" style={{ color: 'var(--text-3)' }}>Tải hệ thống bình thường</div>
        </div>

        <div className="stat-card" style={{ borderColor: 'var(--danger)', background: '#FEF2F2' }}>
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
             <div>
               <div className="stat-label" style={{ color: 'var(--danger)' }}>Báo Động Kho Hàng</div>
               <div className="stat-value" style={{ color: 'var(--danger)' }}>14</div>
             </div>
             <div className="stat-icon" style={{ background: '#FEE2E2', color: 'var(--danger)' }}>
               <AlertTriangle size={24}/>
             </div>
           </div>
           <div className="stat-change" style={{ color: 'var(--danger)' }}>Sản phẩm có tồn kho thấp (&lt;10)</div>
        </div>

        <div className="stat-card">
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
             <div>
               <div className="stat-label">Nhân Viên Trực Cấp</div>
               <div className="stat-value">8/12</div>
             </div>
             <div className="stat-icon" style={{ background: '#F3F4F6', color: '#4B5563' }}>
               <Users size={24}/>
             </div>
           </div>
           <div className="stat-change" style={{ color: 'var(--text-3)' }}>Khớp với lịch trình định kỳ</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
         <div className="card" style={{ padding: '2rem' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem' }}>Biểu Đồ Tương Tác Sách AI (Mock)</h2>
            <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFC', borderRadius: '12px', border: '1px dashed #CBD5E1', color: '#94A3B8' }}>
               [Biểu đồ Chart.js sẽ chèn tại đây] 
               Kênh Recommender-AI System API báo cáo lượng Impression.
            </div>
         </div>
         <div className="card" style={{ padding: '2rem' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem' }}>Log Hoạt Động (Audit)</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
               <div style={{ paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>
                 <div style={{ fontSize: '0.85rem', color: 'var(--text-4)' }}>14:32:01 - Staff Service</div>
                 <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Nhân viên NVA01 đã bắt đầu ca trực.</div>
               </div>
               <div style={{ paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>
                 <div style={{ fontSize: '0.85rem', color: 'var(--text-4)' }}>14:30:11 - Order Service</div>
                 <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Đơn hàng #ORD-7721 giá trị 1.2M hoàn tất.</div>
               </div>
               <div>
                 <div style={{ fontSize: '0.85rem', color: 'var(--text-4)' }}>14:28:44 - Inventory Service</div>
                 <div style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--danger)' }}>Cảnh báo sách BK-1002 thấp!</div>
               </div>
            </div>
         </div>
      </div>
    </div>
  );
}
