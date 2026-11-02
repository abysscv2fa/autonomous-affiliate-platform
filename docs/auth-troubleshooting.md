# Xử lý lỗi 401 / dashboard hiện 0

Luồng đúng: Trình duyệt -> `/api/*` (cùng origin, Nuxt server) -> proxy thêm header `x-affpilot-internal-token` -> Backend so với `AUTOPILOT_TOKEN`.

Hai biến phải CÙNG giá trị:
- Backend: `AUTOPILOT_TOKEN`
- Frontend (Nuxt server): `BACKEND_API_TOKEN`, cùng `BACKEND_API_BASE` (URL backend, không có /api)

Kiểm tra theo thứ tự:
1. Frontend trả 503 "Backend proxy is not configured": thiếu `BACKEND_API_BASE` hoặc `BACKEND_API_TOKEN`.
2. Backend trả 503 "AUTOPILOT_TOKEN is not configured": backend chưa có `AUTOPILOT_TOKEN`.
3. Backend trả 401: hai token khác nhau (kiểm tra khoảng trắng/xuống dòng thừa), hoặc trình duyệt gọi thẳng backend (đừng đặt `NUXT_PUBLIC_API_BASE`).
4. Job định kỳ (`scripts/daily_autopilot.py`) gửi header `X-Autopilot-Token` cùng giá trị `AUTOPILOT_TOKEN`; middleware chấp nhận cả hai header.
5. Sau khi đổi biến môi trường frontend phải build/deploy lại (Nuxt đọc biến lúc chạy server nhưng nên restart).

Thử nhanh backend: `curl -s -o /dev/null -w "%{http_code}" -H "x-affpilot-internal-token: $AUTOPILOT_TOKEN" https://<backend>/api/dashboard` phải ra 200.
