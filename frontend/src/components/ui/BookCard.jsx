import { ShoppingCart, Star } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useCart } from '../../context/CartContext';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';

export default function BookCard({ book }) {
  const { addToCart } = useCart();
  const { user } = useAuth();
  const addToast = useToast();

  const handleAdd = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!user) {
      addToast('Vui lòng đăng nhập để mượn/mua sách.', 'err');
      return;
    }
    const success = await addToCart(book.id, 1);
    if (success) {
      addToast(`Đã thêm ${book.title} vào giỏ`, 'ok');
    } else {
      addToast('LỖi thêm vào giỏ', 'err');
    }
  };

  return (
    <div className="card card-hover" style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative', overflow: 'hidden' }}>
      <Link to={`/book/${book.id}`} style={{ display: 'block', height: '240px', background: 'var(--surface-2)', position: 'relative' }}>
         {book.cover_image_url ? (
            <img src={book.cover_image_url} alt={book.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
         ) : (
            <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-4)', fontSize: '0.9rem', fontWeight: 600 }}>No Image</div>
         )}
         {book.badge && (
            <span className="badge badge-warning" style={{ position: 'absolute', top: '10px', left: '10px', boxShadow: 'var(--shadow-sm)' }}>
              {book.badge}
            </span>
         )}
      </Link>
      
      <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', flex: 1 }}>
         <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
           <div style={{ display: 'flex', alignItems: 'center', color: 'var(--warning)', fontSize: '0.85rem', fontWeight: 700 }}>
             <Star size={14} fill="currentColor" stroke="none" style={{ marginRight: '2px' }} /> 
             {book.average_rating ? Number(book.average_rating).toFixed(1) : 'Chưa có'}
           </div>
           <span style={{ color: 'var(--text-4)', fontSize: '0.8rem' }}>• {book.author || 'Đang cập nhật'}</span>
         </div>
         
         <Link to={`/book/${book.id}`} style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-1)', marginBottom: '0.5rem', lineHeight: 1.4, transition: 'var(--transition)' }} onMouseOver={e=>e.currentTarget.style.color='var(--primary)'} onMouseOut={e=>e.currentTarget.style.color='var(--text-1)'}>
           {book.title}
         </Link>
         
         <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
           <div>
             <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--primary)', letterSpacing: '-0.02em' }}>
               {Number(book.price).toLocaleString()} ₫
             </div>
           </div>
           {/* Add to cart shortcut button */}
           <button onClick={handleAdd} style={{ width: '38px', height: '38px', borderRadius: '50%', border: 'none', background: 'var(--primary-light)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: 'var(--transition)' }} onMouseOver={e=>{e.currentTarget.style.background='var(--primary)'; e.currentTarget.style.color='#fff'; e.currentTarget.style.transform='scale(1.1)';}} onMouseOut={e=>{e.currentTarget.style.background='var(--primary-light)'; e.currentTarget.style.color='var(--primary)'; e.currentTarget.style.transform='scale(1)';}}>
             <ShoppingCart size={18} />
           </button>
         </div>
      </div>
    </div>
  );
}
