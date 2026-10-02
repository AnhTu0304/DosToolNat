# Thiết kế Kỹ thuật: dos-tool — Giai đoạn 3 (Phase 3: Scenario Engine)

**Ngày lập:** 02/10/2026  
**Dự án:** `dos-tool`  
**Mục tiêu:** Xây dựng Engine kịch bản kiểm thử (Scenario Engine) cho phép định nghĩa các bài test nhiều giai đoạn (multi-stage load scenarios) qua file YAML, tự động điều phối thực thi tuần tự qua Phase 2 Load Engine.  
**Phạm vi:** Triển khai Giai đoạn 3. Chỉ hỗ trợ HTTP GET, kiểm tra an toàn từng stage và tổng thời lượng kịch bản trước khi chạy.

---

## 1. Yêu cầu & Luồng hoạt động

### 1.1 Mục tiêu chính
- Quản lý các file kịch bản trong thư mục `scenarios/` (định dạng YAML).
- Hỗ trợ các lệnh CLI:
  - `dos-tool scenario list`: Liệt kê các kịch bản có sẵn trong thư mục `scenarios/`.
  - `dos-tool scenario show <name>`: Hiển thị chi tiết cấu hình và các stage của kịch bản mà không gửi request.
  - `dos-tool scenario run <name>`: Thẩm định an toàn và thực thi tuần tự từng stage.
- Thẩm định an toàn toàn diện trước khi thực thi:
  - Thẩm định URL target hợp lệ.
  - Thẩm định từng stage không vượt quá các giới hạn an toàn (`max_request_rate`, `max_concurrency`, `max_test_duration`, `request_timeout`).
  - **Quy tắc tổng thời lượng (Total Duration Rule)**: Tổng thời lượng của tất cả các stages (`sum(stage.duration)`) không được vượt quá `max_test_duration` cấu hình.
- Tái sử dụng Phase 2 `LoadTestRunner` cho từng stage. Tuyệt đối không viết lại engine mạng.
- Tổng hợp số liệu:
  - Lưu giữ nguyên vẹn `LoadTestReport` cho từng stage.
  - Tính tổng requests, tổng thành công, thất bại, timeouts, connection errors toàn kịch bản.
  - Giữ riêng biệt các chỉ số P95, P99 theo từng stage (không tính trung bình sai lệch về mặt thống kê trên các percentile).

---

## 2. Kiến trúc & Cấu trúc thư mục

```text
app/
├── cli.py                     # Bổ sung nhóm lệnh Typer `scenario`: list, show, run
│
├── scenarios/
│   ├── __init__.py
│   ├── models.py              # ScenarioStage, Scenario, StageResult, ScenarioResult
│   ├── loader.py              # Quét thư mục scenarios/ & nạp / parse file YAML
│   └── runner.py              # ScenarioRunner điều phối chạy tuần tự các stage
│
├── engine/                    # Tái sử dụng trọn vẹn từ Phase 2
│   ├── runner.py              # LoadTestRunner & ConnectivityRunner
│   ├── worker.py
│   └── scheduler.py
│
├── metrics/                   # Tái sử dụng từ Phase 2
│   ├── models.py
│   └── collector.py
│
└── safety/
    └── controller.py          # Bổ sung validate_scenario() (kiểm tra từng stage & tổng duration)
```

---

## 3. Định dạng kịch bản mẫu (YAML Schema)

```yaml
name: ecommerce_product_ramp
description: Controlled ramp-up test for ecommerce product API
target: http://localhost:5000/api/products
method: GET
stages:
  - rate: 2
    concurrency: 1
    duration: 10
  - rate: 5
    concurrency: 2
    duration: 10
  - rate: 10
    concurrency: 5
    duration: 10
```

---

## 4. Kế hoạch Kiểm thử (TDD Strategy)

1. `tests/test_scenarios.py`:
   - Nạp file YAML hợp lệ / không hợp lệ.
   - Thẩm định model: target hợp lệ, method phải là GET, stages không được rỗng, rate/concurrency/duration phải dương.
   - Kiểm tra `dos-tool scenario list` phát hiện các file yaml và bỏ qua file lỗi.
   - Kiểm tra `dos-tool scenario show <name>`.
   - Kiểm tra kiểm soát an toàn: vi phạm stage đơn lẻ hoặc tổng thời lượng kịch bản vượt quá giới hạn.
2. `tests/test_scenario_runner.py`:
   - Chạy tuần tự các stage qua mock transport.
   - Kiểm tra thứ tự thực thi đúng tuần tự.
   - Kiểm tra thu thập số liệu tổng và từng stage trong `ScenarioResult`.
   - Kiểm tra dừng an toàn nếu có lỗi nghiêm trọng hoặc bị ngắt.
