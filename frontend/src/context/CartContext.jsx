import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../lib/api';
import { useAuth } from './AuthContext';

const CartContext = createContext(null);

export const CartProvider = ({ children }) => {
  const { user } = useAuth();
  const [cartCount, setCartCount] = useState(0);
  const [cartItems, setCartItems] = useState([]);

  // Fetch logic
  const fetchCart = useCallback(async () => {
    if (!user?.cart_id) {
       setCartCount(0);
       setCartItems([]);
       return;
    }
    
    try {
      const res = await apiFetch(`/carts/${user.cart_id}/`);
      if (res.ok) {
        const data = await res.json();
        
        // Enrich cart items with book details from Book-Service
        const itemsWithDetails = await Promise.all(
           (data.items || []).map(async (item) => {
              try {
                 const bookRes = await apiFetch(`/books/${item.book_id}/`);
                 if(bookRes.ok) {
                    const bookData = await bookRes.json();
                    return { ...item, title: bookData.title, cover_image_url: bookData.cover_image_url, price: bookData.price };
                 }
              } catch(e) {}
              // Fallback to basic schema if fetch fails
              return { ...item, title: `Sách ID: ${item.book_id}`, price: item.price_at_add || 0 };
           })
        );
        
        setCartItems(itemsWithDetails);
        
        // Tính tổng số lượng thay vì chỉ các mặt hàng
        const totalItemsCount = itemsWithDetails.reduce((acc, item) => acc + item.quantity, 0);
        setCartCount(totalItemsCount);
      }
    } catch (e) {
       console.error("Lỗi lấy giỏ hàng", e);
    }
  }, [user]);

  const addToCart = async (bookId, quantity = 1) => {
    if (!user) return false;
    try {
      const res = await apiFetch(`/customers/${user.service_user_id}/updateCart/`, {
        method: 'POST',
        body: JSON.stringify({ book_id: bookId, quantity })
      });
      if (res.ok) {
        fetchCart();
        return true;
      }
    } catch (e) {
      console.error(e);
    }
    return false;
  };

  // Luôn bắt trigger kéo giỏ hàng khi user thay đổi (VD log vào)
  useEffect(() => {
    fetchCart();
  }, [fetchCart]);

  return (
    <CartContext.Provider value={{ cartCount, cartItems, refreshCart: fetchCart, addToCart }}>
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => useContext(CartContext);
