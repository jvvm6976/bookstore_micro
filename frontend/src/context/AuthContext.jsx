import { createContext, useContext, useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';
import { useToast } from './ToastContext';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const addToast = useToast();

  useEffect(() => {
    // Tự động nạp user từ localStorage khi mới load
    try {
      const u = JSON.parse(localStorage.getItem('cb_user'));
      if (u && u.access_token) {
        setUser(u);
      }
    } catch (e) {
      console.error('Invalid user schema in storage.');
    }

    // Lắng nghe window event khi token bị 401
    const handleUnauthorized = () => {
      setUser(null);
      addToast('Phiên làm việc hết hạn, vui lòng đăng nhập lại.', 'err');
      window.location.href = '/customer-login';
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [addToast]);

  const login = (userData) => {
    localStorage.setItem('cb_user', JSON.stringify(userData));
    setUser(userData);
    addToast(`Chào mừng ${userData.username || 'bạn'} trở lại!`, 'ok');
  };

  const logout = () => {
    localStorage.removeItem('cb_user');
    setUser(null);
    addToast('Đăng xuất hoàn tất.', 'info');
    window.location.href = '/';
  };

  const updateProfile = (newData) => {
    const updated = { ...user, ...newData };
    localStorage.setItem('cb_user', JSON.stringify(updated));
    setUser(updated);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
