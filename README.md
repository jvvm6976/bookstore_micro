# ShopSphere Ecommerce Microservices

ShopSphere là một nền tảng thương mại điện tử đa ngành được xây dựng theo kiến trúc microservices. Dự án mô phỏng một marketplace hiện đại, nơi người dùng có thể duyệt sản phẩm, tìm kiếm theo danh mục, lưu sản phẩm yêu thích, thêm vào giỏ hàng, đặt hàng, thanh toán, theo dõi vận chuyển, đánh giá sản phẩm và nhận gợi ý cá nhân hóa từ AI Chatbot.

Hệ thống tập trung vào trải nghiệm mua sắm thống nhất cho nhiều nhóm sản phẩm như sách, điện tử và thời trang, đồng thời tách các nghiệp vụ chính thành nhiều service độc lập để dễ mở rộng và bảo trì.

## Mục Tiêu Dự Án

- Xây dựng một hệ thống ecommerce hoàn chỉnh theo mô hình microservices.
- Tách riêng các nghiệp vụ như người dùng, sản phẩm, giỏ hàng, đơn hàng, thanh toán, vận chuyển, đánh giá, thông báo và AI.
- Cung cấp giao diện web thống nhất cho khách hàng.
- Tích hợp AI Chatbot để tư vấn sản phẩm, hỗ trợ tìm kiếm và trả lời các câu hỏi phổ biến.
- Mô phỏng luồng mua hàng thực tế từ duyệt sản phẩm đến sau bán hàng.

## Tính Năng Chính

### Khách Hàng

- Đăng ký và đăng nhập tài khoản.
- Quản lý thông tin cá nhân và địa chỉ giao hàng.
- Duyệt catalog sản phẩm theo ngành hàng và danh mục.
- Tìm kiếm sản phẩm bằng tiếng Việt hoặc tiếng Anh.
- Xem chi tiết sản phẩm.
- Thêm sản phẩm vào giỏ hàng.
- Lưu sản phẩm vào danh sách yêu thích.
- Đặt hàng và thanh toán.
- Theo dõi trạng thái đơn hàng và vận chuyển.
- Đánh giá sản phẩm sau khi mua.
- Nhận thông báo về đơn hàng, thanh toán và vận chuyển.

### Catalog Sản Phẩm

ShopSphere hiện hỗ trợ nhiều ngành hàng:

- Books: sách văn học, khoa học, phi hư cấu.
- Electronics: điện thoại, laptop, phụ kiện điện tử.
- Fashion: quần áo, giày, thời trang nam và nữ.

Sản phẩm có các thông tin như tên, mô tả, SKU, giá, tồn kho, trạng thái, danh mục, ngành hàng và dữ liệu đặc thù theo từng loại sản phẩm.

### Giỏ Hàng Và Wishlist

- Mỗi người dùng có giỏ hàng riêng.
- Sản phẩm trong giỏ hàng lưu số lượng và đơn giá tại thời điểm thêm.
- Wishlist cho phép lưu sản phẩm quan tâm để mua sau.
- Có thể chuyển sản phẩm từ wishlist sang giỏ hàng.

### Đơn Hàng, Thanh Toán Và Vận Chuyển

Luồng mua hàng được thiết kế theo hướng gần với thực tế:

- Tạo đơn hàng từ giỏ hàng.
- Kiểm tra tồn kho trước khi đặt hàng.
- Ghi nhận giá sản phẩm tại thời điểm checkout.
- Tạo thông tin giao hàng từ địa chỉ mặc định của người dùng.
- Thanh toán qua các phương thức như COD, VNPay, MoMo hoặc Stripe.
- Theo dõi trạng thái vận chuyển từ xử lý đến giao hàng thành công.
- Cập nhật trạng thái đơn hàng theo tiến trình thanh toán và vận chuyển.

### Đánh Giá Và Thông Báo

- Người dùng có thể đánh giá sản phẩm đã mua.
- Review có trạng thái chờ duyệt.
- Hệ thống thông báo hỗ trợ các sự kiện như tạo đơn hàng, thanh toán thành công và giao hàng.
- Người dùng có thể xem thông báo chưa đọc và đánh dấu đã đọc.

## AI Chatbot

AI Chatbot là một điểm nổi bật của ShopSphere. Chatbot hỗ trợ người dùng trong quá trình mua sắm bằng cách hiểu ý định, trích xuất thông tin sản phẩm và kết hợp dữ liệu từ catalog, review, hành vi người dùng và knowledge base.

Chatbot có thể xử lý các nhóm yêu cầu như:

- Tư vấn sản phẩm theo nhu cầu.
- Tìm sản phẩm theo ngành hàng, danh mục, thương hiệu hoặc khoảng giá.
- Gợi ý sản phẩm phổ biến hoặc sản phẩm tương tự.
- Cá nhân hóa đề xuất dựa trên hành vi người dùng.
- Trả lời câu hỏi về chính sách đổi trả, thanh toán và giao hàng.
- Hỗ trợ tra cứu thông tin đơn hàng khi có đủ dữ liệu liên quan.

Ví dụ:

- "Tôi muốn mua điện thoại"
- "Tìm laptop Apple"
- "Gợi ý sản phẩm thời trang"
- "Chính sách đổi trả như thế nào?"

AI service sử dụng nhiều thành phần phối hợp:

- Intent detector để nhận diện mục đích câu hỏi.
- Entity extractor để nhận diện sản phẩm, danh mục, thương hiệu và giá.
- Catalog client để truy xuất dữ liệu sản phẩm.
- Recommendation service để gợi ý sản phẩm.
- RAG/Knowledge Base để bổ sung ngữ cảnh từ sản phẩm và review.
- Response composer để tạo câu trả lời phù hợp với ngữ cảnh ShopSphere.

## Kiến Trúc Tổng Quan

Dự án được tổ chức theo kiến trúc microservices. Mỗi service phụ trách một miền nghiệp vụ riêng và giao tiếp với nhau thông qua REST API hoặc message broker.

| Service | Cổng | Vai trò |
|---|---:|---|
| API Gateway | 8000 | Điểm vào chính của hệ thống, render giao diện web và chuyển tiếp API |
| User Service | 8001 | Quản lý tài khoản, đăng nhập, hồ sơ và địa chỉ |
| Product Service | 8002 | Quản lý ngành hàng, danh mục, sản phẩm và tồn kho |
| Cart Service | 8003 | Quản lý giỏ hàng và wishlist |
| Order Service | 8004 | Xử lý checkout, đơn hàng và lịch sử trạng thái |
| Payment Service | 8005 | Xử lý thanh toán và giao dịch |
| Shipping Service | 8006 | Quản lý vận chuyển và tracking |
| Comment Rate Service | 8007 | Quản lý đánh giá và phản hồi sản phẩm |
| Notification Service | 8008 | Quản lý thông báo người dùng |
| AI Service | 8009 | Chatbot, gợi ý sản phẩm, phân tích hành vi và knowledge base |

## Công Nghệ Sử Dụng

- Backend: Python, Django, Django REST Framework
- Frontend: Django Templates, HTML, CSS, JavaScript
- Authentication: JWT
- Database: MySQL, PostgreSQL
- Message Broker: RabbitMQ
- Graph Database: Neo4j
- AI/RAG: FAISS, knowledge base, recommendation logic
- Containerization: Docker, Docker Compose

## Hướng Dẫn Chạy Dự Án

Yêu cầu cài sẵn Docker Desktop và Docker Compose.

Mở terminal tại thư mục dự án:

```powershell
cd C:\Users\asus\Downloads\Ecommerce
```

Build và chạy toàn bộ hệ thống:

```powershell
docker compose up -d --build
```

Sau khi container khởi động, truy cập ứng dụng tại:

```text
http://localhost:8000
```

Xem danh sách service đang chạy:

```powershell
docker compose ps
```

Build lại một service cụ thể:

```powershell
docker compose up -d --build api-gateway
docker compose up -d --build product-service
docker compose up -d --build ai-service
```

Dừng hệ thống:

```powershell
docker compose down
```

Dừng hệ thống và xóa dữ liệu volume:

```powershell
docker compose down -v
```

## Giao Diện Chính

ShopSphere có các giao diện dành cho khách hàng:

- Trang chủ marketplace.
- Trang catalog và tìm kiếm sản phẩm.
- Trang chi tiết sản phẩm.
- Trang giỏ hàng.
- Trang thanh toán.
- Trang đơn hàng.
- Trang theo dõi vận chuyển.
- Trang wishlist.
- Trang thông báo.
- Trang đánh giá.
- Trang đăng nhập và đăng ký.
- Trang hồ sơ người dùng.
- Trang AI Chatbot.

Giao diện được thiết kế theo hướng thống nhất, tập trung vào trải nghiệm mua sắm rõ ràng, dễ tìm kiếm và dễ thao tác.

## Dữ Liệu Và Hạ Tầng

Hệ thống sử dụng nhiều loại lưu trữ phù hợp với từng nghiệp vụ:

- MySQL cho các nghiệp vụ người dùng, đơn hàng, thanh toán và vận chuyển.
- PostgreSQL cho catalog, giỏ hàng, đánh giá, thông báo và AI.
- RabbitMQ cho các sự kiện nội bộ giữa service.
- Neo4j cho dữ liệu graph phục vụ phân tích và AI.
- FAISS index cho truy xuất knowledge base trong AI service.

## Điểm Nổi Bật

- Kiến trúc microservices tách biệt rõ từng nghiệp vụ.
- Catalog đa ngành thay vì chỉ tập trung vào một loại sản phẩm.
- Hỗ trợ tìm kiếm tiếng Việt cho các từ khóa phổ biến như điện thoại, laptop, sách, giày và thời trang.
- Luồng checkout có kiểm tra tồn kho, tạo vận chuyển, tạo thông báo và hỗ trợ hoàn stock khi hủy đơn.
- AI Chatbot được tích hợp trực tiếp vào trải nghiệm mua sắm.
- Giao diện frontend thống nhất qua API Gateway.

## Trạng Thái Dự Án

ShopSphere hiện là một bản triển khai ecommerce microservices hoàn chỉnh ở mức demo/prototype, có đầy đủ các service cốt lõi và giao diện web để mô phỏng quá trình mua sắm thực tế từ tìm kiếm sản phẩm đến sau bán hàng.
