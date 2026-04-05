import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import BookCard from '../components/ui/BookCard';
import { Filter, Search as SearchIcon } from 'lucide-react';

export default function Catalog() {
  const [searchParams, setSearchParams] = useSearchParams();
  const searchQ = searchParams.get('search') || '';
  const categoryQ = searchParams.get('category') || '';
  const minPriceQ = searchParams.get('min_price') || '';
  const maxPriceQ = searchParams.get('max_price') || '';

  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);

  // States for local form (to avoid instant reload while picking)
  const [category, setCategory] = useState(categoryQ);
  
  // Custom price ranges
  // 1: < 50,000
  // 2: 50,000 - 150,000
  // 3: > 150,000
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
        // /books/search/ returns { count, results }, while /books/ returns an array
        setBooks(data.results || data);
      }
    } catch(err) {
      console.error(err);
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
     // Keep search keyword if any
     if(searchQ) setSearchParams({ search: searchQ });
     else setSearchParams({});
  };

  return (
    <div className="container page-section fade-in">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        
        {/* Header */}
        <div>
           <h1 style={{ fontSize: '2.5rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '0.5rem' }}>
              {searchQ ? `Tìm kiếm: "${searchQ}"` : 'Danh Mục Sản Phẩm'}
           </h1>
           <p style={{ color: 'var(--text-3)' }}>Khám phá kho tàng tri thức với hàng ngàn tựa sách hấp dẫn.</p>
        </div>

        {/* Cấu Hình Bộ Lọc (Dropdowns) */}
        <div style={{ background: 'var(--surface-2)', padding: '1.5rem', borderRadius: 'var(--radius-lg)', display: 'flex', flexWrap: 'wrap', gap: '1.5rem', alignItems: 'center' }}>
           <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, color: 'var(--text-2)' }}>
              <Filter size={20}/> Lọc Sách:
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

        {/* Results */}
        {loading ? (
            <div style={{ textAlign: 'center', padding: '6rem' }}><div className="spin spin-lg"></div></div>
        ) : books.length > 0 ? (
            <div>
               <div style={{ marginBottom: '1.5rem', fontWeight: 600, color: 'var(--text-3)' }}>Đã tìm thấy {books.length} kết quả phù hợp</div>
               <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '2rem' }}>
                 {books.map(book => <BookCard key={book.id} book={book} />)}
               </div>
            </div>
        ) : (
            <div className="empty-state" style={{ background: 'var(--surface)', borderRadius: 'var(--radius)', marginTop: '2rem' }}>
              <SearchIcon size={48} color="var(--border)" style={{ marginBottom: '1rem' }} />
              <h3>Không tìm thấy sách</h3>
              <p>Thử bỏ bớt bộ lọc hoặc sử dụng từ khóa tìm kiếm khác xem sao.</p>
            </div>
        )}
      </div>
    </div>
  );
}
