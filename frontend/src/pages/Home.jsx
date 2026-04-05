import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { apiFetch } from '../lib/api';
import BookCard from '../components/ui/BookCard';

export default function Home() {
  const addToast = useToast();
  
  const [searchParams, setSearchParams] = useSearchParams();
  const searchQ = searchParams.get('search') || '';
  const categoryQ = searchParams.get('category') || '';
  const minPriceQ = searchParams.get('min_price') || '';
  const maxPriceQ = searchParams.get('max_price') || '';

  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);

  // States for local form
  const [category, setCategory] = useState(categoryQ);
  
  const getPriceRangeId = () => {
     if(minPriceQ === '0' && maxPriceQ === '50000') return '1';
     if(minPriceQ === '50000' && maxPriceQ === '150000') return '2';
     if(minPriceQ === '150000' && !maxPriceQ) return '3';
     return '';
  };
  const [priceRange, setPriceRange] = useState(getPriceRangeId());

  useEffect(() => {
    fetchBooks();
  }, [searchQ, categoryQ, minPriceQ, maxPriceQ]);

  const fetchBooks = async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams();
      if (searchQ) q.append('q', searchQ);
      if (categoryQ) q.append('category', categoryQ);
      if (minPriceQ) q.append('min_price', minPriceQ);
      if (maxPriceQ) q.append('max_price', maxPriceQ);
      
      const endpoint = q.toString() ? `/books/search/?${q.toString()}` : `/books/`;
      
      const res = await apiFetch(endpoint);
      if (res.ok) {
         const data = await res.json();
         setBooks(data.results || data.books || data || []);
      } else {
         addToast("Không thể tải danh sách sách", "err");
      }
    } catch (e) {
      addToast("Lỗi kết nối", "err");
    } finally {
      setLoading(false);
    }
  };

  const handleApplyFilter = () => {
     const newParams = new URLSearchParams();
     if(searchQ) newParams.set('search', searchQ);
     if(category) newParams.set('category', category);
     
     if(priceRange === '1') {
        newParams.set('min_price', '0');
        newParams.set('max_price', '50000');
     } else if(priceRange === '2') {
        newParams.set('min_price', '50000');
        newParams.set('max_price', '150000');
     } else if(priceRange === '3') {
        newParams.set('min_price', '150000');
     }
     
     setSearchParams(newParams);
  };

  const clearFilter = () => {
     setCategory('');
     setPriceRange('');
     if(searchQ) setSearchParams({ search: searchQ });
     else setSearchParams({});
  };

  return (
    <div style={{ flex: 1 }}>
      {!searchQ && (
        <div style={{ background: 'linear-gradient(135deg, var(--primary-light), var(--surface))', padding: '6rem 2rem', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
          <div className="container fade-in" style={{ position: 'relative', zIndex: 2 }}>
            <h1 style={{ fontSize: '4.5rem', fontWeight: 900, marginBottom: '1.5rem', letterSpacing: '-0.04em', lineHeight: 1.1, color: 'var(--text-1)' }}>
              Tri thức Không giới hạn.<br/> <span style={{ color: 'var(--primary)' }}>Cảm hứng Bất tận.</span>
            </h1>
            <p style={{ color: 'var(--text-3)', fontSize: '1.25rem', maxWidth: '600px', margin: '0 auto 2.5rem', lineHeight: 1.6 }}>
              Tuyển tập những tác phẩm khai phóng tư duy. Trải nghiệm không gian đọc sách tối giản, vượt giới hạn.
            </p>
            <button className="btn btn-primary btn-lg btn-pill" onClick={()=>window.scrollTo({top: window.innerHeight * 0.8, behavior:'smooth'})}>
              Bắt đầu Khám phá
            </button>
          </div>
          {/* Glass floating effects */}
          <div style={{ position: 'absolute', top: '10%', left: '20%', width: '300px', height: '300px', background: 'var(--secondary)', filter: 'blur(100px)', opacity: 0.15, borderRadius: '50%' }}></div>
          <div style={{ position: 'absolute', bottom: '10%', right: '20%', width: '400px', height: '400px', background: 'var(--primary)', filter: 'blur(120px)', opacity: 0.15, borderRadius: '50%' }}></div>
        </div>
      )}

      <div className="container page-section" style={{ padding: '4rem 2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '2.5rem' }}>
           <h2 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-1)' }}>
             {searchQ ? `Kết quả tìm kiếm cho "${searchQ}"` : category ? `Danh mục: ${category}` : 'Sách Nổi Bật Mới Nhất'}
           </h2>
        </div>

        <div style={{ background: 'var(--surface-2)', padding: '1.5rem', borderRadius: 'var(--radius-lg)', display: 'flex', flexWrap: 'wrap', gap: '1.5rem', alignItems: 'center', marginBottom: '3rem' }}>
           <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, color: 'var(--text-2)' }}>
              Bộ Lọc:
           </div>
           
           <div style={{ display: 'flex', gap: '1rem', flex: 1, minWidth: '280px' }}>
              <select className="input" value={category} onChange={e => setCategory(e.target.value)} style={{ flex: 1, cursor: 'pointer' }}>
                 <option value="">Tất cả danh mục</option>
                 <option value="programming">Lập trình & Công nghệ</option>
                 <option value="science">Khoa học Phổ thông</option>
                 <option value="fiction">Văn học giả tưởng</option>
                 <option value="history">Lịch sử & Xã hội</option>
              </select>

              <select className="input" value={priceRange} onChange={e => setPriceRange(e.target.value)} style={{ flex: 1, cursor: 'pointer' }}>
                 <option value="">Mọi mức giá</option>
                 <option value="1">Dưới 50.000 ₫</option>
                 <option value="2">Từ 50.000 ₫ - 150.000 ₫</option>
                 <option value="3">Trên 150.000 ₫</option>
              </select>
           </div>
           
           <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button onClick={handleApplyFilter} className="btn-primary" style={{ padding: '0.75rem 1.5rem', borderRadius: '8px' }}>Áp dụng</button>
              {(categoryQ || minPriceQ || maxPriceQ) && (
                 <button onClick={clearFilter} className="btn-ghost" style={{ padding: '0.75rem 1rem' }}>Bỏ lọc</button>
              )}
           </div>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '6rem' }}>
             <div className="spin spin-lg"></div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '2rem' }}>
            {books.length > 0 ? books.map((b) => (
               <BookCard key={b.id} book={b} />
            )) : (
              <div className="empty-state" style={{ gridColumn: '1/-1' }}>
                <h3>Không tìm thấy cuốn sách nào</h3>
                <p>Thử sử dụng từ khóa tiếng anh hoặc kiểm tra lại tên sách.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
