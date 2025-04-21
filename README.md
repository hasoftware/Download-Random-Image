# Auto Generator Image 10KB

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.6%2B-blue)

Công cụ tự động tải và tối ưu hóa hình ảnh với kích thước dưới 10KB từ nhiều nguồn khác nhau. Chương trình này hỗ trợ tải hình ảnh đồng thời từ nhiều API và tự động nén hình ảnh xuống còn dưới 10KB mà vẫn giữ được chất lượng tốt nhất có thể.

## Tính năng chính

- **Tải ảnh từ nhiều nguồn khác nhau:**

  - [Pexels](https://www.pexels.com/) - Kho ảnh chuyên nghiệp với nhiều chủ đề
  - [ThisPersonDoesNotExist](https://thispersondoesnotexist.com/) - Ảnh khuôn mặt AI tạo ra
  - [Picsum Photos](https://picsum.photos/) - Ảnh ngẫu nhiên đa dạng
  - [TheCatAPI](https://thecatapi.com/) - Ảnh mèo đáng yêu

- **Tối ưu hóa hình ảnh:**

  - Nén ảnh xuống dưới 10KB
  - Giảm kích thước thông minh
  - Lựa chọn chất lượng tối ưu bằng thuật toán tìm kiếm nhị phân

- **Xử lý đa luồng:**
  - Tải nhiều ảnh cùng lúc
  - Tải song song từ nhiều nguồn
  - Điều chỉnh số lượng luồng cho mỗi nguồn
- **Theo dõi tiến trình:**
  - Hiển thị thống kê chi tiết
  - Ước tính thời gian hoàn thành
  - Tỷ lệ thành công theo nguồn
- **Chức năng tiên tiến:**
  - Phát hiện và bỏ qua ảnh trùng lặp bằng perceptual hashing
  - Điều chỉnh tải CPU tự động
  - Xử lý giới hạn rate limit của API
  - Chế độ debug để khắc phục sự cố

## Yêu cầu hệ thống

- Python 3.6 trở lên
- Các thư viện phụ thuộc (được cài đặt tự động):
  - requests
  - Pillow (PIL)
  - colorama
  - tabulate
  - psutil (tùy chọn, để giám sát CPU)

## Cài đặt

1. Clone repository:

```bash
git clone https://github.com/yourusername/Auto_Genator_Image_10KB.git
cd Auto_Genator_Image_10KB
```

2. Cài đặt các thư viện cần thiết:

```bash
pip install -r requirements.txt
```

3. (Tùy chọn) Tạo file `keyword.txt` chứa danh sách từ khóa tìm kiếm cho Pexels, mỗi từ khóa cách nhau bằng dấu phẩy:

```
landscape, nature, mountain, beach, sunset, forest, ocean, waterfall, desert, city
```

## Hướng dẫn sử dụng

1. Chạy chương trình:

```bash
python download_landscape.py
```

2. Cấu hình các tùy chọn:

   - Bật/tắt chế độ debug
   - Bật/tắt chế độ điều chỉnh CPU tự động
   - Chọn các API muốn sử dụng (Pexels, ThisPersonDoesNotExist, Picsum, TheCatAPI)
   - Cấu hình tốc độ tải xuống và số luồng cho mỗi API
   - Nhập tổng số lượng ảnh muốn tải

3. Theo dõi tiến trình:
   - Chương trình sẽ hiển thị bảng tiến độ
   - Thống kê theo từng nguồn
   - Ước tính thời gian hoàn thành

## Cấu trúc thư mục

```
Auto_Genator_Image_10KB/
│
├── download_landscape.py    # Mã nguồn chính
├── keyword.txt              # Danh sách từ khóa tìm kiếm cho Pexels
├── requirements.txt         # Danh sách thư viện cần thiết
├── README.md                # Tài liệu hướng dẫn
│
├── images/                  # Thư mục lưu ảnh đã tải (tạo tự động)
└── output/                  # Thư mục đầu ra (tạo tự động)
```

## API Key

Chương trình đã được cấu hình với API key mặc định cho Pexels và TheCatAPI. Tuy nhiên, bạn có thể sử dụng API key riêng của mình:

- **Pexels**: Đăng ký tại [Pexels API](https://www.pexels.com/api/) và cập nhật trong mã nguồn
- **TheCatAPI**: Đăng ký tại [TheCatAPI](https://thecatapi.com/) hoặc nhập key khi chạy chương trình

## Chi tiết kỹ thuật

### Thuật toán tối ưu hóa hình ảnh

1. **Phát hiện trùng lặp bằng perceptual hashing:**
   - Chuyển đổi ảnh sang grayscale
   - Resize xuống 8x8 pixel
   - Tính ngưỡng độ sáng trung bình
   - Tạo hash nhị phân dựa trên so sánh độ sáng
2. **Thuật toán tìm kiếm nhị phân cho chất lượng tối ưu:**
   - Thử nghiệm các mức chất lượng nén từ 5% đến 95%
   - Sử dụng tìm kiếm nhị phân để nhanh chóng tìm mức chất lượng cao nhất mà vẫn dưới 10KB
3. **Tối ưu hóa kích thước ảnh:**
   - Resize ảnh theo tỷ lệ khung hình
   - Tăng độ tương phản và độ sáng
   - Áp dụng bộ lọc làm sắc nét

### Quản lý đa luồng

- Sử dụng `ThreadPoolExecutor` để tạo và quản lý luồng
- Khóa đồng bộ hóa (`threading.Lock`) để bảo vệ tài nguyên dùng chung
- Quản lý lồng nhau các executor để kiểm soát tốc độ và tải

### Giám sát hiệu suất

- Đo thời gian hoàn thành
- Ước tính thời gian còn lại
- Tự động điều chỉnh tốc độ dựa trên tải CPU

## Điều chỉnh hiệu suất

- **Tốc độ tải xuống**: Tăng/giảm số ảnh mỗi giây cho từng API
- **Số luồng**: Điều chỉnh số luồng đồng thời cho mỗi API
- **Ngưỡng CPU**: Thiết lập ngưỡng CPU tối đa và mức mục tiêu
- **Chế độ debug**: Bật để xem thông tin chi tiết về quá trình tải xuống

## Đóng góp

Đóng góp và báo cáo lỗi rất được hoan nghênh! Vui lòng tạo issue hoặc pull request trên GitHub.

## Giấy phép

Dự án này được phân phối dưới giấy phép MIT. Xem file `LICENSE` để biết thêm chi tiết.
