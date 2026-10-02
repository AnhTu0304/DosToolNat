# Thiết kế Kỹ thuật: dos-tool — Giai đoạn 2 (Phase 2: Controlled HTTP Load Engine)

**Ngày lập:** 02/10/2026  
**Dự án:** `dos-tool`  
**Mục tiêu:** Xây dựng Engine tải HTTP có kiểm soát (Controlled HTTP Load Engine) để kiểm thử hiệu năng và độ ổn định của ứng dụng web được cấp quyền kiểm thử.  
**Phạm vi:** Triển khai Giai đoạn 2. Chỉ kiểm thử bằng phương thức HTTP GET, tuyệt đối không triển khai các tính năng phá hoại, không mutate dữ liệu (không POST/PUT/DELETE), không bypass bảo vệ (không WAF/proxy bypass).

---

## 1. Tổng quan & Yêu cầu kỹ thuật

### 1.1 Mục tiêu chính
- Bổ sung lệnh CLI `dos-tool load` với các tham số: `--target`, `--rate`, `--concurrency`, `--duration`, `--timeout`.
- Điều phối tải bằng `asyncio` kết hợp `httpx.AsyncClient`.
- Kiểm soát tốc độ request (RPS) đều đặn qua `RateScheduler`, tránh tình trạng dồn cục (bursting).
- Khống chế số kết nối đồng thời qua `asyncio.Semaphore`.
- Thu thập và phân loại chi tiết các trạng thái: HTTP 2xx, 3xx, 4xx, 5xx, Timeout, Connection Error.
- Tính toán chính xác độ trễ (latency ms): Min, Max, Average, P50, P95, P99 dựa trên công thức phân vị chuẩn.
- Cập nhật tiến độ theo thời gian thực (Rich Live Progress).
- Cơ chế dừng an toàn (Graceful Shutdown) khi hết thời gian hoặc khi người dùng ngắt bằng `Ctrl+C`.
- Báo cáo kết quả tổng kết có cấu trúc chuẩn dạng bảng và sẵn sàng xuất JSON/CSV (`LoadTestReport`).
- Thẩm định an toàn bắt buộc trước khi chạy: Từ chối ngay nếu tham số vượt quá ngưỡng cấu hình (`max_request_rate`, `max_concurrency`, `max_test_duration`, `request_timeout`).

### 1.2 Giới hạn an toàn (Safety Restrictions)
- Chỉ gửi request `GET`.
- Nghiêm cấm xoay vòng IP/proxy, tránh né WAF/CAPTCHA, bypass rate-limit, brute-force hoặc quét mục tiêu bên thứ ba.
- Ngưỡng an toàn mặc định:
  - `max_request_rate`: 100 req/s
  - `max_concurrency`: 20
  - `max_test_duration`: 60 s
  - `request_timeout`: 5.0 s

---

## 2. Kiến trúc các thành phần

```text
app/
├── cli.py                     # Cập nhật: thêm lệnh `load`, hiển thị Rich Live & Bảng kết quả
│
├── engine/
│   ├── __init__.py
│   ├── runner.py              # ConnectivityRunner (Phase 1) & LoadTestRunner (Phase 2)
│   ├── worker.py              # Worker thực thi async GET request, bắt lỗi, đo latency
│   └── scheduler.py           # RateScheduler điều phối nhịp độ phát request theo interval
│
├── metrics/
│   ├── __init__.py
│   ├── models.py              # RequestResult & LoadTestReport Pydantic models
│   └── collector.py           # MetricsCollector thread/async-safe, tính toán percentile
│
├── safety/
│   ├── __init__.py
│   └── controller.py          # Thẩm định URL và kiểm tra đa tham số giới hạn
│
└── config.py                  # Kế thừa cấu hình Phase 1
```

---

## 3. Chi tiết thiết kế Module

### 3.1 `app/metrics/models.py`
- `RequestResult`:
  - `timestamp: float`
  - `status_code: int | None`
  - `latency_ms: float`
  - `success: bool`
  - `timeout: bool`
  - `connection_error: bool`
  - `error_message: str | None`
- `LoadTestReport` (Pydantic Model):
  - `target: str`
  - `method: str = "GET"`
  - `requested_rate: float`
  - `actual_rate: float`
  - `concurrency: int`
  - `duration: float`
  - `total_requests: int`
  - `successful_requests: int`
  - `failed_requests: int`
  - `status_2xx: int`
  - `status_3xx: int`
  - `status_4xx: int`
  - `status_5xx: int`
  - `timeouts: int`
  - `connection_errors: int`
  - `min_latency: float`
  - `max_latency: float`
  - `average_latency: float`
  - `p50_latency: float`
  - `p95_latency: float`
  - `p99_latency: float`
  - `start_time: float`
  - `end_time: float`
  - `elapsed_time: float`

### 3.2 `app/metrics/collector.py`
- `MetricsCollector`:
  - Thu thập danh sách `RequestResult`.
  - Tính toán độ trễ sử dụng phương pháp tính phân vị chuẩn:
    - Nếu danh sách rỗng: trả về 0.0.
    - Sắp xếp mảng độ trễ: tính chỉ số phân vị chuẩn `k = (p / 100) * (n - 1)`, nội suy tuyến tính giữa các giá trị liền kề.
  - Phân loại mã HTTP:
    - 200–299: `status_2xx`
    - 300–399: `status_3xx`
    - 400–499: `status_4xx`
    - 500–599: `status_5xx`
  - Xuất báo cáo `build_report() -> LoadTestReport`.

### 3.3 `app/engine/worker.py`
- `execute_request(client: httpx.AsyncClient, target_url: str, semaphore: asyncio.Semaphore) -> RequestResult`:
  - Dùng `async with semaphore:` để giới hạn độ đồng thời.
  - Đo thời gian bằng `time.perf_counter()`.
  - Bắt các ngoại lệ: `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.RequestError`, `Exception`.
  - Không bao giờ để lỗi ngoại lệ làm crash engine tải.

### 3.4 `app/engine/scheduler.py`
- `RateScheduler`:
  - Khởi tạo với: `rate: float`, `duration: float`.
  - Phương thức sinh nhịp `generate_ticks()`:
    - Khoảng cách giữa 2 request: `interval = 1.0 / rate`.
    - Tính thời gian bắt đầu và kết thúc mục tiêu (`start_time + duration`).
    - Dùng `asyncio.sleep` tính toán bù trừ thời gian trôi (drift compensation) để đảm bảo phát đều đặn theo giây mà không dồn cục.
    - Hỗ trợ dừng tức thì khi gọi `stop()`.

### 3.5 `app/engine/runner.py`
- `LoadTestRunner`:
  - Điều phối `MetricsCollector`, `RateScheduler`, `Worker`, và client `httpx.AsyncClient`.
  - Hỗ trợ callback cập nhật tiến độ (Progress callback) phục vụ Rich Live UI.
  - Đón bắt tín hiệu ngắt (Cancel/Interrupt) để thực hiện Graceful Shutdown:
    - Đặt cờ dừng cho scheduler.
    - Đợi các task đang chạy trong vòng timeout ngắn hợp lý.
    - Tổng kết toàn bộ metrics thu được đến thời điểm dừng.

### 3.6 `app/safety/controller.py`
- Mở rộng phương thức `validate_load_parameters(rate: int, concurrency: int, duration: int, timeout: float)`:
  - Kiểm tra và gom toàn bộ các vi phạm nếu có, tạo thông báo chi tiết:
    ```text
    Safety validation failed.
    Requested rate: 1000 req/s (Maximum allowed: 100 req/s)
    Requested concurrency: 100 (Maximum allowed: 20)
    Requested duration: 120s (Maximum allowed: 60s)
    ```

### 3.7 `app/cli.py`
- Bổ sung lệnh `load`:
  - Gọi `SafetyController` trước tiên.
  - Hiển thị bảng tóm tắt thông số trước khi chạy.
  - Khởi chạy `LoadTestRunner` với giao diện tiến độ compact qua Rich.
  - Sau khi kết thúc, in bảng kết quả chi tiết `LOAD TEST RESULT`.
  - Trả về exit code 0 nếu test hoàn tất và tỷ lệ thành công tốt, exit code 1 nếu lỗi cấu hình / an toàn.

---

## 4. Kế hoạch Kiểm thử (TDD Strategy)

1. `tests/test_metrics.py`:
   - Tính toán min, max, avg, P50, P95, P99 với tập dữ liệu đã biết trước.
   - Xử lý khi tập kết quả rỗng.
   - Phân loại đúng mã HTTP 2xx, 3xx, 4xx, 5xx, timeout, connect_error.
   - Kiểm tra khả năng serialize sang dict / JSON của `LoadTestReport`.
2. `tests/test_scheduler.py`:
   - Kiểm tra số lượng nhịp phát ra xấp xỉ `rate * duration`.
   - Kiểm tra khả năng dừng sớm khi gọi `stop()`.
3. `tests/test_load_engine.py`:
   - Chạy tải giả lập với `httpx.MockTransport` (async).
   - Kiểm tra concurrency không vượt quá giới hạn semaphore.
   - Kiểm tra xử lý hỗn hợp (vừa có 200, 404, 500, vừa có timeout và connect error).
   - Kiểm tra Graceful Shutdown khi bị cancel giữa chừng.
4. `tests/test_safety.py`:
   - Kiểm tra từ chối đồng thời nhiều tham số vượt ngưỡng an toàn.
5. `tests/test_cli.py`:
   - Kiểm tra lệnh `dos-tool load --help`.
   - Kiểm tra lệnh `dos-tool load` bị từ chối khi vượt ngưỡng.
   - Kiểm tra lệnh `dos-tool load` chạy thành công với mock.
   - Bảo toàn các lệnh Phase 1 (`--help`, `version`, `config`, `test`).
