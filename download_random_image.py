import os
import requests
from PIL import Image, ImageFilter, ImageEnhance
from io import BytesIO
from pathlib import Path
import json
import hashlib
from datetime import datetime, timedelta
import concurrent.futures
import time
import threading
from colorama import init, Fore, Back, Style
from tabulate import tabulate
import random
import psutil

# Khởi tạo colorama
init()

class ImageDownloader:
    def __init__(self):
        self.api_key = "Ms9jiPvj8G1EviJwdgZGHd3Kztbo5fDbWWsEuHTujCa0SVL89oStHcqk"
        self.headers = {"Authorization": self.api_key}
        # API key cho TheCatAPI
        self.catapi_key = "live_kTZGJC9WjJwYQ12oGl2M95H8QOxEpV49KxO5sVy8QfHfRRkO0vVPLCQVoBaCLmPw"
        self.catapi_headers = {"x-api-key": self.catapi_key}
        self.downloaded_images = self.load_downloaded_images()
        self.downloaded_hashes = set()  # Thêm thuộc tính downloaded_hashes
        self.debug_mode = False  # Thêm thuộc tính debug_mode
        self.download_count = 0  # Thêm thuộc tính download_count
        self.total_downloaded = 0
        self.global_counter = self.get_last_counter()
        self.lock = threading.Lock()
        self.total_requested = 0
        self.total_successful = 0
        self.total_failed = 0
        self.start_time = None
        self.last_update_time = None
        self.last_successful_count = 0
        self.last_api_call = 0
        self.api_call_interval = 1.0
        self.rate_limit_reset = 0
        self.rate_limit_remaining = 0
        self.successful_by_source = {"pexels": 0, "thispersondoesnotexist": 0, "picsum": 0, "catapi": 0}
        self.download_speed = 1.0
        self.num_threads = 1
        self.thispersondoesnotexist_speed = 3.33  # 300ms = 3.33 ảnh/giây
        self.thispersondoesnotexist_threads = 10  # Số luồng mặc định cho thispersondoesnotexist
        self.picsum_speed = 3.33  # 300ms = 3.33 ảnh/giây
        self.picsum_threads = 10  # Số luồng mặc định cho picsum
        self.catapi_speed = 3.33  # 300ms = 3.33 ảnh/giây
        self.catapi_threads = 10  # Số luồng mặc định cho catapi
        self.apis_to_use = []  # Danh sách API được chọn
        self.cpu_threshold = 85  # Ngưỡng CPU cao (%)
        self.cpu_target = 60  # Mức CPU mục tiêu (%)
        self.adaptive_delay = 0.1  # Thời gian delay tự động (giây)
        self.adaptive_enabled = True  # Bật/tắt chế độ điều chỉnh CPU tự động
        
        # Tạo thư mục output nếu chưa tồn tại
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

    def get_last_counter(self):
        """Lấy số thứ tự cuối cùng từ thư mục output"""
        output_dir = Path("output")
        if not output_dir.exists():
            return 0
            
        max_counter = 0
        for file in output_dir.glob("IMG_*.jpg"):
            try:
                counter = int(file.stem.split('_')[1])
                max_counter = max(max_counter, counter)
            except (ValueError, IndexError):
                continue
        return max_counter
    
    def load_downloaded_images(self):
        """Tải danh sách ảnh đã tải về từ file"""
        try:
            with open("downloaded_images.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_downloaded_images(self):
        """Lưu danh sách ảnh đã tải về vào file"""
        with open("downloaded_images.json", "w") as f:
            json.dump(self.downloaded_images, f, indent=2)
    
    def calculate_image_hash(self, image):
        """Tính toán hash của ảnh để kiểm tra trùng lặp"""
        try:
            # Chuyển ảnh sang grayscale để dễ so sánh
            img_gray = image.convert('L')
            # Giảm kích thước để tăng tốc độ tính toán
            img_small = img_gray.resize((8, 8), Image.LANCZOS)
            # Lấy giá trị độ sáng của từng pixel
            pixels = list(img_small.getdata())
            # Tính ngưỡng trung bình
            avg = sum(pixels) / len(pixels)
            # Tạo hash nhị phân: 1 nếu pixel sáng hơn trung bình, 0 nếu ngược lại
            bits = ''.join('1' if pixel > avg else '0' for pixel in pixels)
            # Chuyển chuỗi bit thành số nguyên
            hash_value = int(bits, 2)
            return hash_value
        except Exception as e:
            self.debug_print(f"Lỗi khi tính toán hash ảnh: {str(e)}")
            # Trả về giá trị ngẫu nhiên nếu có lỗi để tránh trùng lặp
            return random.randint(1, 10**10)
    
    def is_duplicate(self, image_hash):
        """Kiểm tra xem ảnh đã được tải về chưa"""
        with self.lock:
            return image_hash in self.downloaded_hashes
    
    def download_image(self, url):
        """Tải ảnh từ URL"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                return image
        except Exception as e:
            print(f"Lỗi khi tải ảnh: {str(e)}")
        return None
    
    def resize_image(self, image, target_width=360, target_height=640):
        """Thay đổi kích thước ảnh với chất lượng tốt hơn"""
        # Tính tỷ lệ khung hình gốc
        original_ratio = image.width / image.height
        target_ratio = target_width / target_height
        
        # Cắt ảnh để phù hợp với tỷ lệ khung hình mới
        if original_ratio > target_ratio:
            # Ảnh rộng hơn, cắt hai bên
            new_width = int(image.height * target_ratio)
            left = (image.width - new_width) // 2
            image = image.crop((left, 0, left + new_width, image.height))
        else:
            # Ảnh cao hơn, cắt trên dưới
            new_height = int(image.width / target_ratio)
            top = (image.height - new_height) // 2
            image = image.crop((0, top, image.width, top + new_height))
        
        # Thay đổi kích thước
        return image.resize((target_width, target_height), Image.LANCZOS)
    
    def optimize_image(self, image):
        """Tối ưu hóa ảnh trước khi lưu"""
        # Chuyển đổi sang RGB nếu là ảnh RGBA
        if image.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Tăng độ tương phản và độ sáng
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.1)
        
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.05)
        
        # Áp dụng bộ lọc để cải thiện độ nét
        image = image.filter(ImageFilter.SHARPEN)
        
        return image
    
    def save_image(self, image_data, filename, source):
        """Lưu ảnh với kích thước tối đa là 10KB"""
        try:
            # Chuyển binary data thành đối tượng Image
            image = Image.open(BytesIO(image_data))
            
            # Chuyển ảnh sang RGB nếu có kênh Alpha để tránh lỗi
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3] if image.mode == 'RGBA' else None)
                image = background
            
            # Kiểm tra kích thước của ảnh và resize nếu cần
            width, height = image.size
            max_dimension = 800
            
            if width > max_dimension or height > max_dimension:
                if width > height:
                    new_width = max_dimension
                    new_height = int(height * (max_dimension / width))
                else:
                    new_height = max_dimension
                    new_width = int(width * (max_dimension / height))
                
                image = image.resize((new_width, new_height), Image.LANCZOS)
                self.debug_print(f"[{source}] Đã resize ảnh từ {width}x{height} xuống {new_width}x{new_height}")
            
            # Tính toán hash của ảnh để kiểm tra trùng lặp
            image_hash = self.calculate_image_hash(image)
            
            # Kiểm tra trùng lặp
            if self.is_duplicate(image_hash):
                self.debug_print(f"[{source}] Ảnh trùng lặp bỏ qua: {filename}")
                return False
            
            # Thêm hash vào danh sách đã tải
            with self.lock:
                self.downloaded_hashes.add(image_hash)
            
            # Đảm bảo thư mục tồn tại
            os.makedirs('images', exist_ok=True)
            
            # Binary search để tìm chất lượng tối ưu để ảnh dưới 10KB
            quality_low = 5
            quality_high = 95
            best_quality = 0
            best_image_data = None
            
            while quality_low <= quality_high:
                quality_mid = (quality_low + quality_high) // 2
                
                # Lưu ảnh tạm với chất lượng thử nghiệm
                temp_buffer = BytesIO()
                image.save(temp_buffer, format='JPEG', quality=quality_mid, optimize=True)
                temp_buffer.seek(0)
                current_size = len(temp_buffer.getvalue())
                
                if current_size <= 10240:  # 10KB = 10240 bytes
                    best_quality = quality_mid
                    best_image_data = temp_buffer.getvalue()
                    quality_low = quality_mid + 1
                else:
                    quality_high = quality_mid - 1
            
            if best_image_data:
                # Lưu ảnh với chất lượng tốt nhất đáp ứng yêu cầu kích thước
                file_path = os.path.join('images', f"{filename}.jpg")
                with open(file_path, 'wb') as f:
                    f.write(best_image_data)
                
                self.debug_print(f"[{source}] Lưu ảnh thành công: {file_path} (Chất lượng: {best_quality}%, Kích thước: {len(best_image_data)/1024:.2f}KB)")
                return True
            else:
                self.debug_print(f"[{source}] Không thể lưu ảnh dưới 10KB: {filename}")
                return False
                
        except Exception as e:
            self.debug_print(f"[{source}] Lỗi khi lưu ảnh {filename}: {str(e)}")
            return False
    
    def update_progress(self):
        """Cập nhật và hiển thị bảng tiến độ"""
        os.system('cls' if os.name == 'nt' else 'clear')  # Xóa màn hình
        
        # Tính thời gian ước tính còn lại
        current_time = time.time()
        if self.last_update_time and self.last_successful_count < self.total_successful:
            time_diff = current_time - self.last_update_time
            success_diff = self.total_successful - self.last_successful_count
            if success_diff > 0:
                time_per_image = time_diff / success_diff
                remaining_images = self.total_requested - self.total_successful
                estimated_seconds = remaining_images * time_per_image
                estimated_end = datetime.now() + timedelta(seconds=estimated_seconds)
                estimated_time = estimated_end.strftime("%H:%M:%S")
            else:
                estimated_time = "Đang tính toán..."
        else:
            estimated_time = "Đang tính toán..."
        
        self.last_update_time = current_time
        self.last_successful_count = self.total_successful
        
        # Bảng tiến độ chính
        main_table = [
            ["Tổng số Ảnh yêu cầu", "Số ảnh đã tải được", "Số ảnh tải thất bại"],
            [
                f"{Fore.GREEN}{self.total_requested}{Style.RESET_ALL}",
                f"{Fore.BLUE}{self.total_successful}{Style.RESET_ALL}",
                f"{Fore.RED}{self.total_failed}{Style.RESET_ALL}"
            ]
        ]
        print(tabulate(main_table, headers="firstrow", tablefmt="grid"))
        
        # Bảng thống kê theo nguồn
        source_table = [
            ["Nguồn", "Số ảnh", "Tỷ lệ"]
        ]
        
        # Chỉ hiển thị các nguồn đang được sử dụng
        if "pexels" in self.apis_to_use:
            source_table.append([
                f"{Fore.CYAN}Pexels{Style.RESET_ALL}",
                f"{self.successful_by_source['pexels']}",
                f"{(self.successful_by_source['pexels']/self.total_successful*100 if self.total_successful > 0 else 0):.1f}%"
            ])
            
        if "thispersondoesnotexist" in self.apis_to_use:
            source_table.append([
                f"{Fore.MAGENTA}ThisPersonDoesNotExist{Style.RESET_ALL}",
                f"{self.successful_by_source['thispersondoesnotexist']}",
                f"{(self.successful_by_source['thispersondoesnotexist']/self.total_successful*100 if self.total_successful > 0 else 0):.1f}%"
            ])
            
        if "picsum" in self.apis_to_use:
            source_table.append([
                f"{Fore.YELLOW}Picsum Photos{Style.RESET_ALL}",
                f"{self.successful_by_source['picsum']}",
                f"{(self.successful_by_source['picsum']/self.total_successful*100 if self.total_successful > 0 else 0):.1f}%"
            ])
            
        if "catapi" in self.apis_to_use:
            source_table.append([
                f"{Fore.GREEN}TheCatAPI{Style.RESET_ALL}",
                f"{self.successful_by_source['catapi']}",
                f"{(self.successful_by_source['catapi']/self.total_successful*100 if self.total_successful > 0 else 0):.1f}%"
            ])
        
        print("\nThống kê theo nguồn:")
        print(tabulate(source_table, headers="firstrow", tablefmt="grid"))
        
        print(f"\nTiến độ: {(self.total_successful/self.total_requested)*100:.2f}%")
        print(f"Thời gian kết thúc ước tính: {Fore.YELLOW}{estimated_time}{Style.RESET_ALL}")

    def download_from_thispersondoesnotexist(self):
        """Tải ảnh từ thispersondoesnotexist.com"""
        try:
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-US,en;q=0.9,vi;q=0.8',
                'cache-control': 'max-age=0',
                'dnt': '1',
                'priority': 'u=0, i',
                'referer': 'https://www.google.com/',
                'sec-ch-ua': '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'cross-site',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0'
            }
            
            response = requests.get("https://thispersondoesnotexist.com/", 
                                 headers=headers, 
                                 timeout=10)
            
            if response.status_code == 200:
                # Tạo ảnh trực tiếp từ response content
                image = Image.open(BytesIO(response.content))
                return image
            else:
                print(f"Lỗi khi tải ảnh từ thispersondoesnotexist: Status code {response.status_code}")
        except Exception as e:
            print(f"Lỗi khi tải ảnh từ thispersondoesnotexist: {str(e)}")
        return None

    def download_from_picsum(self):
        """Tải ảnh từ picsum.photos"""
        try:
            url = "https://picsum.photos/360/640"
            response = requests.get(url, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                # Tạo ảnh trực tiếp từ response content
                image = Image.open(BytesIO(response.content))
                return image
            else:
                if self.debug_mode:
                    print(f"[Picsum] Lỗi khi tải ảnh: Status code {response.status_code}")
        except Exception as e:
            if self.debug_mode:
                print(f"[Picsum] Lỗi khi tải ảnh: {str(e)}")
        return None

    def download_from_catapi(self):
        """Tải ảnh từ TheCatAPI"""
        try:
            # Lấy ngẫu nhiên một ảnh mèo từ TheCatAPI
            url = "https://api.thecatapi.com/v1/images/search?size=med"
            
            if self.debug_mode:
                print(f"[CatAPI] Đang gửi yêu cầu API...")
                
            response = requests.get(url, headers=self.catapi_headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    image_url = data[0]["url"]
                    if self.debug_mode:
                        print(f"[CatAPI] Tìm thấy ảnh: {image_url}")
                    
                    # Tải ảnh
                    img_response = requests.get(image_url, timeout=10)
                    if img_response.status_code == 200:
                        image = Image.open(BytesIO(img_response.content))
                        return image
                    else:
                        if self.debug_mode:
                            print(f"[CatAPI] Lỗi khi tải ảnh: Status code {img_response.status_code}")
                else:
                    if self.debug_mode:
                        print("[CatAPI] Không tìm thấy ảnh nào trong kết quả API")
            else:
                if self.debug_mode:
                    print(f"[CatAPI] Lỗi khi gọi API: Status code {response.status_code}")
                    print(f"Response: {response.text}")
        except Exception as e:
            if self.debug_mode:
                print(f"[CatAPI] Lỗi khi tải ảnh: {str(e)}")
        return None

    def process_single_image(self, source):
        """Xử lý việc tải và lưu một ảnh từ nguồn cụ thể."""
        try:
            if source == "thispersondoesnotexist":
                url = "https://thispersondoesnotexist.com"
                self.debug_print(f"[ThisPersonDoesNotExist] Đang tải ảnh từ {url}")
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    timestamp = int(time.time() * 1000)
                    filename = f"person_{timestamp}"
                    with self.lock:
                        self.total_successful += 1
                        self.successful_by_source["thispersondoesnotexist"] += 1
                    success = self.save_image(response.content, filename, source)
                    if success:
                        self.debug_print(f"[ThisPersonDoesNotExist] Đã tải thành công ảnh")
                        self.update_progress()
                    return success
                else:
                    self.debug_print(f"[ThisPersonDoesNotExist] Lỗi khi tải ảnh: {response.status_code}")
            
            elif source == "picsum":
                width = 800
                height = 600
                timestamp = int(time.time() * 1000)
                url = f"https://picsum.photos/{width}/{height}?random={timestamp}"
                self.debug_print(f"[Picsum] Đang tải ảnh từ {url}")
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    filename = f"picsum_{timestamp}"
                    with self.lock:
                        self.total_successful += 1
                        self.successful_by_source["picsum"] += 1
                    success = self.save_image(response.content, filename, source)
                    if success:
                        self.debug_print(f"[Picsum] Đã tải thành công ảnh")
                        self.update_progress()
                    return success
                else:
                    self.debug_print(f"[Picsum] Lỗi khi tải ảnh: {response.status_code}")
            
            elif source == "catapi":
                url = "https://api.thecatapi.com/v1/images/search"
                headers = {"x-api-key": self.catapi_key}
                self.debug_print(f"[TheCatAPI] Đang gửi yêu cầu đến {url}")
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        img_url = data[0]["url"]
                        self.debug_print(f"[TheCatAPI] Đang tải ảnh từ {img_url}")
                        img_response = requests.get(img_url, timeout=10)
                        if img_response.status_code == 200:
                            timestamp = int(time.time() * 1000)
                            filename = f"cat_{timestamp}"
                            with self.lock:
                                self.total_successful += 1
                                self.successful_by_source["catapi"] += 1
                            success = self.save_image(img_response.content, filename, source)
                            if success:
                                self.debug_print(f"[TheCatAPI] Đã tải thành công ảnh")
                                self.update_progress()
                            return success
                        else:
                            self.debug_print(f"[TheCatAPI] Lỗi khi tải ảnh: {img_response.status_code}")
                    else:
                        self.debug_print(f"[TheCatAPI] Không tìm thấy ảnh trong phản hồi API")
                else:
                    self.debug_print(f"[TheCatAPI] Lỗi khi truy vấn API: {response.status_code}")
            
            else:
                self.debug_print(f"Nguồn không được hỗ trợ: {source}")
                
            with self.lock:
                self.total_failed += 1
            self.update_progress()
                
        except Exception as e:
            self.debug_print(f"[{source.capitalize()}] Lỗi khi xử lý ảnh: {str(e)}")
            with self.lock:
                self.total_failed += 1
            self.update_progress()
        
        return False

    def adjust_cpu_load(self):
        """Điều chỉnh tải CPU bằng cách thay đổi thời gian chờ"""
        if not self.adaptive_enabled:
            return
            
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            if cpu_percent > self.cpu_threshold:
                # Tăng thời gian chờ nếu CPU quá cao
                self.adaptive_delay += 0.05
                if self.debug_mode:
                    print(f"\n[CPU] Đang cao: {cpu_percent:.1f}%, tăng delay lên {self.adaptive_delay:.2f}s")
                time.sleep(self.adaptive_delay)
            elif cpu_percent > self.cpu_target and self.adaptive_delay > 0.1:
                # Giữ delay hiện tại nếu CPU vẫn cao hơn mức mục tiêu
                if self.debug_mode and random.random() < 0.01:  # Chỉ in log 1% thời gian để giảm tải
                    print(f"\n[CPU] Vẫn cao: {cpu_percent:.1f}%, giữ delay ở {self.adaptive_delay:.2f}s")
                time.sleep(self.adaptive_delay)
            elif self.adaptive_delay > 0.1:
                # Giảm thời gian chờ dần dần nếu CPU ổn định
                self.adaptive_delay = max(0.1, self.adaptive_delay - 0.01)
                if self.debug_mode and random.random() < 0.01:
                    print(f"\n[CPU] Ổn định: {cpu_percent:.1f}%, giảm delay xuống {self.adaptive_delay:.2f}s")
        except Exception:
            # Bỏ qua lỗi nếu có
            pass

    def wait_for_rate_limit(self):
        """Đợi cho đến khi có thể gọi API tiếp"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        
        if time_since_last_call < self.api_call_interval:
            sleep_time = self.api_call_interval - time_since_last_call
            time.sleep(sleep_time)
        
        if self.rate_limit_remaining <= 0 and self.rate_limit_reset > current_time:
            sleep_time = self.rate_limit_reset - current_time
            print(f"\nĐã hết giới hạn API. Đợi {sleep_time:.1f} giây...")
            time.sleep(sleep_time)
        
        self.last_api_call = time.time()

    def update_rate_limit(self, response):
        """Cập nhật thông tin rate limit từ response"""
        if 'X-RateLimit-Reset' in response.headers:
            self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])
        if 'X-RateLimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])

    def make_api_request(self, url, params):
        """Thực hiện yêu cầu API với rate limiting"""
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.wait_for_rate_limit()
                if self.debug_mode:
                    print(f"\n[Pexels] Đang gửi yêu cầu API lần {attempt + 1}...")
                    print(f"URL: {url}")
                    print(f"Params: {params}")
                
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
                self.update_rate_limit(response)
                
                if response.status_code == 200:
                    if self.debug_mode:
                        print(f"[Pexels] Yêu cầu API thành công!")
                    return response
                elif response.status_code == 429:
                    if 'Retry-After' in response.headers:
                        retry_after = int(response.headers['Retry-After'])
                        print(f"\n[Pexels] API đã bị giới hạn. Đợi {retry_after} giây...")
                        time.sleep(retry_after)
                    else:
                        print(f"\n[Pexels] API đã bị giới hạn. Thử lại sau {retry_delay} giây...")
                        time.sleep(retry_delay * (attempt + 1))
                else:
                    print(f"\n[Pexels] Lỗi API: {response.status_code}")
                    print(f"Response: {response.text}")
                    time.sleep(retry_delay)
            except Exception as e:
                print(f"\n[Pexels] Lỗi kết nối: {str(e)}")
                time.sleep(retry_delay)
        
        return None

    def download_and_process_images(self, query, count):
        """Tải và xử lý ảnh"""
        if not self.start_time:
            self.start_time = time.time()
            
        search_url = "https://api.pexels.com/v1/search"
        page = 1
        successful_downloads = 0
        max_retries = 3
        
        if self.debug_mode:
            print(f"\n[Pexels] Bắt đầu tải ảnh cho từ khóa '{query}'")
            print(f"Số lượng ảnh cần tải: {count}")
        
        while successful_downloads < count and max_retries > 0:
            params = {
                "query": query,
                "per_page": min(40, (count - successful_downloads) * 2),
                "page": page,
                "size": "large"
            }
            
            response = self.make_api_request(search_url, params)
            if not response:
                max_retries -= 1
                if max_retries > 0:
                    print(f"\n[Pexels] Không thể kết nối API. Còn {max_retries} lần thử...")
                    time.sleep(5)
                    continue
                break
            
            try:
                data = response.json()
                if self.debug_mode:
                    print(f"\n[Pexels] Đã nhận được {len(data.get('photos', []))} ảnh từ API")
                
                if data["photos"]:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = []
                        for photo in data["photos"]:
                            if successful_downloads >= count:
                                break
                            futures.append(executor.submit(self.process_single_image, photo["source"]))
                        
                        for future in concurrent.futures.as_completed(futures):
                            if successful_downloads >= count:
                                break
                            try:
                                result = future.result()
                                if result:
                                    successful_downloads += 1
                                    if self.debug_mode:
                                        print(f"[Pexels] Đã tải thành công ảnh {successful_downloads}/{count}")
                            except Exception as e:
                                print(f"[Pexels] Lỗi khi xử lý ảnh: {str(e)}")
                                with self.lock:
                                    self.total_failed += 1
                                    self.update_progress()
                else:
                    max_retries -= 1
                    if max_retries > 0:
                        print(f"\n[Pexels] Không tìm thấy ảnh phù hợp cho '{query}'. Còn {max_retries} lần thử...")
                        time.sleep(2)
                        continue
                    break
                    
            except Exception as e:
                max_retries -= 1
                if max_retries > 0:
                    print(f"\n[Pexels] Lỗi xử lý dữ liệu: {str(e)}. Còn {max_retries} lần thử...")
                    time.sleep(2)
                    continue
                break
                
            page += 1
            if page > 100:
                break
            
            time.sleep(random.uniform(0.5, 1.5))
        
        if successful_downloads < count:
            print(f"\n[Pexels] Không thể tải đủ {count} ảnh cho từ khóa '{query}'. Đã tải được {successful_downloads} ảnh.")
        
        self.save_downloaded_images()
        return successful_downloads

    def download_from_pexels(self, keywords, total_count):
        """Tải ảnh từ Pexels"""
        if "pexels" not in self.apis_to_use:
            return
            
        remaining_pexels = total_count
        keyword_index = 0
        
        while remaining_pexels > 0 and keyword_index < len(keywords):
            keyword = keywords[keyword_index]
            count = min(remaining_pexels, 100)  # Tải tối đa 100 ảnh mỗi lần
            if self.debug_mode:
                print(f"\n[Pexels] Đang tải {count} ảnh cho từ khóa '{keyword}'...")
            try:
                successful = self.download_and_process_images(keyword, count)
                remaining_pexels -= successful
                
                if successful == 0:
                    keyword_index += 1  # Chuyển sang từ khóa tiếp theo nếu không tải được ảnh nào
                    if self.debug_mode:
                        print(f"[Pexels] Không tải được ảnh nào cho từ khóa '{keyword}'. Chuyển sang từ khóa tiếp theo.")
                else:
                    keyword_index = 0  # Quay lại từ khóa đầu tiên nếu tải thành công
                    if self.debug_mode:
                        print(f"[Pexels] Đã tải thành công {successful} ảnh cho từ khóa '{keyword}'")
            except Exception as e:
                print(f"[Pexels] Lỗi khi tải ảnh: {str(e)}")
                keyword_index += 1  # Chuyển sang từ khóa tiếp theo nếu có lỗi

    def debug_print(self, message):
        """In thông điệp gỡ lỗi nếu chế độ debug được bật"""
        if hasattr(self, 'debug_mode') and self.debug_mode:
            print(message)

def read_keywords():
    """Đọc từ khóa từ file keyword.txt"""
    try:
        with open("keyword.txt", "r", encoding="utf-8") as f:
            content = f.read().strip()
            keywords = [kw.strip() for kw in content.split(",")]
            return keywords
    except FileNotFoundError:
        print("Không tìm thấy file keyword.txt")
        return []
    except Exception as e:
        print(f"Lỗi khi đọc file keyword.txt: {str(e)}")
        return []

def main():
    print("\n===== CHƯƠNG TRÌNH TẢI ẢNH TỰ ĐỘNG =====\n")
    
    # Tạo các thư mục cần thiết
    os.makedirs('images', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    
    # Kiểm tra thư viện psutil
    try:
        import psutil
    except ImportError:
        print("\nĐang cài đặt thư viện psutil để giám sát CPU...")
        try:
            import subprocess
            subprocess.check_call(["pip", "install", "psutil"])
            print("Đã cài đặt psutil thành công!")
            import psutil
        except Exception as e:
            print(f"Không thể cài đặt psutil: {str(e)}")
            print("Chương trình vẫn sẽ chạy nhưng không thể tối ưu hóa CPU.")
    
    # Hỏi người dùng có muốn bật chế độ debug không
    debug_mode = input("Bạn có muốn bật chế độ debug không? (y/n): ").lower() == 'y'
    
    if debug_mode:
        print("\n=== CHẾ ĐỘ DEBUG ĐÃ ĐƯỢC BẬT ===")
        print("Các thông tin chi tiết sẽ được hiển thị")
        print("="*30 + "\n")
    
    # Khởi tạo đối tượng downloader
    downloader = ImageDownloader()
    downloader.debug_mode = debug_mode
    
    # Hỏi về chế độ điều chỉnh CPU tự động
    auto_cpu = input("\nBạn có muốn bật chế độ điều chỉnh CPU tự động không? (y/n): ").lower() == 'y'
    downloader.adaptive_enabled = auto_cpu
    
    if auto_cpu:
        # Hỏi về ngưỡng CPU tối đa
        try:
            cpu_threshold = float(input("\nNhập ngưỡng CPU tối đa (%) (70-95): "))
            if 70 <= cpu_threshold <= 95:
                downloader.cpu_threshold = cpu_threshold
            else:
                print("Giá trị không hợp lệ. Sử dụng giá trị mặc định 85%")
        except ValueError:
            print("Giá trị không hợp lệ. Sử dụng giá trị mặc định 85%")
        
        # Hỏi về mức CPU mục tiêu
        try:
            cpu_target = float(input("\nNhập mức CPU mục tiêu (%) (40-70): "))
            if 40 <= cpu_target <= 70:
                downloader.cpu_target = cpu_target
            else:
                print("Giá trị không hợp lệ. Sử dụng giá trị mặc định 60%")
        except ValueError:
            print("Giá trị không hợp lệ. Sử dụng giá trị mặc định 60%")
    
    # Hỏi người dùng muốn sử dụng API nào
    print("\nCác API có sẵn:")
    print("1. Pexels (Có giới hạn API)")
    print("2. ThisPersonDoesNotExist (Không giới hạn)")
    print("3. Picsum Photos (Không giới hạn)")
    print("4. TheCatAPI (Ảnh mèo, có giới hạn API)")
    
    apis_to_use = []
    while True:
        api_choice = input("\nChọn các API muốn sử dụng (VD: 1,2,3,4 hoặc 2,3,4): ")
        choices = [choice.strip() for choice in api_choice.split(',')]
        
        valid_choices = True
        for choice in choices:
            if choice not in ['1', '2', '3', '4']:
                valid_choices = False
                print("Lựa chọn không hợp lệ. Vui lòng chọn 1, 2, 3 hoặc 4.")
                break
        
        if valid_choices:
            if '1' in choices:
                apis_to_use.append("pexels")
            if '2' in choices:
                apis_to_use.append("thispersondoesnotexist")
            if '3' in choices:
                apis_to_use.append("picsum")
            if '4' in choices:
                apis_to_use.append("catapi")
            
            if apis_to_use:
                break
            else:
                print("Vui lòng chọn ít nhất một API.")
    
    downloader.apis_to_use = apis_to_use
    
    # Cài đặt cho Pexels nếu được chọn
    if "pexels" in apis_to_use:
        # Hỏi người dùng về tốc độ tải cho Pexels
        while True:
            try:
                download_speed = float(input("\nNhập tốc độ tải cho Pexels (ảnh/giây, ví dụ: 1.0): "))
                if download_speed > 0:
                    break
                print("Tốc độ phải lớn hơn 0")
            except ValueError:
                print("Vui lòng nhập số")
        
        # Hỏi người dùng về số luồng tải cho Pexels
        while True:
            try:
                num_threads = int(input("Nhập số luồng tải cho Pexels (1-10): "))
                if 1 <= num_threads <= 10:
                    break
                print("Số luồng phải nằm trong khoảng 1-10")
            except ValueError:
                print("Vui lòng nhập số")
        
        downloader.download_speed = download_speed
        downloader.num_threads = num_threads
    
    # Cài đặt cho ThisPersonDoesNotExist nếu được chọn
    if "thispersondoesnotexist" in apis_to_use:
        # Hỏi người dùng về tốc độ tải cho ThisPersonDoesNotExist
        while True:
            try:
                thispersondoesnotexist_speed = float(input("\nNhập tốc độ tải cho ThisPersonDoesNotExist (ảnh/giây, ví dụ: 3.33 = 300ms): "))
                if thispersondoesnotexist_speed > 0:
                    break
                print("Tốc độ phải lớn hơn 0")
            except ValueError:
                print("Vui lòng nhập số")
        
        # Hỏi người dùng về số luồng tải cho ThisPersonDoesNotExist
        while True:
            try:
                thispersondoesnotexist_threads = int(input("Nhập số luồng tải cho ThisPersonDoesNotExist (1-20): "))
                if 1 <= thispersondoesnotexist_threads <= 20:
                    break
                print("Số luồng phải nằm trong khoảng 1-20")
            except ValueError:
                print("Vui lòng nhập số")
        
        downloader.thispersondoesnotexist_speed = thispersondoesnotexist_speed
        downloader.thispersondoesnotexist_threads = thispersondoesnotexist_threads
    
    # Cài đặt cho Picsum nếu được chọn
    if "picsum" in apis_to_use:
        # Hỏi người dùng về tốc độ tải cho Picsum
        while True:
            try:
                picsum_speed = float(input("\nNhập tốc độ tải cho Picsum Photos (ảnh/giây, ví dụ: 3.33 = 300ms): "))
                if picsum_speed > 0:
                    break
                print("Tốc độ phải lớn hơn 0")
            except ValueError:
                print("Vui lòng nhập số")
        
        # Hỏi người dùng về số luồng tải cho Picsum
        while True:
            try:
                picsum_threads = int(input("Nhập số luồng tải cho Picsum Photos (1-20): "))
                if 1 <= picsum_threads <= 20:
                    break
                print("Số luồng phải nằm trong khoảng 1-20")
            except ValueError:
                print("Vui lòng nhập số")
        
        downloader.picsum_speed = picsum_speed
        downloader.picsum_threads = picsum_threads
    
    # Cài đặt cho TheCatAPI nếu được chọn
    if "catapi" in apis_to_use:
        # Hỏi người dùng về tốc độ tải cho TheCatAPI
        while True:
            try:
                catapi_speed = float(input("\nNhập tốc độ tải cho TheCatAPI (ảnh/giây, ví dụ: 3.33 = 300ms): "))
                if catapi_speed > 0:
                    break
                print("Tốc độ phải lớn hơn 0")
            except ValueError:
                print("Vui lòng nhập số")
        
        # Hỏi người dùng về số luồng tải cho TheCatAPI
        while True:
            try:
                catapi_threads = int(input("Nhập số luồng tải cho TheCatAPI (1-20): "))
                if 1 <= catapi_threads <= 20:
                    break
                print("Số luồng phải nằm trong khoảng 1-20")
            except ValueError:
                print("Vui lòng nhập số")
        
        # Nhập API key TheCatAPI tùy chọn
        custom_key = input("\nNhập API key của TheCatAPI (để trống để sử dụng key mặc định): ").strip()
        if custom_key:
            downloader.catapi_key = custom_key
            downloader.catapi_headers = {"x-api-key": custom_key}
            print("Đã cập nhật API key cho TheCatAPI")
        
        downloader.catapi_speed = catapi_speed
        downloader.catapi_threads = catapi_threads
    
    # Hỏi người dùng tổng số lượng ảnh muốn tải
    while True:
        try:
            total_count = int(input("\nNhập tổng số lượng ảnh muốn tải (ví dụ: 100000): "))
            if total_count > 0:
                break
            print("Số lượng ảnh phải lớn hơn 0")
        except ValueError:
            print("Vui lòng nhập số")
    
    # Đọc từ khóa từ file (chỉ cần nếu sử dụng Pexels)
    keywords = []
    if "pexels" in apis_to_use:
        if debug_mode:
            print("\nĐang đọc từ khóa từ file keyword.txt...")
        keywords = read_keywords()
        if not keywords:
            print("Không có từ khóa nào để tải ảnh. Vui lòng kiểm tra file keyword.txt")
            return
        if debug_mode:
            print(f"Đã đọc được {len(keywords)} từ khóa: {', '.join(keywords)}")
    
    # Cập nhật tổng số ảnh yêu cầu
    downloader.total_requested = total_count
    downloader.start_time = time.time()
    
    # Phân phối ảnh đều cho tất cả nguồn đã chọn
    counts = {}
    api_count = len(apis_to_use)
    per_api_count = total_count // api_count
    remainder = total_count % api_count
    
    for i, api in enumerate(apis_to_use):
        counts[api] = per_api_count
        if i < remainder:
            counts[api] += 1
    
    percents = {}
    for api in apis_to_use:
        percents[api] = int(counts[api] / total_count * 100)
    
    if debug_mode:
        print(f"\nSố lượng ảnh sẽ tải:")
        for api in apis_to_use:
            print(f"- Từ {api}: {counts[api]} ảnh ({percents[api]}%)")
        
        print(f"\nCài đặt tốc độ tải:")
        if "pexels" in apis_to_use:
            print(f"- Pexels: {downloader.download_speed} ảnh/giây, {downloader.num_threads} luồng")
        if "thispersondoesnotexist" in apis_to_use:
            print(f"- ThisPersonDoesNotExist: {downloader.thispersondoesnotexist_speed} ảnh/giây ({1000/downloader.thispersondoesnotexist_speed:.0f}ms), {downloader.thispersondoesnotexist_threads} luồng")
        if "picsum" in apis_to_use:
            print(f"- Picsum Photos: {downloader.picsum_speed} ảnh/giây ({1000/downloader.picsum_speed:.0f}ms), {downloader.picsum_threads} luồng")
        if "catapi" in apis_to_use:
            print(f"- TheCatAPI: {downloader.catapi_speed} ảnh/giây ({1000/downloader.catapi_speed:.0f}ms), {downloader.catapi_threads} luồng")
    
    # Hiển thị tiến độ ban đầu
    downloader.update_progress()
    
    # Tải song song từ tất cả các nguồn được chọn
    if debug_mode:
        print("\nBắt đầu tải song song từ các nguồn đã chọn...")
        if downloader.adaptive_enabled:
            print(f"Chế độ điều chỉnh CPU tự động: Đã bật")
            print(f"Ngưỡng CPU tối đa: {downloader.cpu_threshold}%")
            print(f"Mức CPU mục tiêu: {downloader.cpu_target}%")
        else:
            print(f"Chế độ điều chỉnh CPU tự động: Đã tắt")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(apis_to_use)) as executor:
        futures = []
        
        if "pexels" in apis_to_use and counts["pexels"] > 0:
            futures.append(executor.submit(downloader.download_from_pexels, keywords, counts["pexels"]))
        
        if "thispersondoesnotexist" in apis_to_use and counts["thispersondoesnotexist"] > 0:
            # Tạo hàm cục bộ để tải ảnh từ ThisPersonDoesNotExist
            def download_from_thispersondoesnotexist_wrapper():
                remaining = counts["thispersondoesnotexist"]
                with concurrent.futures.ThreadPoolExecutor(max_workers=downloader.thispersondoesnotexist_threads) as ex:
                    futures_local = set()
                    batch_size = min(50, remaining)
                    
                    # Tạo lô tác vụ đầu tiên
                    for _ in range(batch_size):
                        if remaining <= 0:
                            break
                        futures_local.add(ex.submit(downloader.process_single_image, source="thispersondoesnotexist"))
                        remaining -= 1
                    
                    # Xử lý và tạo thêm tác vụ khi cần
                    while futures_local and remaining > 0:
                        done, futures_local = concurrent.futures.wait(
                            futures_local, 
                            return_when=concurrent.futures.FIRST_COMPLETED
                        )
                        
                        # Thêm tác vụ mới vào hàng đợi
                        new_batch = min(len(done), remaining)
                        for _ in range(new_batch):
                            futures_local.add(ex.submit(downloader.process_single_image, source="thispersondoesnotexist"))
                            remaining -= 1
                        
                        # Áp dụng tốc độ tải
                        if not downloader.adaptive_enabled:
                            time.sleep(1/downloader.thispersondoesnotexist_speed)
            
            futures.append(executor.submit(download_from_thispersondoesnotexist_wrapper))
        
        if "picsum" in apis_to_use and counts["picsum"] > 0:
            # Tạo hàm cục bộ để tải ảnh từ Picsum
            def download_from_picsum_wrapper():
                remaining = counts["picsum"]
                with concurrent.futures.ThreadPoolExecutor(max_workers=downloader.picsum_threads) as ex:
                    futures_local = set()
                    batch_size = min(50, remaining)
                    
                    # Tạo lô tác vụ đầu tiên
                    for _ in range(batch_size):
                        if remaining <= 0:
                            break
                        futures_local.add(ex.submit(downloader.process_single_image, source="picsum"))
                        remaining -= 1
                    
                    # Xử lý và tạo thêm tác vụ khi cần
                    while futures_local and remaining > 0:
                        done, futures_local = concurrent.futures.wait(
                            futures_local, 
                            return_when=concurrent.futures.FIRST_COMPLETED
                        )
                        
                        # Thêm tác vụ mới vào hàng đợi
                        new_batch = min(len(done), remaining)
                        for _ in range(new_batch):
                            futures_local.add(ex.submit(downloader.process_single_image, source="picsum"))
                            remaining -= 1
                        
                        # Áp dụng tốc độ tải
                        if not downloader.adaptive_enabled:
                            time.sleep(1/downloader.picsum_speed)
            
            futures.append(executor.submit(download_from_picsum_wrapper))
            
        if "catapi" in apis_to_use and counts["catapi"] > 0:
            # Tạo hàm cục bộ để tải ảnh từ TheCatAPI
            def download_from_catapi_wrapper():
                remaining = counts["catapi"]
                with concurrent.futures.ThreadPoolExecutor(max_workers=downloader.catapi_threads) as ex:
                    futures_local = set()
                    batch_size = min(50, remaining)
                    
                    # Tạo lô tác vụ đầu tiên
                    for _ in range(batch_size):
                        if remaining <= 0:
                            break
                        futures_local.add(ex.submit(downloader.process_single_image, source="catapi"))
                        remaining -= 1
                    
                    # Xử lý và tạo thêm tác vụ khi cần
                    while futures_local and remaining > 0:
                        done, futures_local = concurrent.futures.wait(
                            futures_local, 
                            return_when=concurrent.futures.FIRST_COMPLETED
                        )
                        
                        # Thêm tác vụ mới vào hàng đợi
                        new_batch = min(len(done), remaining)
                        for _ in range(new_batch):
                            futures_local.add(ex.submit(downloader.process_single_image, source="catapi"))
                            remaining -= 1
                        
                        # Áp dụng tốc độ tải
                        if not downloader.adaptive_enabled:
                            time.sleep(1/downloader.catapi_speed)
            
            futures.append(executor.submit(download_from_catapi_wrapper))
        
        # Đợi tất cả các quá trình hoàn thành
        concurrent.futures.wait(futures)
    
    # Hiển thị kết quả cuối cùng
    print("\n" + "="*50)
    print(f"Tổng kết:")
    print(f"Tổng số ảnh yêu cầu: {Fore.GREEN}{total_count}{Style.RESET_ALL}")
    print(f"Số ảnh đã tải thành công: {Fore.BLUE}{downloader.total_successful}{Style.RESET_ALL}")
    print(f"Số ảnh tải thất bại: {Fore.RED}{downloader.total_failed}{Style.RESET_ALL}")
    print(f"Tỷ lệ thành công: {Fore.CYAN}{(downloader.total_successful/total_count)*100:.2f}%{Style.RESET_ALL}")
    print(f"Thời gian thực hiện: {Fore.YELLOW}{timedelta(seconds=int(time.time() - downloader.start_time))}{Style.RESET_ALL}")
    print("="*50)

if __name__ == "__main__":
    main() 
