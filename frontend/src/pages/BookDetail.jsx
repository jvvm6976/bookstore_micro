import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../lib/api';
import { Star, ShoppingCart, ArrowLeft, Send } from 'lucide-react';

export default function BookDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { addToCart } = useCart();
  const { user } = useAuth();
  const addToast = useToast();

  const [book, setBook] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [qty, setQty] = useState(1);
  const [canReview, setCanReview] = useState(false);
  const [newReview, setNewReview] = useState({ content: '', rating: 5 });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchBookData();
  }, [id]);

  const fetchBookData = async () => {
    setLoading(true);
    try {
      // Fetch book info
      const bRes = await apiFetch(`/books/${id}/`);
      if(bRes.ok) {
        const bData = await bRes.json();
        setBook(bData);
      } else {
        addToast("Không tìm thấy thông tin sách.", "err");
        navigate('/');
        return;
      }
      
      // Fetch comments/reviews
      const cRes = await apiFetch(`/comments/book/${id}/`);
      if(cRes.ok) {
        const cData = await cRes.json();
        setReviews(cData);
        if(user) {
           const alreadyReviewed = cData.some(r => r.user_id === user.service_user_id);
           // Logic to allow review can be more complex, but here we just check if not reviewed yet
           setCanReview(!alreadyReviewed);
        }
      }
    } catch(err) {
      addToast("Lỗi kết nối khi tải chi tiết", "err");
    } finally {
      setLoading(false);
    }
  };

  const handleAddToCart = async () => {
    if(!user) { addToast('Cần đăng nhập để mua hàng.', 'err'); return; }
    const ok = await addToCart(book.id, qty);
    if(ok) addToast(`Đã thêm ${qty} cuốn vào giỏ!`, 'ok');
    else addToast('Thêm vào giỏ thất bại', 'err');
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    if(!newReview.content.trim()) return;
    setSubmitting(true);
    try {
       const res = await apiFetch(`/comments/`, {
         method: 'POST',
         body: JSON.stringify({
           book_id: parseInt(id),
           username: user?.username || 'Khách',
           user_id: user?.service_user_id,
           content: newReview.content,
           rating: newReview.rating
         })
       });
       if(res.ok) {
         addToast("Gửi đánh giá thành công!", "ok");
         setNewReview({ content: '', rating: 5 });
         setCanReview(false);
         fetchBookData(); // Refresh to show new review
       } else {
         addToast("Không thể gửi bình luận", "err");
       }
    } catch(e) { addToast("Lỗi mạng", "err"); }
    finally { setSubmitting(false); }
  };

  if(loading) return <div className="page-section" style={{textAlign:'center', padding:'8rem 0'}}><div className="spin spin-lg"></div></div>;
  if(!book) return null;

  return (
    <div className="container page-section fade-in">
       <button onClick={()=>navigate(-1)} className="btn btn-ghost" style={{ padding: 0, marginBottom: '2rem', fontSize: '0.95rem' }}>
          <ArrowLeft size={18}/> Quay lại
       </button>

       <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 400px) 1fr', gap: '4rem', marginBottom: '4rem' }}>
          {/* Image */}
          <div style={{ background: 'var(--surface-2)', borderRadius: 'var(--radius-lg)', padding: '2rem', display: 'flex', alignItems: 'center', justifyItems: 'center' }}>
             <img src={book.cover_image_url || 'https://via.placeholder.com/400x600'} style={{ width: '100%', height: 'auto', borderRadius: '8px', boxShadow: 'var(--shadow-lg)' }} alt={book.title} />
          </div>

          {/* Info */}
          <div style={{ display: 'flex', flexDirection: 'column' }}>
             <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
                <span className="badge badge-primary">{book.category}</span>
                <div style={{ display: 'flex', alignItems: 'center', color: 'var(--warning)', fontWeight: 700 }}>
                   <Star size={16} fill="currentColor" stroke="none" style={{marginRight:'4px'}}/>
                   {book.average_rating ? Number(book.average_rating).toFixed(1) : 'Chưa có đánh giá'}
                </div>
             </div>
             
             <h1 style={{ fontSize: '2.5rem', fontWeight: 900, marginBottom: '0.5rem', lineHeight: 1.2, letterSpacing: '-0.02em' }}>{book.title}</h1>
             <div style={{ fontSize: '1.2rem', color: 'var(--text-3)', marginBottom: '2rem' }}>Tác giả: <span style={{color:'var(--text-1)', fontWeight:600}}>{book.author || 'Đang cập nhật'}</span></div>

             <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--primary)', marginBottom: '2rem' }}>
                {Number(book.price).toLocaleString()} ₫
             </div>

             <div style={{ color: 'var(--text-2)', lineHeight: 1.8, marginBottom: '3rem', fontSize: '1.05rem' }}>
                {book.description || 'Chưa có mô tả chi tiết cho sản phẩm này. Hãy đón đọc những điều thú vị ẩn chứa bên trong từng trang sách.'}
             </div>

             <div style={{ background: 'var(--surface)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '2rem', marginTop: 'auto' }}>
                <div>
                   <label className="field-label" style={{ marginBottom: '0.5rem' }}>Số lượng</label>
                   <div style={{ display: 'flex', alignItems: 'center', background: 'var(--surface-2)', borderRadius: '8px', width: 'fit-content' }}>
                      <button onClick={()=>setQty(q=>Math.max(1, q-1))} style={{ padding: '0.75rem 1rem', background:'none', border:'none', cursor:'pointer', fontSize: '1.2rem'}}>-</button>
                      <span style={{ padding: '0 1rem', fontWeight: 700 }}>{qty}</span>
                      <button onClick={()=>setQty(q=>q+1)} style={{ padding: '0.75rem 1rem', background:'none', border:'none', cursor:'pointer', fontSize: '1.2rem'}}>+</button>
                   </div>
                </div>
                
                <button onClick={handleAddToCart} className="btn-primary" style={{ flex: 1, padding: '1rem', borderRadius: '8px', fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', border: 'none', cursor: 'pointer', transition: 'var(--transition)' }}>
                   <ShoppingCart size={20} /> Thêm Vào Giỏ
                </button>
             </div>
             
             {book.stock <= 10 && book.stock > 0 && (
                <div style={{ marginTop: '1rem', color: 'var(--danger)', fontSize: '0.9rem', fontWeight: 600 }}>Chỉ còn lại {book.stock} cuốn trong kho!</div>
             )}
          </div>
       </div>

       {/* Reviews Section */}
       <div style={{ borderTop: '1px solid var(--border)', paddingTop: '4rem' }}>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 800, marginBottom: '2rem' }}>Đánh giá từ Độc giả</h2>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: '3rem' }}>
             <div>
                {reviews.length > 0 ? (
                   <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                      {reviews.map(r => (
                         <div key={r.id} style={{ background: 'var(--surface)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                               <div style={{ fontWeight: 700, fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                  <div style={{ width: '32px', height: '32px', background: 'var(--primary-light)', color: 'var(--primary)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.9rem' }}>{r.username.charAt(0).toUpperCase()}</div>
                                  {r.username}
                               </div>
                               <div style={{ display: 'flex', color: 'var(--warning)', gap: '2px' }}>
                                  {Array.from({length: 5}).map((_,i) => <Star key={i} size={16} fill={i < r.rating ? "currentColor" : "none" } stroke={i < r.rating ? "none" : "currentColor"} className={i >= r.rating ? "empty" : ""} />)}
                               </div>
                            </div>
                            <p style={{ color: 'var(--text-2)', lineHeight: 1.6 }}>{r.content}</p>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-4)', marginTop: '1rem' }}>{new Date(r.created_at).toLocaleDateString('vi-VN')}</div>
                         </div>
                      ))}
                   </div>
                ) : (
                   <div className="empty-state" style={{ background: 'var(--surface)', borderRadius: 'var(--radius)' }}>
                      <h3>Chưa có bình luận</h3>
                      <p>Hãy là người đầu tiên cảm nhận và đánh giá tác phẩm này.</p>
                   </div>
                )}
             </div>

             <div>
                {user && canReview ? (
                   <form onSubmit={handleReviewSubmit} style={{ background: 'var(--surface-2)', padding: '2rem', borderRadius: 'var(--radius-lg)' }}>
                      <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.5rem' }}>Chia sẻ cảm nghĩ</h3>
                      
                      <div style={{ marginBottom: '1.5rem' }}>
                         <label className="field-label">Điểm số (1-5)</label>
                         <div style={{ display: 'flex', gap: '0.5rem' }}>
                            {Array.from({length: 5}).map((_, i) => (
                               <button key={i} type="button" onClick={() => setNewReview({...newReview, rating: i+1})} style={{ background: 'none', border:'none', cursor:'pointer', color: i < newReview.rating ? 'var(--warning)' : 'var(--border)' }}>
                                  <Star size={28} fill={i < newReview.rating ? "currentColor" : "none"} strokeWidth={i < newReview.rating ? 0 : 2}/>
                               </button>
                            ))}
                         </div>
                      </div>

                      <div style={{ marginBottom: '1.5rem' }}>
                         <label className="field-label">Nội dung đánh giá</label>
                         <textarea className="textarea" rows="4" value={newReview.content} onChange={e=>setNewReview({...newReview, content: e.target.value})} placeholder="Viết cảm nhận của bạn..."></textarea>
                      </div>

                      <button type="submit" disabled={submitting} className="btn-primary" style={{ width: '100%', padding: '0.85rem', borderRadius: '8px', border:'none', cursor:'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                         {submitting ? <span className="spin spin-sm"></span> : <><Send size={18}/> Gửi Đánh Giá</>}
                      </button>
                   </form>
                ) : user && !canReview ? (
                   <div style={{ background: 'var(--surface-2)', padding: '2rem', borderRadius: 'var(--radius-lg)', textAlign: 'center', color: 'var(--text-3)' }}>
                      Bạn đã viết đánh giá cho sản phẩm này.
                   </div>
                ) : (
                   <div style={{ background: 'var(--surface-2)', padding: '2rem', borderRadius: 'var(--radius-lg)', textAlign: 'center' }}>
                      <p style={{ marginBottom: '1rem', color: 'var(--text-3)' }}>Đăng nhập để chia sẻ bình luận và đánh giá của bạn.</p>
                      <button onClick={()=>navigate('/customer-login')} className="btn-outline" style={{ padding: '0.5rem 1rem', borderRadius: '20px' }}>Đăng nhập ngay</button>
                   </div>
                )}
             </div>
          </div>
       </div>
    </div>
  );
}
