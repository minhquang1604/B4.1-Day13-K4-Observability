# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: AI API tail-latency SLO breach
- Severity: Critical
- SLI/SLO liên quan: P95 response latency ≤ 3000 ms.
- Điều kiện và thời gian duy trì: `P95(response_sent.latency_ms) > 3000 ms` trong 10 phút liên tục.
- Ảnh hưởng tới người dùng: Người dùng nhận phản hồi chậm, đặc biệt ở tail latency; nguy cơ timeout hoặc bỏ phiên.
- Ba bước kiểm tra đầu tiên:
  1. Xác nhận P95/P99 tăng trên panel Latency và xác định time window bị ảnh hưởng.
  2. Mở một trace chậm trong time window đó, so sánh thời lượng các span retrieval và generation.
  3. Tìm `correlation_id` của trace trong `data/logs.jsonl` để xác nhận feature, model và lỗi liên quan.
- Mitigation tạm thời: Tắt hoặc giảm traffic của feature bị ảnh hưởng; nếu retrieval là span chậm, dùng fallback answer/giảm timeout theo runbook triển khai.
- Owner: Hùng (SRE).

## Alert 2

- Tên: AI API error-rate SLO breach
- Severity: Critical
- SLI/SLO liên quan: Error rate ≤ 2%.
- Điều kiện và thời gian duy trì: `count(request_failed) / count(request_received) * 100 > 2%` trong 5 phút liên tục.
- Ảnh hưởng tới người dùng: Một phần request không nhận được câu trả lời hợp lệ.
- Ba bước kiểm tra đầu tiên:
  1. Xác nhận error rate và breakdown `error_type` trên panel Errors.
  2. Mở trace hoặc log gần nhất của lỗi có cùng `correlation_id` để xác định span thất bại.
  3. So sánh lỗi theo `feature`, `model` và `env` để khoanh vùng phạm vi ảnh hưởng.
- Mitigation tạm thời: Roll back thay đổi gần nhất hoặc tắt feature bị lỗi; khi dependency không sẵn sàng, bật fallback an toàn và theo dõi error rate.
- Owner: Hùng (SRE).

## Alert 3

- Tên: AI API daily-cost budget breach
- Severity: Warning
- SLI/SLO liên quan: Daily generated-response cost ≤ 2.5 USD.
- Điều kiện và thời gian duy trì: `sum(response_sent.cost_usd) > 2.5 USD` trong cửa sổ rolling 24 giờ.
- Ảnh hưởng tới người dùng: Chưa nhất thiết gián đoạn ngay, nhưng có nguy cơ vượt ngân sách và phải hạn chế dịch vụ sau đó.
- Ba bước kiểm tra đầu tiên:
  1. Xác nhận total cost và traffic trong cùng time window trên panel Cost và Traffic.
  2. So sánh `tokens_in`, `tokens_out`, `model` và `feature` của các request có cost cao.
  3. Mở trace mẫu để kiểm tra prompt/version hoặc generation bất thường trước khi kết luận.
- Mitigation tạm thời: Hạ token limit hoặc chuyển tạm sang cấu hình/model có chi phí thấp hơn sau khi owner ứng dụng phê duyệt.
- Owner: Hùng (SRE).
