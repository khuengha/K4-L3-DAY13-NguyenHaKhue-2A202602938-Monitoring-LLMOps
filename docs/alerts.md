# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms` (SLO chính `fast_successful_requests`: `latency_ms <= 3000`, target 99.5% trong 28d)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` duy trì liên tục 5 phút (tránh báo giả do một request đột xuất)
- Ảnh hưởng tới người dùng: P95 vượt ngưỡng SLO nghĩa là ≥5% người dùng phải chờ hơn 3 giây mới nhận được câu trả lời; nếu kéo dài, SLO 99.5%/28d bị đốt error budget (0.5% ≈ tối đa 50/10,000 request)
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel latency để xác nhận P95/P99/TTFT tăng và khoảng thời gian tăng bắt đầu từ khi nào.
  2. Lọc `data/logs.jsonl` trong khoảng đó theo `event=response_sent` sắp giảm dần theo `latency_ms`, lấy một `correlation_id` có `latency_ms` cao bất thường.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh span `retrieval` và `generation` để xác định span nào chiếm phần thời gian bất thường (VD: `rag_slow` làm retrieval chậm).
- Mitigation tạm thời: tắt scenario gây chậm (`/incidents/rag_slow/disable`), hoặc rollback prompt về version ổn định nếu nguyên nhân do generation; giảm concurrency nếu do tải.
- Owner: `student-2A202602938`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ lỗi request (error_rate_pct) — guardrail trong `config/slo.yaml` cho phép tối đa 2%
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` duy trì 5 phút (cửa sổ đủ dài để loại trừ 1-2 request lỗi đơn lẻ)
- Ảnh hưởng tới người dùng: hơn 2% request bị lỗi/timeout — người dùng không nhận được câu trả lời; đây là cảnh báo critical vì SLO đo "fast successful requests"
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel errors để xác nhận tỷ lệ lỗi và các error_type tăng từ khi nào.
  2. Lọc `data/logs.jsonl` các record `level in (error, critical)`, lấy một `correlation_id` cùng `error_type` và `tool_name`/`tool_success` của request lỗi.
  3. Mở trace cùng `correlation_id` trên Langfuse, tìm span lỗi (VD: `tool_fail` làm tool span fail) và đọc `status_message`.
- Mitigation tạm thời: tắt scenario lỗi (`/incidents/tool_fail/disable`), bật lại khi đã xác nhận nguyên nhân; nếu do prompt version mới, rollback label `production` về version cũ.
- Owner: `student-2A202602938`

## Alert 3

- Tên: `QualityScoreDegradation`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `avg(quality_score)` — guardrail trong `config/slo.yaml` yêu cầu tối thiểu 0.75
- Điều kiện và thời gian duy trì: `avg(quality_score) < 0.75` duy trì 10 phút (chất lượng dao động tự nhiên nên cần cửa sổ dài hơn các alert latency/error)
- Ảnh hưởng tới người dùng: câu trả lời chất lượng thấp hơn ngưỡng chấp nhận (không có tài liệu tham chiếu, quá ngắn, không liên quan câu hỏi) — người dùng vẫn nhận câu trả lời nhưng sai/kém ích
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel quality để xác nhận avg quality giảm từ khi nào và có khớp với thời điểm deploy/đổi prompt không.
  2. Lọc `data/logs.jsonl` theo `event=response_sent` với `quality_score` thấp, so sánh `prompt_version` và `feature` của các request này.
  3. Mở trace trên Langfuse của một `correlation_id` bất thường, xem metadata `prompt_version`, `prompt_label`, `doc_count` để xác định nguyên nhân (prompt mới tệ, retrieval rỗng, hay dữ liệu đầu vào thay đổi).
- Mitigation tạm thời: rollback label `production` về prompt version cũ trên Langfuse (không cần sửa code vì app resolve theo label), sau đó chạy lại workload để xác nhận quality phục hồi.
- Owner: `student-2A202602938`
