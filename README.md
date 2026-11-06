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

### Hai vai trò

**Có UI kit:** dùng tối đa element trong kit. Chỉ tạo element mới khi không có cái nào hợp, vẽ theo đúng style kit, đặt vào đúng nhóm và đặt tên theo quy tắc. Sprite của kit giữ tên file gốc làm tên layer trong PSD, dùng nhiều lần vẫn cùng một tên, nên khi xuất layer không bị lặp resource.

**Không có UI kit:** skill hỏi bạn mô tả art style, rồi hỏi bạn muốn bắt đầu từ prompt hay từ ảnh tham khảo (ít nhất 1 ảnh, kèm ghi chú là tham khảo layout hay art style). Sau khi bạn chốt màn demo, skill lấy nó làm mốc style, dựng một bộ component nền (font, nút, popup, panel, thanh, tab, khung, icon) và dùng lặp lại, chỉ thêm element mới khi thật cần.

**Mỗi màn có phần riêng:** sau khi chốt màn mốc, skill vẽ thêm 1 concept cho mỗi loại màn khác (shop, settings...) theo cùng style. Element chia hai lớp: lớp base dùng chung và lớp riêng từng màn, ví dụ shop có tab, khung item, tag giá, settings có icon từng dòng và toggle. Lệnh `mockup` và `qa` cảnh báo `PLAIN_SCREEN` khi một màn chỉ có panel, nút và chữ.

**Nền và art, cả hai vai trò:** màn nào cũng có nền. Màn thường dùng nền và pattern của kit trước. HUD có ảnh cảnh vẽ theo art style của game. Popup dùng màn cha làm mờ (`backdrop`). Nhân vật và vật phẩm không có trong kit thì skill tự tạo, hiển thị bằng hình thay vì chữ.

### Bảng hỏi khi tạo wireframe

`$gui-wireframe create` luôn bắt đầu bằng 7 câu hỏi đánh số: hướng màn hoặc kích thước tự nhập, các màn cần làm, thể loại game, gameplay, chức năng từng màn, nội dung từng vùng (dọc: Top, Middle, Bottom; ngang: Top, Left, Right, Bottom), và có tạo prototype không. Trả lời trên một dòng, ví dụ:

```text
1b | 2: 1, 6, Other: Gacha | 3: 13 | 4: ... | 5: ... | 6: ... | 7b
```

Câu thể loại và gameplay chỉ hỏi ở wireframe đầu tiên của một game mới. Câu trả lời lưu trong `brief.json`. Bước đầu chỉ vẽ ảnh wireframe. Sau khi bạn chỉnh và chốt bằng `$gui-confirm wireframe`, prototype mới được tạo, và chỉ khi câu 7 chọn có.

### Bảng hỏi khi tạo UI visual

`$gui-visual` hỏi 3 câu trước khi làm art:

1. File wireframe. Nếu kit đã có wireframe đã chốt thì dùng luôn, chỉ trả lời khi muốn thay.
2. Có UI kit không: có thì add kit kèm mô tả. Không thì chọn có ảnh reference (không giới hạn số ảnh, kèm mô tả) hoặc tự sáng tạo theo mô tả (màu sắc, UI style chọn từ danh sách, mô tả thêm).
3. Có background sẵn không: có thì add file. Không thì chọn lọc từ UI kit hoặc tạo mới theo art style, kèm mô tả nếu muốn.

Ví dụ trả lời: `1: D:\wf\home.png | 2b1: D:\ref\a.png, D:\ref\b.png - giống a nhưng ấm hơn | 3b2`. Nếu chạy `asset` hay `mockup` khi chưa trả lời thì skill sẽ hỏi bảng này trước.

Danh sách thể loại, art style và màn hình lấy từ sheet UI KIT FILTER, lưu ở `game-ui-kit/references/catalog.md`. Bộ base và quy tắc đặt tên (`btn_yellow`, `btn_sp_green`, `title_red`, `set_coin_1`, `loading_bar_yellow_a`...) ở `game-ui-kit/references/ui_kit_standard.md`.

## Lệnh

Gõ `$gui` trong Codex để thấy danh sách.

| Lệnh | Tác dụng |
|---|---|
| `$gui-info` | Xem các lệnh, tình trạng kit và bước tiếp theo |
| `$gui-kit <đường dẫn>` | Nạp UI kit có sẵn |
| `$gui-wireframe create <mô tả>` | Hỏi bảng câu hỏi, rồi vẽ ảnh wireframe. Chưa tạo prototype |
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
| `$gui-confirm wireframe` | Chốt wireframe, tạo prototype nếu bảng hỏi chọn có |
| `$gui-visual` | Hỏi bảng câu hỏi visual: wireframe, UI kit hoặc ref hoặc art style, background |
| `$gui-confirm <màn> [v2]` | Chốt mockup một màn |
| `$gui-flow` | Tạo demo bấm thử và sơ đồ luồng |
| `$gui-spec` | Tạo tài liệu bàn giao |
| `$gui-export` | Xuất PSD sửa được cho các màn đã chốt |
| `$gui-export unity` | Xuất JSON mapping cho Unity |

Thứ tự: `wireframe create`, `wireframe adjust`, `confirm wireframe`, `visual`, `asset`, `mockup`, `mockup adjust`, `confirm <màn>`, `flow`, `export`.

Kết quả nằm trong `ui_art/<tên_kit>/`: sprite ở `elements/`, mockup ở `preview/mockups/`, demo ở `demo/index.html`, file xuất ở `export/`. PSD có text thật, group theo quan hệ cha con, shape cho hình đủ đơn giản và smart object cho hình phức tạp. Mockup, PSD và JSON chưa phải màn hình dựng trong game engine.
