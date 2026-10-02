# Thiết kế Kỹ thuật: dos-tool — Giai đoạn 1 (Phase 1: Project Foundation)

**Ngày lập:** 02/10/2026  
**Dự án:** `dos-tool`  
**Mục tiêu:** Xây dựng nền tảng khung cho công cụ kiểm thử tải và khả năng chịu tải HTTP (controlled HTTP/DoS testing tool) cho các ứng dụng web thuộc quyền sở hữu hoặc được cấp quyền rõ ràng.  
**Phạm vi:** Chỉ triển khai Giai đoạn 1 (Foundation). KHÔNG triển khai engine tạo tải cao hoặc tính năng tấn công.

---

## 1. Tổng quan & Phạm vi dự án

### 1.1 Mục đích
`dos-tool` là dự án Python độc lập, không phụ thuộc vào hệ thống AI Self-Healing bên ngoài.
Giai đoạn 1 xây dựng:
- Cấu trúc dự án Python sạch, tương thích môi trường ảo (`venv`).
- Giao diện dòng lệnh CLI (Typer + Rich).
- Quản lý cấu hình linh hoạt (Pydantic V2 + PyYAML).
- Bộ điều khiển an toàn (`SafetyController`) thẩm định thông số trước khi thực hiện.
- Hệ thống ghi log có cấu trúc, không rò rỉ dữ liệu nhạy cảm.
- Kiểm tra kết nối HTTP cơ bản (1 request GET duy nhất bằng `httpx`).
- Bộ unit test toàn diện (pytest + mock).
- Tài liệu README và cấu hình Git.

### 1.2 Giới hạn nghiêm ngặt (Non-Goals trong Phase 1)
- KHÔNG tạo lưu lượng lớn (high-volume request generation), không flooding.
- KHÔNG có concurrent attack workers hoặc distributed attack.
- KHÔNG xoay vòng IP/proxy, không bypass WAF/CAPTCHA/Rate-limit.
- KHÔNG dùng Django, FastAPI hay cơ sở dữ liệu.
- KHÔNG có web dashboard.

---

## 2. Kiến trúc & Cấu trúc thư mục

### 2.1 Cây thư mục dự án
```text
dos-tool/ (tại root D:\natdostool)
│
├── app/
│   ├── __init__.py           # __version__ = "0.1.0"
│   ├── cli.py                # Typer CLI commands: test, config, version
│   ├── config.py             # AppConfig Pydantic model & YAML loader
│   │
│   ├── engine/
│   │   ├── __init__.py
│   │   └── runner.py         # ConnectivityRunner & ConnectivityResult
│   │
│   ├── scenarios/
│   │   └── __init__.py       # Placeholder chuẩn bị cho Phase 3
│   │
│   ├── metrics/
│   │   └── __init__.py       # Placeholder chuẩn bị cho Phase 4
│   │
│   └── safety/
│       ├── __init__.py
│       └── controller.py     # SafetyController & SafetyValidationError
│
├── configs/
│   └── config.yaml           # File cấu hình mẫu với các ngưỡng an toàn
│
├── scenarios/                # Thư mục lưu kịch bản
├── reports/                  # Thư mục xuất báo cáo
│
├── tests/
│   ├── __init__.py
│   ├── test_config.py        # Test nạp & xác thực cấu hình
│   ├── test_safety.py        # Test kiểm tra an toàn URL và các giới hạn
│   └── test_http.py          # Test HTTP connectivity client với mock
│
├── docs/
│   └── superpowers/specs/    # Tài liệu thiết kế kỹ thuật
│
├── requirements.txt
├── .gitignore
├── README.md
└── pyproject.toml
```

---

## 3. Chi tiết các thành phần (Component Design)

### 3.1 Cấu hình (`app/config.py` & `configs/config.yaml`)
- Sử dụng **Pydantic V2** (`BaseModel`, `Field`, `field_validator`).
- Các trường cấu hình:
  - `target_url: str` (Mặc định: `"http://localhost:8000"`)
  - `request_timeout: float` (Mặc định: `5.0` giây)
  - `max_test_duration: int` (Mặc định: `60` giây)
  - `max_request_rate: int` (Mặc định: `100` req/s)
  - `max_concurrency: int` (Mặc định: `20`)
  - `log_level: str` (Mặc định: `"INFO"`, các mức: DEBUG, INFO, WARNING, ERROR)
- Hàm `load_config(path: Path | str | None) -> AppConfig`: Đọc file YAML nếu tồn tại, kết hợp fallback giá trị mặc định. Nếu file lỗi cú pháp, báo lỗi chi tiết.

### 3.2 Bộ điều khiển an toàn (`app/safety/controller.py`)
- Lớp ngoại lệ: `SafetyValidationError(ValueError)`
- Lớp `SafetyController`:
  - `validate_target_url(url: str) -> str`:
    - Thẩm định URL phải có scheme hợp lệ (`http://` hoặc `https://`).
    - Phải có network location (host/domain/ip) hợp lệ.
    - Không chứa ký tự bất thường hoặc rỗng.
  - `validate_limits(timeout: float, duration: int | None = None, rate: int | None = None, concurrency: int | None = None) -> None`:
    - `timeout` phải > 0 và <= `config.request_timeout`.
    - `duration` (nếu có) phải > 0 và <= `config.max_test_duration`.
    - `rate` (nếu có) phải > 0 và <= `config.max_request_rate`.
    - `concurrency` (nếu có) phải > 0 và <= `config.max_concurrency`.

### 3.3 HTTP Connectivity Client (`app/engine/runner.py`)
- Lớp dữ liệu `ConnectivityResult`:
  - `target: str`
  - `method: str` (mặc định "GET")
  - `status_code: int | None`
  - `latency_ms: float`
  - `success: bool`
  - `error_message: str | None`
- Lớp `ConnectivityRunner`:
  - Khởi tạo nhận `timeout: float = 5.0`, hoặc nhận custom `client: httpx.Client | None`.
  - Phương thức `test_connectivity(target_url: str) -> ConnectivityResult`:
    - Đo thời gian trước và sau request bằng `time.perf_counter()`.
    - Gửi 1 GET request duy nhất.
    - Bắt các ngoại lệ:
      - `httpx.TimeoutException` -> `success=False`, `error_message="Request timed out"`
      - `httpx.ConnectError` -> `success=False`, `error_message="Connection refused / failed"`
      - `httpx.RequestError` -> `success=False`, `error_message=str(err)`
      - `Exception` -> `success=False`, `error_message=f"Unexpected error: {err}"`
    - Trả về `ConnectivityResult`.

### 3.4 CLI Interface (`app/cli.py`)
- Khởi tạo ứng dụng Typer: `app = typer.Typer(name="dos-tool", help="Controlled HTTP/DoS Testing Tool")`
- Các lệnh chính:
  1. `dos-tool --help`: Hiển thị trợ giúp tổng quan.
  2. `dos-tool version`: Hiển thị phiên bản ứng dụng (`v0.1.0`).
  3. `dos-tool config [--path <FILE>]`: Hiển thị cấu hình hiện tại dạng bảng hoặc YAML.
  4. `dos-tool test --target <URL> [--timeout <SEC>] [--config <FILE>] [--debug]`:
     - Kiểm tra an toàn `target` qua `SafetyController`.
     - Chạy `ConnectivityRunner.test_connectivity(target)`.
     - In kết quả ra terminal theo phong cách bảng Rich:
       ```
       DOS TOOL - Connectivity Test
       ──────────────────────────────
       Target      : http://localhost:8000
       Method      : GET
       Status      : 200
       Latency     : 42 ms
       Result      : SUCCESS
       ──────────────────────────────
       ```
     - Trả về exit code: `0` nếu `success=True`, `1` nếu `success=False` hoặc lỗi thẩm định an toàn.
     - Ẩn Python traceback trừ khi có cờ `--debug`.

### 3.5 Ghi Log (`app/logger.py` hoặc cấu hình trong `app/config.py`)
- Cấu hình format log: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- Không in header `Authorization`, `Cookie`, hay credentials.

---

## 4. Chiến lược kiểm thử (Testing Strategy)

Áp dụng TDD (Test-Driven Development):
1. `tests/test_config.py`:
   - Nạp cấu hình mặc định khi không truyền file.
   - Nạp cấu hình từ YAML hợp lệ.
   - Ném lỗi khi cấu hình chứa giá trị âm / sai kiểu.
2. `tests/test_safety.py`:
   - URL hợp lệ (`http://localhost:8000`, `https://example.com/api`).
   - URL không có scheme hoặc scheme lạ (`ftp://`, `ssh://`, `invalid-url`).
   - Giới hạn vượt ngưỡng (concurrency > max, duration > max, timeout <= 0).
3. `tests/test_http.py`:
   - Kết nối thành công (mô phỏng 200 OK với mock transport).
   - Xử lý timeout (`httpx.TimeoutException`).
   - Xử lý lỗi từ chối kết nối (`httpx.ConnectError`).
   - Xử lý mã lỗi HTTP 404, 500.

---

## 5. Lộ trình phát triển toàn diện (Roadmap)
- **Phase 1 — Project Foundation** (Đang triển khai)
- **Phase 2 — HTTP Load Engine**
- **Phase 3 — Scenario Engine**
- **Phase 4 — Metrics & Reporting**
- **Phase 5 — Web Dashboard**
- **Phase 6 — Fault Injection**
- **Phase 7 — Experiment Framework**
