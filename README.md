# RustDesk Hub

RustDesk Hub là gói RustDesk Server OSS tự lưu trữ, có thể tái tạo. Gói này
chạy dịch vụ điểm hẹn `hbbs` và dịch vụ chuyển tiếp `hbbr` chính thức trong hai
container được gia cố, ưu tiên phiên kết nối ngang hàng trực tiếp, lưu bền vững
định danh Ed25519 cùng cơ sở dữ liệu SQLite và cung cấp các phép kiểm tra thực
tế đối với cổng lắng nghe.

Các ứng dụng khách RustDesk tiêu chuẩn vẫn giữ nguyên tính năng điều khiển máy
tính từ xa, bảng nhớ tạm và truyền tệp; trung tâm này chỉ điều phối hoặc chuyển
tiếp các phiên đã mã hóa, không cần và cũng không cố đọc nội dung tệp được
truyền.

## Khởi động nhanh

Yêu cầu: Docker Engine/Desktop có Docker Compose v2.

```bash
cp .env.example .env
bash scripts/start.sh
bash scripts/status.sh
bash scripts/stop.sh
```

PowerShell:

```powershell
Copy-Item .env.example .env
.\scripts\Start.ps1
.\scripts\Status.ps1
.\scripts\Stop.ps1
```

Mặc định, dịch vụ chỉ lắng nghe tại `127.0.0.1`. Để truy cập từ xa, hãy sửa `.env`,
đặt `RUSTDESK_PUBLIC_HOST` thành tên DNS/IP công khai, đặt
`RUSTDESK_BIND_ADDRESS=0.0.0.0` và chỉ cho phép các cổng cần thiết trên
tường lửa. Các tập lệnh khởi động sẽ từ chối lắng nghe công khai nếu máy chủ
được quảng bá vẫn là giá trị giữ chỗ.

Định cấu hình mỗi ứng dụng khách RustDesk bằng ID Server, Relay Server và khóa
công khai do tập lệnh trạng thái in ra. Quy trình đa nền tảng đã kiểm thử nằm trong
`client/ONBOARDING.md`; ví dụ:

```powershell
.\client\Onboard.ps1 -ServerHost rustdesk.example.com -Platform all -Probe
```

Không sao chép `id_ed25519`; khóa bí mật đó phải luôn nằm trong Docker volume
được đặt tên.

Bạn có thể chạy tập lệnh trạng thái để lấy khóa công khai, sau đó nhập ID
Server, Relay Server và Key vào **RustDesk > Settings > Network**. Tập lệnh đưa
máy vào hệ thống có thể tìm ứng dụng khách đã cài, tạo hồ sơ cấu hình cho
Windows/Linux/macOS, kiểm tra máy chủ, áp dụng cấu hình có sao lưu và mở GUI.

## Cổng

| Cổng | Giao thức | Dịch vụ | Mục đích |
|---:|:---:|:---:|---|
| 21115 | TCP | hbbs | Kiểm tra loại NAT |
| 21116 | TCP + UDP | hbbs | ID/điểm hẹn và xuyên NAT |
| 21117 | TCP | hbbr | Chuyển tiếp có mã hóa |
| 21118 | TCP | hbbs | Điểm hẹn WebSocket cho ứng dụng khách web |
| 21119 | TCP | hbbr | Chuyển tiếp WebSocket cho ứng dụng khách web |

Với triển khai chỉ dùng ứng dụng khách gốc, có thể để đóng các cổng tường lửa
21118 và 21119. Tệp Compose vẫn ánh xạ các cổng này để phép kiểm tra cổng lắng
nghe bao quát đầy đủ bộ tính năng của máy chủ OSS. Cổng 21114 được cố ý bỏ qua
vì API server là tính năng Pro.

## Bảo mật và vận hành

- Hai dịch vụ dùng chung khóa được tạo tự động và truyền tham số `-k _`; ứng
  dụng khách phải dùng khóa công khai do tập lệnh trạng thái báo cáo.
- Container chạy ở chế độ chỉ đọc, loại bỏ mọi capability phạm vi rộng, chỉ giữ
  lại năm capability cần thiết để chuẩn bị volume và chuyển sang UID 10001, đồng
  thời bật `no-new-privileges`.
- Chỉ volume được đặt tên là có thể ghi bền vững; `/tmp` là tmpfs tạm thời
  16 MB. Việc xoay vòng log bị giới hạn ở ba tệp, mỗi tệp 10 MB.
- `RUSTDESK_ALWAYS_USE_RELAY=N` giữ P2P trực tiếp làm đường truyền ưu tiên. Chỉ
  đặt thành `Y` khi chính sách yêu cầu mọi phiên phải đi qua relay của bạn.
- `stop` giữ lại khóa/cơ sở dữ liệu. Muốn xóa vĩnh viễn phải dùng đúng cặp tham
  số `--purge-data --yes` hoặc `-PurgeData -Force`.
- Hãy sao lưu volume được đặt tên trước khi nâng cấp. Các image RustDesk và
  Alpine từ nguồn gốc được ghim theo phiên bản và mã băm đa kiến trúc; hãy xem
  xét và kiểm thử mọi cập nhật mã băm có chủ đích.

Công cụ kiểm tra nội bộ tùy chọn không khởi động GUI và không mở cổng nào. Công
cụ này kiểm tra bốn cổng lắng nghe TCP nội bộ mà một ứng dụng khách chạy trong
container sẽ truy cập:

```powershell
.\scripts\Probe-Client.ps1
```

## Kiểm thử

Kiểm tra tĩnh và các điều kiện xác nhận Compose đã chuẩn hóa không yêu cầu tiến
trình nền Docker đang chạy:

```powershell
.\tests\Run-Tests.ps1
```

Khi Docker đang chạy, hãy dựng image và thực hiện bài kiểm thử nhanh đầu-cuối
tách biệt. Bài kiểm thử sẽ cấp phát các cổng vòng lặp cục bộ tạm thời, chờ cả
hai phép kiểm tra sức khỏe, kết nối tới mọi cổng lắng nghe TCP, xác minh ánh xạ
UDP, xác nhận cả hai tiến trình máy chủ đã hạ đặc quyền/capability, khởi động
lại `hbbs` để chứng minh khóa định danh được lưu bền vững, chạy công cụ kiểm
tra ứng dụng khách tách biệt, tạo hồ sơ cho cả ba hệ điều hành máy tính rồi chỉ
xóa các container/volume kiểm thử do chính nó tạo ra:

```powershell
.\tests\Run-Tests.ps1 -Runtime
```

Các lệnh tương đương trên Linux/macOS là `bash tests/run-tests.sh` và
`bash tests/run-tests.sh --runtime`.

RustDesk Server OSS được cấp phép theo AGPL-3.0. Hãy đọc `NOTICE.md` trước khi
phân phối lại.

## Đóng gói Windows

Artifact Windows được hỗ trợ là ZIP không ký, chỉ chứa Compose bundle, tập lệnh
vận hành, onboarding CLI và tài liệu. Gói không chứa RustDesk GUI, `.exe`, MSI
hay DLL. Dựng và xác minh artifact bằng:

```powershell
.\tests\Test-WindowsPackaging.ps1
```

Artifact cục bộ được ghi vào `dist/` và được Git bỏ qua. Workflow
`.github/workflows/rustdesk-hub-release.yml` chỉ build/test/upload workflow
artifact với quyền đọc; nó không tạo GitHub Release và không publish image.
Chi tiết allowlist, checksum, provenance và các blocker installer nằm trong
`packaging/README.md`.
