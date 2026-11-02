# Xử lý lỗi 401 / dashboard hiện 0

## Mô hình xác thực

Luồng trình duyệt: Browser -> same-origin `/api/*` -> Nuxt server proxy -> Backend.

Có hai credential độc lập:

- Backend `FRONTEND_PROXY_TOKEN`: chỉ dành cho header `x-affpilot-internal-token` từ Nuxt proxy.
- Backend `AUTOPILOT_TOKEN`: chỉ dành cho header `x-autopilot-token` từ GitHub Actions / scheduled jobs.
- Frontend `BACKEND_API_TOKEN`: phải trùng chính xác với Backend `FRONTEND_PROXY_TOKEN`.
- Frontend `BACKEND_API_BASE`: URL gốc của Backend, có `https://` và không thêm `/api`.

Nếu Backend chưa đặt `FRONTEND_PROXY_TOKEN`, middleware hỗ trợ cấu hình cũ bằng cách fallback sang `AUTOPILOT_TOKEN`. Khi `FRONTEND_PROXY_TOKEN` đã đặt, token proxy và token scheduled không dùng thay thế cho nhau.

## Kiểm tra theo thứ tự

1. Frontend trả 503 "Backend proxy is not configured": kiểm tra `BACKEND_API_BASE` và `BACKEND_API_TOKEN` trên service dashboard.
2. Frontend trả 503 do URL: `BACKEND_API_BASE` phải là URL tuyệt đối hợp lệ, bắt đầu bằng `https://` hoặc `http://`.
3. Backend trả 503: cả `FRONTEND_PROXY_TOKEN` và `AUTOPILOT_TOKEN` đều chưa được cấu hình.
4. Backend trả 401: đối chiếu fingerprint của token nhận được và token mong đợi trong log Backend. Không chia sẻ giá trị token thật.
5. GitHub Actions phải gửi `X-Autopilot-Token` bằng secret `AUTOPILOT_TOKEN` trùng với biến `AUTOPILOT_TOKEN` trên Backend.
6. Không gửi đồng thời hai header xác thực; middleware từ chối request có cả hai để tránh nhập nhằng.

## Cấu hình Render

- Backend service: `FRONTEND_PROXY_TOKEN` và `AUTOPILOT_TOKEN` là hai secret riêng.
- Frontend service: `BACKEND_API_BASE` trỏ đến Backend và `BACKEND_API_TOKEN` bằng `FRONTEND_PROXY_TOKEN`.
- GitHub Actions secret: `AUTOPILOT_TOKEN` bằng biến cùng tên trên Backend.

Sau khi đổi biến môi trường, chờ Render restart/deploy cả hai service.

## Chẩn đoán fingerprint

Frontend ghi một dòng `[affpilot-proxy]` với host, độ dài token và fingerprint SHA-256 rút gọn. Backend ghi `AUTH 401` với header được nhận, nguồn proxy, độ dài và fingerprint của token nhận được / token mong đợi. Fingerprint chỉ phục vụ đối chiếu; không đăng log công khai.

## AdSpy

`POST /api/ads-research/search` chỉ tạo URL tìm kiếm công khai cho Meta Ad Library; nó không truy vấn hoặc scrape quảng cáo. HTTP 200 xác nhận Backend đã tạo URL thành công. Danh sách quảng cáo không tự xuất hiện; người dùng mở Meta Ad Library và tự lưu nội dung công khai cần nghiên cứu.
