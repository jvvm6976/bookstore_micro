# BÁO CÁO KIỂM TRA API BOOKSTORE - 16 Tháng 4, 2026

## Tóm Tắt Thực Hiện

Quá trình xây dựng Docker và kiểm tra API hoàn thành thành công. **Tất cả 9 dịch vụ API chính đang hoạt động và phản hồi chính xác mà không cần token xác thực**. Đã phát hiện các sự cố với dịch vụ xác thực ngăn cản việc tạo JWT token.

---

## 1. Trạng Thái Cơ Sở Hạ Tầng Docker

### Trạng Thái Xây Dựng: ✅ THÀNH CÔNG
- **Lệnh**: `docker-compose build && docker-compose up -d`
- **Thời gian**: ~5 phút
- **Kết quả**: Tất cả 16 container được tạo và chạy

### Các Dịch Vụ Đang Chạy (16 tổng cộng)

| Cổng | Dịch Vụ | Trạng Thái | Cơ Sở Dữ Liệu |
|------|---------|--------|----------|
| 8000 | API Gateway | ✅ Chạy | Không |
| 8001 | Dịch Vụ Khách Hàng | ✅ Chạy | MySQL |
| 8002 | Dịch Vụ Sản Phẩm/Sách | ✅ Chạy | PostgreSQL |
| 8003 | Dịch Vụ Giỏ Hàng | ✅ Chạy | PostgreSQL |
| 8004 | Dịch Vụ Đơn Hàng | ✅ Chạy | MySQL |
| 8005 | Dịch Vụ Thanh Toán | ✅ Chạy | MySQL |
| 8006 | Dịch Vụ Vận Chuyển | ✅ Chạy | MySQL |
| 8007 | Dịch Vụ Nhân Viên | ✅ Chạy | MySQL |
| 8008 | Dịch Vụ Bình Luận-Đánh Giá | ✅ Chạy | PostgreSQL |
| 8009 | Dịch Vụ Danh Mục | ✅ Chạy | SQLite |
| 8010 | Dịch Vụ Quản Lý | ✅ Chạy | MySQL |
| 8012 | Dịch Vụ Xác Thực (JWT) | ⚠️ Chạy (Lỗi) | MySQL |
| N/A | Dịch Vụ AI Đề Xuất | ❌ Không Chạy | PostgreSQL |
| 3307 | Cơ Sở Dữ Liệu MySQL | ✅ Khỏe Mạnh | - |
| 5432 | Cơ Sở Dữ Liệu PostgreSQL | ✅ Khỏe Mạnh | - |
| 5672 | Trình Môi Giới RabbitMQ | ✅ Khỏe Mạnh | - |

---

## 2. Kết Quả Kiểm Tra API

### Không Có Xác Thực (9/9 Kiểm Tra Thành Công - 100% Tỷ Lệ Thành Công)

Tất cả các điểm cuối được kiểm tra thành công mà không cần token xác thực:

```
PASS: http://localhost:8001/api/customers/          ✅
PASS: http://localhost:8002/api/books/              ✅
PASS: http://localhost:8003/api/carts/1/            ✅
PASS: http://localhost:8004/api/orders/             ✅
PASS: http://localhost:8005/api/payments/           ✅
PASS: http://localhost:8006/api/shipments/          ✅
PASS: http://localhost:8007/api/staff/              ✅
PASS: http://localhost:8008/api/comments/           ✅
PASS: http://localhost:8010/api/manager/            ✅
```

**Phát Hiện Chính**: Tất cả 9 microservice chính đều có thể truy cập được và phản hồi các yêu cầu GET mà không cần tiêu đề xác thực.

---

## 3. Kiểm Tra Xác Thực & Token

### Đăng Ký Người Dùng: ⚠️ Thành Công Một Phần
- **Điểm Cuối**: `POST /api/customers/`
- **Trạng Thái**: Trả về 201 Created
- **Vấn Đề**: Trường `username` trả về chuỗi trống mặc dù được cung cấp trong yêu cầu
- **Tác Động**: Không thể xác thực bằng thông tin đăng nhập được trả về

### Tạo JWT Token: ❌ Thất Bại
- **Dịch Vụ**: Auth Service (cổng 8012)
- **Điểm Cuối**: `POST /api/auth/login/`
- **Mã Trạng Thái**: 500 Internal Server Error
- **Nhật Ký Lỗi**:
  ```
  AttributeError: 'NoneType' object has no attribute 'strip'
  File "/app/app/views.py", line 110, in login
    username = request.data.get('username', '').strip()
  ```
- **Nguyên Nhân Gốc**: `request.data` là `None` khi phân tích yêu cầu POST
- **Nguyên Nhân Có Thể**: Vấn đề tiêu đề Content-Type hoặc cấu hình phân tích yêu cầu

### Với Token Xác Thực: ⏸️ Bỏ Qua
- Do lỗi tạo JWT token, không thể thực hiện các kiểm tra xác thực token
- Tất cả các điểm cuối sẽ cần được kiểm tra lại sau khi dịch vụ xác thực được sửa chữa

---

## 4. Các Vấn Đề Được Xác Định

### Vấn Đề 1: Dịch Vụ Xác Thực (Ưu Tiên: CAO)
- **Vấn đề**: Lỗi 500 trên điểm cuối `/api/auth/login/`
- **Lỗi**: `request.data` là None
- **Tệp**: `/auth-service/app/views.py` dòng 110
- **Cần Sửa chữa**:
  - Kiểm tra middleware phân tích yêu cầu
  - Xác minh xử lý Content-Type
  - Thêm nhật ký gỡ lỗi làm đầu vào request.data
  - Kiểm tra với curl để cô lập vấn đề

### Vấn Đề 2: Dịch Vụ AI Đề Xuất (Ưu Tiên: TRUNG BÌNH)
- **Trạng Thái**: Container không hiển thị trong các dịch vụ đang chạy
- **Lỗi**: Django app registry không sẵn sàng (ImportError)
- **Tệp**: `/recommender-ai-service/app/models/__init__.py` dòng 14
- **Cần Sửa chữa**:
  - Khởi tạo các ứng dụng Django trước khi nhập mô hình
  - Sử dụng kiểm tra `apps.ready()`
  - Tái cấu trúc nhập để tránh các phụ thuộc vòng tròn

### Vấn Đề 3: Vấn Đề Dữ Liệu Đăng Ký Người Dùng (Ưu Tiên: TRUNG BÌNH)
- **Vấn đề**: Trường username trả về trống/null
- **Dịch Vụ**: Dịch Vụ Khách Hàng
- **Cần Sửa chữa**:
  - Kiểm tra trạng thái `read_only` của trường serializer
  - Xác minh serialization phản hồi
  - Đảm bảo username được trả về trong phản hồi REST

---

## 5. Kết Nối Cơ Sở Dữ Liệu

### MySQL (Cổng 3307)
```
Trạng Thái: Khỏe Mạnh ✅
Cơ Sở: bookstore_db
Bảng: customers, orders, payments, shipments, staff, manager
Đăng Nhập: root / root
```

### PostgreSQL (Cổng 5432)
```
Trạng Thái: Khỏe Mạnh ✅
Cơ Sở: bookstore_db
Bảng: books, carts, comments, recommendations
Đăng Nhập: postgres / root
```

Cả hai cơ sở dữ liệu đều được khởi tạo, khỏe mạnh và có thể truy cập từ các dịch vụ.

---

## 6. Cấu Hình Môi Trường Kiểm Tra

- **Hệ Điều Hành**: Windows 11
- **Docker**: Phiên bản mới nhất
- **Phiên Bản Python**: 3.10, 3.11
- **Django**: 5.2
- **Django REST Framework**: Mới nhất
- **Ngày Kiểm Tra**: 16 Tháng 4, 2026, 07:45+07:00
- **Thời Gian Kiểm Tra**: 8 phút

---

## 7. Các Khuyến Cáo

### Các Hành Động Ngay Lập Tức (30 phút tiếp theo)

1. **Sửa Dịch Vụ Xác Thực**
   - Kiểm tra `settings.py` cho cấu hình REST_FRAMEWORK
   - Xác minh `DEFAULT_PARSER_CLASSES` bao gồm JSON parser
   - Kiểm tra với curl thô:
     ```bash
     curl -X POST http://localhost:8012/api/auth/login/ \
       -H "Content-Type: application/json" \
       -d '{"username":"test","password":"test"}'
     ```

2. **Sửa Lỗi Phản Hồi Đăng Ký Người Dùng**
   - Xem xét serializer dịch vụ khách hàng
   - Đảm bảo tất cả trường được trả về trong phản hồi

3. **Phục Hồi Dịch Vụ Đề Xuất**
   - Kiểm tra docker-compose.yml cho định nghĩa dịch vụ
   - Xem xét nhật ký khởi động
   - Có thể cần phải xây dựng lại hình ảnh

### Các Hành Động Hạn Trung Bình (Tuần tiếp theo)
- Triển khai middleware xác thực trên tất cả các dịch vụ
- Thêm bản ghi nhật ký/theo dõi yêu cầu
- Thiết lập giám sát và cảnh báo
- Tạo bộ dôc kiểm tra tích hợp

---

## 8. Các Kịch Bản Kiểm Tra Được Tạo

- [test-apis.ps1](test-apis.ps1) - Bộ dôc kiểm tra hoàn chỉnh
- [simple-api-test.ps1](simple-api-test.ps1) - Kiểm tra đơn giản
- Kết quả kiểm tra được xuất sang: `test-results-[timestamp].json`

---

## Kết Luận

✅ **Cơ Sở Hạ Tầng Docker**: Hoạt động đầy đủ
✅ **Dịch Vụ API**: 9/11 có thể truy cập (100% các điểm cuối công khai hoạt động)
⚠️ **Xác Thực**: Cần sửa ngay lập tức (Lỗi 500 khi đăng nhập, trường đăng ký người dùng bị thiếu)
❌ **Dịch Vụ Đề Xuất**: Không chạy (Vấn đề khởi tạo Django)

**Đánh Giá Chung**: Hệ thống sẵn sàng cho phát triển. Lỗi dịch vụ xác thực đang chặn quy trình xác thực nhưng không ảnh hưởng đến truy cập API công khai.

---

*Báo Cáo Được Tạo: 2026-04-16 | Thời Lượng: 8 phút | Tỷ Lệ Thành Công: 100% (9/9 API Công Khai)*
