import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

// Contexts
import { ToastProvider } from './context/ToastContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { CartProvider } from './context/CartContext';

// Layouts
import CustomerLayout from './components/layout/CustomerLayout';
import InternalLayout from './components/layout/InternalLayout';

// Pages
import Home from './pages/Home';
import LoginCustomer from './pages/LoginCustomer';
import LoginInternal from './pages/LoginInternal';
import Cart from './pages/Cart';
import StaffDashboard from './pages/StaffDashboard';
import ManagerDashboard from './pages/ManagerDashboard';
import Catalog from './pages/Catalog';
import BookDetail from './pages/BookDetail';
import Checkout from './pages/Checkout';
import Profile from './pages/Profile';

import './index.css';

const InternalRoute = ({ children, allowedRoles }) => {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!allowedRoles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
};

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <CartProvider>
            <Routes>
              {/* Customer Portal */}
              <Route path="/" element={<CustomerLayout />}>
                <Route index element={<Home />} />
                <Route path="customer-login" element={<LoginCustomer />} />
                <Route path="cart" element={<Cart />} />
                <Route path="catalog" element={<Catalog />} />
                <Route path="book/:id" element={<BookDetail />} />
                <Route path="checkout" element={<Checkout />} />
                <Route path="profile" element={<Profile />} />
              </Route>

              {/* Internal Login */}
              <Route path="/login" element={<LoginInternal />} />
              
              {/* Internal Portal */}
              <Route path="/" element={<InternalLayout />}>
                <Route path="staff" element={
                  <InternalRoute allowedRoles={['staff', 'manager']}>
                    <StaffDashboard />
                  </InternalRoute>
                } />
                <Route path="manager" element={
                  <InternalRoute allowedRoles={['manager']}>
                    <ManagerDashboard />
                  </InternalRoute>
                } />
              </Route>
            </Routes>
          </CartProvider>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
