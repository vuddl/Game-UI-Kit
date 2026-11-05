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

Ghép thử màn hình từ kit, không tạo ảnh mới:

```text
$game-ui-kit Ghép mockup màn hình shop và HUD từ kit ở D:\duong_dan\kit, theo bố cục ảnh D:\duong_dan\shop.png.
```

Kết quả nằm trong `ui_art/<tên_kit>/`, với sprite ở `elements/` và mockup ở `preview/mockups/`. Mockup chỉ là ảnh xem trước, chưa phải màn hình dựng trong game engine.
