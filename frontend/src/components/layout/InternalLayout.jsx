import { Outlet, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Users, Box, Truck, BarChart3, Settings, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function InternalLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const role = user?.role || 'staff';

  const menuItems = [
    { name: 'Dashboard Tổng', path: '/manager', roles: ['manager'], icon: <LayoutDashboard size={20} /> },
    { name: 'Điểm danh & Ca làm', path: '/staff', roles: ['staff', 'manager'], icon: <Users size={20} /> },
    { name: 'Quản lý Kho', path: '/staff?tab=inventory', roles: ['staff', 'manager'], icon: <Box size={20} /> },
    { name: 'Trung tâm Vận chuyển', path: '/staff?tab=shipping', roles: ['staff', 'manager'], icon: <Truck size={20} /> },
    { name: 'Báo cáo Hệ thống', path: '/manager?tab=reports', roles: ['manager'], icon: <BarChart3 size={20} /> },
    { name: 'Cài đặt Cổng API', path: '/manager?tab=settings', roles: ['manager'], icon: <Settings size={20} /> },
  ];

  // Lọc menu theo role
  const allowedMenuItems = menuItems.filter(i => i.roles.includes(role));

  return (
    <div className="dashboard-layout" style={{ minHeight: '100vh' }}>
      {/* Sidebar */}
      <div className="sidebar" style={{ minHeight: '100vh', background: '#0F172A', color: '#CBD5E1', borderRight: 'none' }}>
        <div style={{ padding: '1.5rem', marginBottom: '1rem', borderBottom: '1px solid #1E293B' }}>
          <Link to="/" style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff' }}>
             Zenith<span style={{ color: 'var(--primary)' }}>Internal</span>
          </Link>
          <div style={{ fontSize: '0.8rem', color: '#94A3B8', marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
             <span style={{ display: 'inline-block', width: '8px', height: '8px', background: 'var(--success)', borderRadius: '50%' }}></span>
             {user?.username || 'Admin'} ({role})
          </div>
        </div>

        <div className="sidebar-section" style={{ color: '#475569' }}>Menu Quản Lộ</div>
        {allowedMenuItems.map((item, idx) => {
          const isActive = location.pathname === item.path || location.search.includes(item.path.split('?')[1]);
          return (
            <Link key={idx} to={item.path} className={`sidebar-item ${isActive ? 'active' : ''}`} style={{ color: isActive ? '#fff' : '#CBD5E1', background: isActive ? 'rgba(124, 58, 237, 0.15)' : 'transparent', borderLeftColor: isActive ? 'var(--primary)' : 'transparent' }}>
              {item.icon} {item.name}
            </Link>
          );
        })}

        <div style={{ marginTop: 'auto', padding: '1.5rem', borderTop: '1px solid #1E293B' }}>
          <button onClick={logout} className="btn w-100" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#F87171', border: '1px solid currentColor', width: '100%' }}>
            <LogOut size={18} /> Thoát hệ thống
          </button>
        </div>
      </div>

      {/* Main Content Dashboard */}
      <div className="dash-content" style={{ background: '#F1F5F9' }}>
         <Outlet />
      </div>
    </div>
  );
}
