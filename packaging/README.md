# Đóng gói bản phát hành Windows

Artifact Windows được hỗ trợ là một file ZIP chưa ký, chứa server bundle Docker
Compose, wrapper PowerShell/CMD để vận hành, CLI onboarding client, tài liệu và
bộ test. Gói này chủ ý không chứa RustDesk GUI binary.

Dựng và xác minh tại máy cục bộ:

```powershell
.\packaging\Build-WindowsPackage.ps1 -Force
.\packaging\Test-WindowsPackage.ps1 `
  -Package .\dist\rustdesk-hub-windows-0.1.0.zip `
  -RunBundleTests
```

Hoặc chạy toàn bộ regression đóng gói, bao gồm phép thử từ chối archive bị sửa:

```powershell
.\tests\Test-WindowsPackaging.ps1
```

`windows-files.txt` là allowlist payload duy nhất. Trình dựng thêm `LICENSE`,
sau đó tạo `RELEASE-MANIFEST.json` chứa kích thước và SHA-256 của từng file.
Trình xác minh từ chối file thừa/thiếu, executable hoặc installer không được
phép, file giống private key, trạng thái sinh tự động và checksum không khớp.

ZIP cũng chứa `windows/Verify-Release-Files.cmd` để kiểm tra lại mọi payload sau
khi giải nén theo `RELEASE-MANIFEST.json`. Cần kiểm tra `.zip.sha256` bên ngoài
trước vì checksum của ZIP là lớp bảo vệ chính cho manifest.

Workflow GitHub Actions trong repo standalone dựng, xác minh và tải artifact
lên; khi tag `rustdesk-hub-v*` được push, workflow tạo GitHub Release. Workflow
không tự tạo repository và không phát hành image container.

## Trở ngại hiện tại đối với installer MSI/EXE

- Chưa cấu hình chứng chỉ ký mã Authenticode hoặc dịch vụ ký được bảo vệ. Một
  MSI/EXE chưa ký sẽ gặp SmartScreen và có provenance kém hơn ZIP có checksum.
- Chưa chọn/review WiX Toolset hoặc Inno Setup, upgrade code, install scope và
  chính sách uninstall.
- Repository không dựng RustDesk GUI binary. Nếu đóng gói GUI upstream, cần xác
  minh phiên bản/chữ ký và rà soát giấy phép phân phối lại; ZIP hiện liên kết
  tới client chính thức đã ký.
- Cần chạy workflow trên GitHub ít nhất một lần để xác minh hosted runner thực tế.
