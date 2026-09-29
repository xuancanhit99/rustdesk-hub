# Cấu hình ứng dụng khách

Để dùng bộ tạo cấu hình, trình phát hiện cài đặt, công cụ kiểm tra điểm cuối và
trình khởi chạy đã được kiểm thử, hãy bắt đầu với
[ONBOARDING.md](ONBOARDING.md).

Phương án cấu hình thủ công dự phòng:

1. Chạy `scripts/status.sh` hoặc `scripts/Status.ps1` rồi sao chép khóa công khai.
2. Trong RustDesk, mở **Settings > Network > Unlock network settings**.
3. Đặt **ID Server** thành `your-host:21116`.
4. Đặt **Relay Server** thành `your-host:21117`.
5. Đặt **Key** thành khóa công khai do tập lệnh trạng thái in ra.
6. Để trống **API Server**; tính năng này thuộc RustDesk Server Pro, không phải
   OSS.

Bạn có thể dùng [RustDesk2.toml.example](RustDesk2.toml.example) làm mẫu nhưng
không được ghi đè tệp hiện có của ứng dụng khách. `onboard.py --apply --yes` sẽ
hợp nhất thông qua CLI chính thức của RustDesk rồi xác minh lại các giá trị.
