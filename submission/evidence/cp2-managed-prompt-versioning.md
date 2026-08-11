# CP2 — Managed prompt versioning và rollback

Thời điểm xác minh cuối: 2026-08-11. Dữ liệu dưới đây được đọc lại từ
Langfuse bằng API sau khi các trace đã được flush; không suy luận từ log cục bộ.

## Trạng thái prompt cuối

| Prompt | Version | Nội dung thay đổi chính | Labels cuối |
|---|---:|---|---|
| `day13-chat` | 1 | Câu trả lời ngắn dựa trên docs | `baseline`, `production` |
| `day13-chat` | 2 | Chia câu trả lời thành `Answer` và `Evidence` | `candidate`, `latest` |

Hai version đều giữ đúng ba biến contract: `{{feature}}`, `{{docs}}` và
`{{message}}`.

## Đổi label và rollback

1. Tạo v1 với `baseline`, `production` và v2 với `candidate`.
2. Chuyển `production` từ v1 sang v2. Request kiểm chứng dùng v2:
   [trace `c308216c...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/c308216c1542c32260ef4c5041914285).
3. Rollback `production` về v1. Request kiểm chứng sau rollback dùng v1:
   [trace `c6107a2d...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/c6107a2d17d81fc90a9d61c19e6c68d4).
4. Đọc lại prompt sau rollback xác nhận v1 có `baseline`, `production`; v2 có
   `candidate`, `latest`.

## Mười trace managed prompt đã xác minh

| # | Session | Correlation ID | Label | Version | Latency | Trace |
|---:|---|---|---|---:|---:|---|
| 1 | `qa-prompt-versioning` | `req-3e39865b` | `baseline` | 1 | 0.922 s | [`21078f5a...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/21078f5a7f64abd98de7dab1fa5b2cb3) |
| 2 | `qa-prompt-versioning` | `req-10bea1cc` | `candidate` | 2 | 0.883 s | [`9c23cd223...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/9c23cd2239f2e7eec6140954d85a9f3e) |
| 3 | `qa-production-switch` | `req-c0ec21e2` | `production` | 2 | 0.911 s | [`c308216c...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/c308216c1542c32260ef4c5041914285) |
| 4 | `qa-production-rollback` | `req-52045b22` | `production` | 1 | 1.015 s | [`c6107a2d...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/c6107a2d17d81fc90a9d61c19e6c68d4) |
| 5 | `qa-managed-01` | `req-8e6f0b68` | `baseline` | 1 | 1.050 s | [`01d099ad...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/01d099adb747ff08dda92fc6a6a7a657) |
| 6 | `qa-managed-02` | `req-a5b23019` | `candidate` | 2 | 0.920 s | [`929af52c...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/929af52cf6a95732cbae5fadc3008399) |
| 7 | `qa-managed-03` | `req-1320264e` | `baseline` | 1 | 0.153 s | [`507a7611...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/507a7611ef2a519303f3ae44acd2174c) |
| 8 | `qa-managed-04` | `req-70920d26` | `candidate` | 2 | 0.155 s | [`77e624e6...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/77e624e66a8639da37890d6121b4dd62) |
| 9 | `qa-managed-05` | `req-40230ea9` | `baseline` | 1 | 0.155 s | [`d49a95a5...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/d49a95a5b786b1d9075f6b451f25a736) |
| 10 | `qa-managed-06` | `req-9408542d` | `candidate` | 2 | 0.158 s | [`03e7f9a0...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/03e7f9a06ba98600732f3e46fa94e7d7) |

Mỗi trace trên được API xác nhận có đủ `prompt_name=day13-chat`,
`prompt_label` và `prompt_version`. Các trace cũng có generation `run` và các
observation `rag_retrieve`, `llm_generate` để mở waterfall.

## Ảnh UI cần lưu khi đăng nhập Langfuse

Rubric yêu cầu ảnh giao diện ngoài evidence API. Mở các link trace ở trên và
lưu bốn ảnh sau vào cùng thư mục này trước khi nộp:

- `prompt-versions-v1-v2.png`: danh sách v1/v2 và labels cuối.
- `prompt-production-switch-v2.png`: tạm chuyển `production` sang v2.
- `prompt-production-rollback-v1.png`: v1 đang giữ label `production`.
- `trace-waterfall-managed.png`: waterfall của trace baseline hoặc candidate,
  thấy `rag_retrieve` và `llm_generate`.
