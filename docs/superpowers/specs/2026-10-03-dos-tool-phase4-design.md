# Thiết kế Kỹ thuật: dos-tool — Giai đoạn 4 (Phase 4: Metrics & Experiment Reporting)

**Ngày lập:** 03/10/2026  
**Dự án:** `dos-tool`  
**Mục tiêu:** Xây dựng hệ thống lưu trữ kết quả thử nghiệm, xuất báo cáo đa định dạng (JSON, CSV, HTML) và ghi lại toàn bộ mẫu độ trễ (latency samples) của từng request để phục vụ nghiên cứu và phân tích.  
**Phạm vi:** Triển khai Giai đoạn 4. Giữ nguyên tính độc lập, không tích hợp AI, Kubernetes, hay database; tách rời hoàn toàn tầng reporting khỏi HTTP load engine.

---

## 1. Yêu cầu kiến trúc & Nguyên tắc cốt lõi

### 1.1 Nguyên tắc kiến trúc
- **Low Coupling**: Không nhúng logic ghi file vào `LoadTestRunner` hay `ScenarioRunner`.
- **Tái sử dụng thống kê**: Tách riêng `app/metrics/statistics.py` để tính toán Min, Max, Avg, P50, P95, P99, Success Rate, Error Rate độc lập.
- **Tính toán Percentile trung thực**:
  - Không lấy trung bình cộng P95 của các stage để làm P95 tổng thể.
  - P95/P99 của kịch bản được tính trực tiếp từ toàn bộ tập hợp mẫu trễ thô (raw latency samples) thu được.
- **Bảo mật**: Tuyệt đối không lưu request/response body, authorization headers, cookies hay credentials.
- **Định danh duy nhất**: Mỗi lần chạy sinh ra một `experiment_id` có dạng `YYYYMMDD_HHMMSS_<scenario_name>`, lưu trong thư mục riêng biệt không bị ghi đè: `reports/<scenario_name>/<experiment_id>/`.

---

## 2. Cấu trúc thư mục sau Phase 4

```text
app/
├── cli.py
├── config.py
│
├── engine/
│   ├── __init__.py
│   ├── runner.py
│   ├── worker.py
│   └── scheduler.py
│
├── scenarios/
│   ├── __init__.py
│   ├── loader.py
│   ├── models.py
│   └── runner.py
│
├── metrics/
│   ├── __init__.py
│   ├── models.py              # Bổ sung LatencySample, ExperimentResult
│   ├── collector.py
│   └── statistics.py          # Module tính toán thống kê & phân vị tái sử dụng
│
├── reporting/
│   ├── __init__.py
│   ├── recorder.py            # ExperimentRecorder điều phối lưu kết quả
│   ├── json_reporter.py       # Xuất experiment.json
│   ├── csv_reporter.py        # Xuất stages.csv & latency.csv
│   └── html_reporter.py       # Xuất report.html trực quan
│
└── safety/
    ├── __init__.py
    └── controller.py
```

---

## 3. Chi tiết Model & Định dạng xuất dữ liệu

### 3.1 `LatencySample`
- `timestamp`: Chuỗi ISO 8601 UTC (ví dụ: `2026-10-03T15:30:02.123Z`)
- `stage_number`: Số thứ tự của stage (1-based)
- `latency_ms`: Độ trễ tính bằng mili-giây (float hoặc `None` nếu lỗi kết nối trước khi nhận phản hồi)
- `status_code`: Mã trạng thái HTTP (int hoặc `None`)
- `success`: boolean
- `error_type`: `"timeout"`, `"connection_error"`, `"http_error"`, hoặc `None`

### 3.2 File xuất ra trong mỗi Experiment
1. `experiment.json`: Chứa metadata, cấu hình an toàn, kết quả chi tiết từng stage, số liệu tổng hợp và toàn bộ latency samples.
2. `stages.csv`: Bảng tóm tắt các stage (Stage, Target Rate, Actual RPS, Concurrency, Duration, Requests, Success, Failed, Timeouts, 2xx, 3xx, 4xx, 5xx, Min, Avg, P50, P95, P99, Max Latency).
3. `latency.csv`: Danh sách từng request phục vụ vẽ biểu đồ và phân tích sâu trong Excel hoặc Pandas.
4. `report.html`: Giao diện web tĩnh đẹp mắt, trực quan, hiển thị summary cards, bảng stage, phân bố lỗi và đồ thị độ trễ.

---

## 4. Kế hoạch Kiểm thử (TDD Strategy)

1. `tests/test_statistics.py`:
   - Tính toán Min, Max, Average, P50, P95, P99.
   - Xử lý danh sách rỗng, 1 phần tử.
   - Tính toán Success Rate và Error Rate với mẫu 0 và mẫu bình thường.
2. `tests/test_reporting.py`:
   - Kiểm tra sinh `experiment_id` đúng định dạng `YYYYMMDD_HHMMSS_<scenario>`.
   - Kiểm tra xuất `experiment.json` đúng cấu trúc schema.
   - Kiểm tra xuất `stages.csv` và `latency.csv` đúng các cột yêu cầu.
   - Kiểm tra xuất `report.html` chứa đầy đủ thông tin experiment.
   - Kiểm tra tạo thư mục output và không ghi đè giữa các lần chạy.
3. `tests/test_cli.py`:
   - Kiểm tra lệnh `dos-tool scenario run` tự động sinh ra các file báo cáo.
   - Kiểm tra cờ `--output` cho phép tuỳ biến thư mục xuất.
