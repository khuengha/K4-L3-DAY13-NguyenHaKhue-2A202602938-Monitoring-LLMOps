# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên: Nguyễn Hà Khuê**
- **MSSV: 2A202602938**
- **Lớp:** K4-L3B
- **Repository URL: [Repo/Khue](https://github.com/khuengha/K4-L3-DAY13-NguyenHaKhue-2A202602938-Monitoring-LLMOps)**
- **Commit SHA cuối: 53c93f5fc765489d9a76b5f0219a02bc5a1deffb**
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602938`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (CP0) | 100/100 (CP1) | Baseline đo trước khi sửa code: chỉ pass PII scrubbing; sau CP1 pass cả schema, correlation ID, enrichment |
| `validate_dashboard.py` | | 6/6 panel (CP2) | Dashboard contract hợp lệ theo `config/dashboard.yaml` |
| `pytest` | | 22 passed | Gồm test contract generation usage/cost thêm ở CP2 |
| Số traces hợp lệ | 0 | ≥10 (CP2) | 10 traces tạo bởi load test CP2 trong project Langfuse cá nhân |
| Số PII leak | | | |
| Latency P95 / TTFT P95 | | | |
| Retrieval success rate | | | |

**Ghi chú CP0 (baseline trước khi sửa code):** chạy `uvicorn app.main:app` với code gốc, `/health` trả `{"ok": true, "tracing_enabled": true}`, file `data/logs.jsonl` được tạo, thấy trace mới trong project Langfuse `day13-k4-l3b-2A202602938`. Chạy `scripts/load_test.py` cho 10 request 200 OK nhưng correlation_id hiển thị `MISSING`. `validate_logs.py` lúc này: 20 records — 20 thiếu required fields, 20 thiếu enrichment, 0 unique correlation ID → **Estimated Score: 30/100** (chỉ pass PII scrubbing). Baseline được tái tạo trung thực bằng cách stash code CP1, chạy lại với code gốc, sau đó khôi phục.

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` trong `app/middleware.py` — mỗi request: `clear_contextvars()` để tránh rò rỉ giữa các request, nhận `x-request-id` từ header (nếu client gửi) hoặc sinh mới dạng `req-<8-hex>` bằng `uuid4`, bind vào structlog contextvars để mọi log trong request tự mang `correlation_id`, gắn `request.state.correlation_id` cho handler dùng khi gọi agent/Langfuse, và trả về response header `x-request-id` + `x-response-time-ms`. Load test xác nhận 10/10 request có correlation ID riêng biệt.
- **Các metadata được ghi vào structured log:** trong `main.py` endpoint `/chat` bind `user_id_hash` (SHA-256 của user_id, 12 ký tự hex đầu), `session_id`, `feature`, `model`, `env` vào contextvars trước log `request_received`; kèm `ts` (ISO UTC), `level`, `service`, `event`, `correlation_id`, và payload có `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** đăng ký processor `scrub_event` vào pipeline structlog (`logging_config.py`) — chạy trước `JsonlFileProcessor` nên mọi record được scrub trước khi ghi `data/logs.jsonl`; `scrub_event` scrub cả trường `event` lẫn mọi string trong `payload` bằng `scrub_text` (`app/pii.py`) với các pattern: email, phone VN (+84/0), CCCD (12 số), credit card, passport, địa chỉ VN.
- **Cách kiểm chứng kết quả:** `python scripts/validate_logs.py` sau khi chạy load test — kết quả 20/20 records đầy đủ required fields và enrichment, 10 unique correlation IDs, 0 PII leak → **Estimated Score: 100/100** (baseline 30/100). Ngoài ra `python -m pytest -q`: 22 passed. Log sample `data/logs.jsonl` dòng 1 cho thấy `message_preview` chứa `[REDACTED_EMAIL]`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** project `day13-k4-l3b-2A202602938` chỉ tôi có key (trong `.env` cá nhân, không commit); mỗi trace có `user_id_hash`, `session_id`, `tags=["lab", feature, model]`, `environment=dev` và `metadata.correlation_id` khớp với log — filter theo session/timestamp của chính load test tôi chạy.
- **Cấu trúc root/retrieval/generation observations:** root là `lab-agent-run` (as_type `agent`, từ decorator `@observe` trên `LabAgent.run`) có metadata prompt name/label/version/source. Con 1: `retrieval` (as_type `retrieval`, `LabAgent._retrieve`) có metadata `retriever=mock-lexical`, `doc_count`, `query_preview` đã scrub PII. Con 2: `generation` (as_type `generation`, `LabAgent._generate`) được gắn prompt qua `propagate_attributes(prompt=...)`, có `model=claude-sonnet-4-5`, `usage_details` (input/output/total tokens) và `cost_details` (input/output/total USD) qua `update_current_generation`. Input/output capture tắt (`capture_input=False`) để tránh PII vào trace.
- **Cách nối trace với log:** mỗi request dùng cùng một `correlation_id` (`req-<8-hex>`) — middleware bind vào log contextvars và `propagate_attributes(metadata={...,"correlation_id":...})` ghi vào trace metadata; tìm trace theo correlation_id trong log line là tìm được. Ví dụ cặp đã đối chiếu: log line `data/logs.jsonl` có `correlation_id=req-cb80bb8c` ↔ Langfuse Trace ID `9d1dd29e56bb4c9c5f95aaa37ee509c` (trace có `session_id=s01`, `user_id_hash=2055254ee30a`, model `claude-sonnet-4-5`, 195 tokens, cost $0.002493).
- **Prompt name:** `day13-chat` (biến `{{feature}}`, `{{docs}}`, `{{message}}`), resolve qua `LANGFUSE_PROMPT_NAME`/`LANGFUSE_PROMPT_LABEL`.
- **Version/label baseline:** version 1, labels `baseline` + `production` (nội dung 3 biến `{{feature}}`/`{{docs}}`/`{{message}}`)
- **Version/label candidate:** version 2, label `candidate` (`latest`) — thay đổi: thêm "Answer briefly in two sentences." để câu trả lời ngắn hơn
- **Trace ID của mỗi version:** label `candidate` (v2) → Trace ID `8815e196688baecc396c100b283c20df` (`correlation_id=req-8bc2bf15`, `prompt_source=langfuse`, `prompt_version=2`); label `baseline` (v1) → Trace ID `225acf2545a23e3da758771c67e4ddc5` (`correlation_id=req-c1bdb9b6`, `prompt_version=1`). Đổi label bằng biến `LANGFUSE_PROMPT_LABEL` trong `.env` + restart, code không đổi.
- **Cách promote và rollback `production`:** trên Langfuse UI, chuyển label `production` từ version cũ sang version mới để promote; rollback là chuyển `production` quay lại version cũ. Code không cần sửa vì app resolve prompt theo label mỗi request; rollback rồi chạy lại load test, metadata `prompt_version` trong trace/log đổi theo. *(Điền ảnh evidence `10-prompt-rollback.png` sau khi thực hiện)*

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** dựng bằng Streamlit runtime (`scripts/dashboard.py`) đọc trực tiếp `data/logs.jsonl`, đủ 6 panel đúng contract `config/dashboard.yaml` — (1) Latency P50/P95/P99 + TTFT P95 (ms, threshold SLO P95 ≤ 3000ms), (2) Traffic requests/minute, (3) Error rate % + retrieval success % (threshold error ≤ 2%), (4) Cost USD/minute + total (threshold ≤ $2.5), (5) Tokens in/out, (6) Mean quality score 0–1 (threshold ≥ 0.75); time range 60 phút, refresh 30s. Validator: `HỢP LỆ: 6/6 panel`. Chạy: `python -m streamlit run scripts/dashboard.py`
- **SLO và lý do chọn:** `fast_successful_requests` — 99.5% request trong 28 ngày phải có `latency_ms <= 3000`. Chọn ngưỡng 3000ms vì baseline load test của tôi có P95 ~600–700ms, ngưỡng 3000ms là ngưỡng symptom người dùng thật sự cảm nhận chậm mà vẫn kề trên incident `rag_slow` (~2.3–3.4s).
- **Cách tính error budget:** SLO 99.5%/28d → error budget 0.5%. Với 10,000 request/28 ngày, tối đa 50 request được phép lỗi hoặc chậm hơn 3000ms.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (warning, `p95(latency_ms) > 3000` trong 5m), `HighErrorRate` (critical, `error_rate_pct > 2` trong 5m), `QualityScoreDegradation` (warning, `avg(quality_score) < 0.75` trong 10m) — tất cả symptom-based (đo triệu chứng người dùng, không đo tên implementation), có duration, severity, owner `student-2A202602938`, Slack `#k4-l3b-alerts`; runbook 3 bước kiểm tra + mitigation cho từng alert tại `docs/alerts.md`. Config: `config/alert_rules.yaml`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4, seed 1312, file `config/challenge.json` — gitignored)
- **Khoảng thời gian điều tra:** 2026-09-30 ~04:13:23–04:13:37 UTC (5 request `feature=monitoring`, session `k4-l3b-challenge-s01..s05`, workload `load_test.py --challenge --concurrency 5` sau khi bật incident)
- **Triệu chứng từ metrics:** 5/5 request thành công (HTTP 200) nhưng latency 7,989–13,356ms — tất cả vượt ngưỡng challenge 2000ms, trong khi baseline trước đó P95 chỉ ~600–700ms. `/metrics` sau workload: `latency_p95=2697ms` (trước incident ~500–600ms), không có lỗi, cost/tokens bình thường → symptom là tail latency tăng, không phải error.
- **Log line và correlation ID liên quan:** `data/logs.jsonl` dòng 122–123: `event=request_received` rồi `event=response_sent` có `correlation_id=req-e282bcaf`, `session_id=k4-l3b-challenge-s04`, `latency_ms=2653`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`, `quality_score=0.9` — TTFT thấp (50ms) nhưng tổng latency cao → thời gian mất ở phần trước generation, tức retrieval.
- **Trace ID và span gây ảnh hưởng:** Trace ID `ec3ce463365fb7659b5f8f43a1dbfcf9` (correlation_id=req-e282bcaf, session k4-l3b-challenge-s04) — waterfall cho thấy span `retrieval` chiếm 2.51s trong tổng 2.66s của trace (~95%), trong khi span `generation` chỉ 0.15s.
- **Root cause:** incident `rag_slow` được bật qua `/incidents/rag_slow/enable` làm mock RAG bị inject delay trong span `retrieval`; evidence khớp chuỗi: metric (P95 vượt ngưỡng SLO 3000ms và ngưỡng challenge 2000ms) → log (`latency_ms` cao, `ttft_ms` thấp, `tool_name=retrieval`, `tool_success=true`) → trace (span `retrieval` dài bất thường, generation bình thường).
- **Fix action:** tắt incident bằng `python scripts/inject_incident.py --scenario rag_slow --disable` (đã xác nhận `/health` trả `rag_slow: false`), sau đó chạy lại workload để xác nhận latency về baseline.
- **Preventive measure:** alert symptom-based `HighLatencyP95` (`p95(latency_ms) > 3000ms` trong 5m, runbook `docs/alerts.md#alert-1`) sẽ phát hiện triệu chứng này trong ~5 phút; runbook 3 bước (dashboard → log lọc theo latency → trace theo correlation_id so sánh span retrieval/generation) dẫn thẳng tới root cause; có thể thêm guardrail ngưỡng retrieval span P95 để phát hiện sớm hơn.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** tách `retrieval` và `generation` thành 2 child observations riêng (thay vì để chung trong root span) — vì chỉ khi có span riêng thì waterfall mới chỉ ra được span nào gây sự cố; chính cấu trúc này giúp CP3 khoanh vùng root cause là retrieval (2.51s/2.66s) chỉ trong một lần nhìn trace. Ngoài ra tắt `capture_input` để PII không vào trace.
- **Một lỗi/blocker đã gặp:** lần đầu chạy load test sau khi sửa middleware, server không kết nối được (WinError 10061) vì quá trình khởi động uvicorn bị lỗi im lặng khi thiếu `--env-file .env`; và trước khi tạo prompt trên Langfuse, mọi trace đều ghi `prompt_source=local-fallback` thay vì prompt managed.
- **Cách tìm nguyên nhân và xử lý:** với lỗi server, đọc log process background và restart bằng đúng lệnh `uvicorn app.main:app --env-file .env` (đúng theo `docs/SETUP.md`); với prompt fallback, đối chiếu metadata trace (`prompt_fetch_error=LangfuseFallback`) với `docs/PROMPT_VERSIONING.md`, tạo prompt `day13-chat` đúng tên + label trên Langfuse Cloud, restart và xác nhận `prompt_source=langfuse` trong trace mới.
- **Cách hiểu luồng Metrics → Logs → Traces:** metric phát hiện triệu chứng ở mức tổng thể (P95 vượt ngưỡng) và cho biết KHÔNG cần debug từng request ngay; log cung cấp sự kiện chi tiết có `correlation_id` để khoanh vùng request bị ảnh hưởng và loại trừ nguyên nhân (TTFT thấp, `tool_name=retrieval`, `tool_success=true` → không phải lỗi tool); trace cho thấy đúng span nào trong request đó chiếm thời gian. Ba nguồn nối bằng `correlation_id` — không nguồn nào tự chứng minh root cause một mình.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt version + label cho phép đổi hành vi model mà không sửa code, rollback là mitigation an toàn nhất khi prompt mới làm chất lượng tụt; token/cost là hai chỉ số vận hành riêng của LLM (generation là span đắt nhất, cost tăng bất thường = triệu chứng riêng cần alert); SLO + error budget biến "chậm/lỗi bao nhiêu là chấp nhận được" thành con số có thể cảnh báo tự động thay vì tranh luận cảm tính.
- **Điều quan trọng nhất đã học:** observability là thiết kế từ đầu chứ không phải gắn sau — correlation ID, structured log, span cha-con phải được dựng trước khi sự cố xảy ra thì lúc điều tra mới nối được metric → log → trace thành một chuỗi bằng chứng duy nhất đến root cause.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** dashboard Streamlit đọc file log cục bộ nên chỉ phản ánh 60 phút gần nhất trên một máy (không phải hệ thống đa instance); quality score hiện là heuristic proxy chứ chưa phải đánh giá chất lượng thật; chưa làm bonus cost optimization before/after.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
