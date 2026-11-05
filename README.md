# Game UI Kit

Skill cho Codex để tạo bộ artwork UI game: nút kèm trạng thái, panel, thanh, khung và icon, xuất thành PNG trong suốt có tên rõ ràng và dữ liệu 9-slice. Skill cũng cắt, sắp xếp và tạo thêm từ UI kit có sẵn, đối chiếu kết quả với ảnh tham chiếu, và ghép mockup xem trước từ chính các sprite. Skill không dựng màn hình trong game engine.

Skill tạo ảnh bằng `image_gen` có sẵn trong Codex, chạy trên tài khoản Codex đang đăng nhập, không cần API key.

## Cài đặt

Trong PowerShell, lệnh này cài hoặc cập nhật skill chính và toàn bộ lệnh `$gui-...`:

```powershell
py -3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/vuddl/Game-UI-Kit/main/game-ui-kit/scripts/update.py').read())"
```

Script cần Python 3 kèm Pillow và numpy:

```powershell
py -3 -m pip install pillow numpy
```

Sau đó mở một phiên Codex mới và gõ `$gui-info`. Xuất PSD sửa được cần cài Photoshop trên máy.

## Cách dùng

Tạo bộ mới:

```text
$game-ui-kit Tạo bộ UI cho game [mô tả game], mobile dọc, gồm main menu, popup, shop, HUD.
```

Sắp xếp kit có sẵn, không tạo ảnh mới:

```text
$game-ui-kit Tôi có kit ở D:\duong_dan\kit. Chỉ sắp xếp và đặt tên, không tạo ảnh mới.
```

Tạo thêm phần còn thiếu:

```text
$game-ui-kit Tôi có kit ở D:\duong_dan\kit. Tạo thêm phần còn thiếu cho màn hình shop và đối chiếu với kit.
```

## Lệnh

Gõ `$gui` trong Codex để thấy danh sách.

| Lệnh | Tác dụng |
|---|---|
| `$gui-info` | Xem các lệnh, tình trạng kit và bước tiếp theo |
| `$gui-kit <đường dẫn>` | Nạp UI kit có sẵn |
| `$gui-wireframe create <mô tả>` | Tạo wireframe và luồng |
| `$gui-wireframe adjust <mô tả>` | Sửa wireframe bằng lời |
| `$gui-tone [auto\|game\|ref]` | Xem hoặc đổi nguồn tông màu |
| `$gui-asset <mô tả>` | Tạo sprite còn thiếu, có tốn hạn mức ảnh |
| `$gui-replace <sprite> <mô tả>` | Tạo lại một sprite, có tốn hạn mức ảnh |
| `$gui-mockup <màn> [x]` | Ghép mockup một màn, `x` mẫu |
| `$gui-mockup all [x]` | Ghép mockup mọi màn |
| `$gui-mockup adjust <mô tả>` | Sửa mockup bằng lời |
| `$gui-review <màn>` | AI nhận xét màn hình |
| `$gui-device <màn>` | Thử trên nhiều tỷ lệ màn hình |
| `$gui-check` | Kiểm tra lỗi và độ khớp tông màu |
| `$gui-confirm wireframe` | Chốt wireframe |
| `$gui-confirm <màn> [v2]` | Chốt mockup một màn |
| `$gui-flow` | Tạo demo bấm thử và sơ đồ luồng |
| `$gui-spec` | Tạo tài liệu bàn giao |
| `$gui-export` | Xuất PSD sửa được cho các màn đã chốt |
| `$gui-export unity` | Xuất JSON mapping cho Unity |

Thứ tự: `kit` (nếu có), `wireframe create`, `wireframe adjust`, `confirm wireframe`, `asset`, `mockup`, `mockup adjust`, `confirm <màn>`, `flow`, `export`.

Kết quả nằm trong `ui_art/<tên_kit>/`: sprite ở `elements/`, mockup ở `preview/mockups/`, demo ở `demo/index.html`, file xuất ở `export/`. PSD có text thật, group theo quan hệ cha con, shape cho hình đủ đơn giản và smart object cho hình phức tạp. Mockup, PSD và JSON chưa phải màn hình dựng trong game engine.
