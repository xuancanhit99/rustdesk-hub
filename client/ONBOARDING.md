# Đưa ứng dụng khách vào hệ thống

RustDesk Hub sử dụng ứng dụng khách RustDesk tiêu chuẩn dành cho máy tính. Sản
phẩm không cung cấp tệp thực thi GUI được đổi thương hiệu. Hãy tải ứng dụng
khách đã ký từ dự án chính thức:
https://github.com/rustdesk/rustdesk/releases

## 1. Phát hiện bản cài đặt

```powershell
.\client\Onboard.ps1 -CheckOnly
```

```bash
bash client/onboard.sh --check-only
```

Trình kiểm tra tìm trong `PATH` và các đường dẫn cài đặt thông dụng trên
Windows, Linux và macOS, sau đó thực thi lệnh `--version` được dự án gốc hỗ
trợ. Mã thoát `4` nghĩa là không tìm thấy ứng dụng khách dùng được.

## 2. Tạo hồ sơ cấu hình cho mọi hệ điều hành máy tính

Hãy khởi động hub trước để công cụ có thể đọc khóa công khai của hub:

```powershell
.\client\Onboard.ps1 -ServerHost rustdesk.example.com -Platform all -Probe
```

```bash
bash client/onboard.sh --host rustdesk.example.com --platform all --probe
```

Đầu ra chứa một tệp `RustDesk2.toml`, một bản kê đường dẫn đích và một tệp
hướng dẫn cho mỗi hệ điều hành. Các tệp TOML này là **đoạn cấu hình dành cho hồ
sơ mới** an toàn. Tuyệt đối không sao chép chúng đè lên `RustDesk2.toml` hiện
có vì việc đó sẽ làm mất ID thiết bị, thông tin máy ngang hàng và các cài đặt
ứng dụng khách không liên quan.

Các đường dẫn hồ sơ mới thường dùng được ghi trong từng `profile.json` được tạo
ra:

- Windows: `%APPDATA%\RustDesk\config\RustDesk2.toml`
- Linux: `${XDG_CONFIG_HOME:-$HOME/.config}/rustdesk/RustDesk2.toml`
- macOS: `$HOME/Library/Preferences/com.carriez.RustDesk/RustDesk2.toml`

## 3. Hợp nhất vào ứng dụng khách đã cài đặt

Chạy từ cửa sổ dòng lệnh Administrator/root đã nâng quyền theo yêu cầu của
RustDesk:

```powershell
.\client\Onboard.ps1 -ServerHost rustdesk.example.com -Apply -Force -Probe
```

```bash
sudo bash client/onboard.sh --host rustdesk.example.com --apply --yes --probe
```

`--apply` không sửa tệp TOML của người dùng. Tham số này gọi lệnh `--option`
được RustDesk hỗ trợ cho ID server, relay và key, ghi lại giá trị cũ dưới dạng
JSON, sau đó đọc lại cả ba giá trị và báo lỗi nếu kết quả xác minh khác nhau.
Thêm `--launch` để mở GUI sau khi áp dụng thành công.

Nếu chính sách ngăn thay đổi qua CLI, hãy nhập thủ công các giá trị được tạo
trong **RustDesk > Settings > Network**. Với OSS, hãy để trống API Server.

## Kiểm tra container, không phải GUI giả lập

Không có container ứng dụng khách GUI RustDesk chính thức. Máy chủ điều khiển
từ xa cần khả năng chụp màn hình, thiết bị nhập liệu và quyền hệ điều hành mà
một công cụ kiểm tra không giao diện không thể giả lập trung thực. Vì vậy, công
cụ Compose tùy chọn chỉ xác minh các cổng lắng nghe ID/relay nội bộ thực tế:

```powershell
.\scripts\Probe-Client.ps1
```

```bash
bash scripts/probe-client.sh
```

Điều khiển toàn màn hình và truyền tệp cần hai ứng dụng khách RustDesk thật.
Sau khi cả hai ứng dụng khách nhận cấu hình được tạo, hãy kết nối bằng ID máy
ngang hàng và dùng chế độ
**File transfer** tiêu chuẩn; nội dung vẫn được mã hóa đầu cuối khi đi qua
relay.
