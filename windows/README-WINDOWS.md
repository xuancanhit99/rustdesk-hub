# RustDesk Hub cho Windows

ZIP này chứa server bundle RustDesk Hub, các launcher vận hành và CLI onboarding
client. Gói **không** chứa file thực thi GUI của RustDesk.

## Lần chạy đầu tiên

1. Cài và khởi động Docker Desktop ở chế độ Linux containers/WSL2.
2. Có thể cài Python 3.10+ để dùng onboarding và test tự động.
3. Chạy `windows\Test-Prerequisites.cmd`.
4. Sao chép `.env.example` thành `.env` rồi kiểm tra nội dung.
5. Chạy `windows\Start-RustDesk-Hub.cmd`.
6. Chạy `windows\Status-RustDesk-Hub.cmd` và lưu public key.

Mặc định an toàn chỉ lắng nghe tại `127.0.0.1`. Hãy cấu hình host thật,
firewall và `RUSTDESK_BIND_ADDRESS=0.0.0.0` trước khi onboarding máy từ xa.

Để cấu hình client, cài bản RustDesk đã ký từ
https://github.com/rustdesk/rustdesk/releases, sau đó chạy:

```bat
windows\Onboard-RustDesk-Client.cmd -ServerHost rustdesk.example.com -Probe
```

Việc áp dụng cấu hình cần terminal nâng quyền và xác nhận rõ ràng:

```bat
windows\Onboard-RustDesk-Client.cmd -ServerHost rustdesk.example.com -Apply -Force
```

Xác minh ZIP đã tải trước khi giải nén:

```powershell
Get-FileHash .\rustdesk-hub-windows-0.1.0.zip -Algorithm SHA256
Get-Content .\rustdesk-hub-windows-0.1.0.zip.sha256
```

Sau khi checksum khớp, nếu Windows đánh dấu script là file tải từ Internet và
execution policy chặn chúng, hãy chủ động bỏ chặn bundle đã xác minh:

```powershell
Get-ChildItem .\rustdesk-hub-windows-0.1.0 -Recurse -File | Unblock-File
```

Sau đó kiểm tra mọi payload theo manifest được bảo vệ bằng checksum:

```bat
windows\Verify-Release-Files.cmd
```

Bản phát hành là ZIP chưa ký, không phải installer. Xem
`RELEASE-MANIFEST.json`, `THIRD_PARTY.json` và `NOTICE.md` để biết chính xác nội
dung và nguồn gốc.
