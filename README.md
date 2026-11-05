# Game UI Kit

Skill cho Codex để tạo bộ artwork UI game: nút kèm trạng thái, panel, thanh, khung và icon, xuất thành PNG trong suốt có tên rõ ràng và dữ liệu 9-slice. Skill cũng cắt, sắp xếp và tạo thêm từ UI kit có sẵn, đối chiếu kết quả với ảnh tham chiếu, và ghép mockup xem trước từ chính các sprite. Skill không dựng màn hình trong game engine.

Skill tạo ảnh bằng `image_gen` có sẵn trong Codex, chạy trên tài khoản Codex đang đăng nhập, không cần API key.

## Cài đặt

Trong Codex:

```text
$skill-installer install https://github.com/vuddl/Game-UI-Kit/tree/main/game-ui-kit
```

Script cần Python 3 kèm Pillow và numpy:

```bash
py -3 -m pip install pillow numpy
```

Trên macOS hoặc Linux, thay `py -3` bằng `python3`. Sau khi cài, mở một phiên Codex mới.

## Cập nhật

`skill-installer` dừng nếu skill đã có trên máy. Hãy xóa thư mục `~/.codex/skills/game-ui-kit` rồi cài lại.

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

Gõ sau `$game-ui-kit`, ví dụ `$game-ui-kit /mockup 3 rearrange`. Codex không cho skill tạo lệnh `/` riêng, nên phải có tên skill ở đầu. Các lệnh này không tạo ảnh AI nên không tốn hạn mức.

| Lệnh | Tác dụng |
|---|---|
| `/info` | Xem tình trạng kit và bước tiếp theo |
| `/tone [auto\|game\|ref]` | Xem hoặc đổi nguồn tông màu. Mặc định `auto`: skill tự quyết định sau khi xem game và ref |
| `/wireframe [x]` | Đề xuất `x` bố cục khung xám cho mỗi màn hình, kèm luồng |
| `/mockup [x] [keep\|rearrange]` | Ghép `x` mẫu cho mỗi màn hình từ sprite thật, giữ bố cục hoặc để AI xếp lại |
| `/choose <màn_hình> v<n>` | Chốt mẫu cho một màn hình |
| `/flow` | Vẽ sơ đồ luồng và tạo demo bấm thử |
| `/export [màn_hình]` | Xuất PSD có layer và PNG cho màn hình đã chốt |

Kết quả nằm trong `ui_art/<tên_kit>/`: sprite ở `elements/`, mockup ở `preview/mockups/`, demo ở `demo/index.html`, file xuất ở `export/`. Mockup và PSD chưa phải màn hình dựng trong game engine. Chữ trong PSD là layer ảnh, chưa sửa nội dung được.
