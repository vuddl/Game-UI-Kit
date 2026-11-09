# Việc cần làm cho game-ui-kit

Cập nhật: 09/11/2026. Danh sách gom từ các phiên ngày 06, 07 và 09/11.

## Trạng thái

Mục 1–20 đã làm xong trên máy ngày 09/11, **chưa commit**. Đã thử bằng script, trình duyệt và Photoshop trên máy này. **Chưa thử một vòng thật trong Codex** (`$setup` → `$wireframe` → `$mockup` → export).

| Mục | Nội dung | Trạng thái |
|---|---|---|
| 1–4 | Codex giữ lượt khi chờ form; máy chủ form chạy riêng; gõ "xong" để lấy câu trả lời; trang "Đã gửi" | Xong. Thử: gửi khi đang chờ, lệnh chờ bị cắt rồi lấy sau, mở form mới thì form cũ tự đóng |
| 5 | Mô tả lựa chọn bằng tiếng Việt | Xong. Cột "Mô tả trên form" trong `catalog.md`, kèm ví dụ game; tên nhóm màn tiếng Việt |
| 6 | "Lựa chọn khác" có ô mô tả (thể loại game, UI style) | Xong. Lưu thành `game_type_description`, `ui_style_description` |
| 7 | Wireframe đẹp như ảnh mẫu | Xong. Dựng HTML/CSS, chụp bằng Edge/Chrome chạy ngầm; item có `wf` và `icon` (bộ icon Lucide trong `assets/`). Không có trình duyệt thì vẽ bản đơn giản và báo `NO_BROWSER` |
| 8 | Bỏ chữ luồng trên wireframe | Xong. Chỉ thêm `goto` khi chọn prototype, ở bước kết quả |
| 9 | Sau "Tiếp tục": hiện ảnh rồi hỏi "Có muốn làm thêm màn hình khác không?" | Xong (SKILL.md) |
| 10 | Form mockup bỏ "Màn nào?", mỗi wireframe có ô Tên màn (gợi ý) và Mô tả màn | Xong. Một form có thể gồm nhiều màn; tên trống thì Codex đoán |
| 11 | Câu hỏi style hiện cả khi có reference, không bắt buộc | Xong (`required_if` trong form) |
| 12 | "Sửa chữa tiếp" mở form sửa có ảnh | Xong. Form `revise`, chọn bản có ảnh xem trước, ý sửa bắt buộc cho bản đã chọn, gắn ảnh kèm ghi chú |
| 13, 16, 20 | PSD vẽ lại bằng shape và layer effect | Xong. Recipe trong `style/recipes/`, lệnh `uikit.py recipe`, hướng dẫn ở `references/recipes.md`. Photoshop dựng live shape, gradient, fill opacity, clipping mask, blend mode, Stroke, Bevel & Emboss, Shadow, Glow, Overlay, effect ở cấp group |
| 14 | Tên layer `(chức năng)_(mô tả)_(màu)_(màn)` | Xong (SKILL.md); lớp con đặt tên `fill_…`, `stroke_…`, `highlight_…` |
| 15 | Chữ là text layer thật | Đã có từ trước, giữ nguyên |
| 17 | Hỏi về background trước mỗi lần xuất PSD | Xong. Câu hỏi mới trong form export |
| 18 | Ảnh lớn giữ kích thước gốc trong smart object | Đã có từ trước, giữ nguyên |
| 19 | Group theo quan hệ cha con | Đã có từ trước; đã kiểm tra trên file PSD thật |

## Giới hạn còn lại

- Recipe tự đoán chỉ nhận hình chữ nhật, chữ nhật bo góc và ellipse, kèm fill hoặc gradient dọc và viền. Bevel, vệt sáng, bóng và các hình phức tạp (icon, ruy băng) Codex phải tự thêm khi xem ảnh so sánh.
- Bộ vẽ thử bằng Python chỉ gần đúng Photoshop, nhất là Bevel. Ảnh kiểm tra cuối cùng là `export/psd/assets/<layout>_check.png` do Photoshop xuất.
- Photoshop không cho script tạo pattern mới, nên bề mặt có hoa văn phải vẽ bằng shape hoặc để ảnh clip vào shape.
- Sprite nào không có recipe vẫn dùng cách cũ: dò thành mảng màu phẳng, hoặc giữ ảnh.
