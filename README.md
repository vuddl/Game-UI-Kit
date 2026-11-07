# Game UI Kit

Skill cho Codex để làm wireframe, UI visual mockup và xuất file thiết kế cho game. Mọi câu hỏi lớn đều hỏi bằng form trong trình duyệt. Skill tạo bộ artwork UI (nút kèm trạng thái, panel, thanh, khung, icon) thành PNG trong suốt có tên rõ ràng và dữ liệu 9-slice, ghép mockup từ chính các sprite, rồi xuất PSD, PNG và JSON hướng dẫn ghép trong Unity. Skill không dựng màn hình trong game engine.

Skill tạo ảnh bằng `image_gen` có sẵn trong Codex, chạy trên tài khoản Codex đang đăng nhập, không cần API key.

## Cài đặt

Trong PowerShell, lệnh này cài hoặc cập nhật skill chính và 4 lệnh `$setup`, `$wireframe`, `$mockup`, `$reset`. Lệnh cũng xoá các lệnh `$gui-...` cũ:

```powershell
py -3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/vuddl/Game-UI-Kit/main/game-ui-kit/scripts/update.py').read())"
```

Script cần Python 3 kèm Pillow và numpy:

```powershell
py -3 -m pip install pillow numpy
```

Sau đó mở một phiên Codex mới và gõ `$setup`. Xuất PSD sửa được cần cài Photoshop trên máy. Bảng chọn bấm được giữa các bước cần app Codex Desktop; nơi khác thì Codex hỏi bằng lựa chọn đánh số.

## Lệnh

| Lệnh | Tác dụng |
|---|---|
| `$setup` | Form định hình game: màn dọc, ngang hay tự nhập kích thước; thể loại game; gameplay. Chưa setup thì các lệnh khác không chạy |
| `$wireframe` | Làm wireframe từng màn bằng form, hoặc làm full các màn còn lại cùng lúc. Kết quả là ảnh PNG |
| `$mockup` | Làm UI visual mockup từng màn bằng form, hoặc làm full. Sau đó hỏi export PSD, PNG, kèm JSON ghép Unity |
| `$reset` | Xoá hết những gì lệnh đang làm đã tạo, rồi làm lại lệnh đó từ đầu. Reset khi đang ở `$setup` thì xoá luôn setup |

Quy tắc chuyển lệnh:

- Gõ lệnh khác khi đang làm dở: bỏ lệnh cũ, sang ngay lệnh mới. Phần đã làm vẫn giữ.
- Gõ lại đúng lệnh đang làm: không có gì thay đổi, làm tiếp từ chỗ dở.
- Quay lại một lệnh đã bỏ dở: làm tiếp từ chỗ dở của lệnh đó.

## Luồng `$wireframe`

1. Form tạo wireframe cho một màn: màn gì, chức năng, mô tả từng vùng (dọc: Top, Middle, Bottom; ngang: Top, Left, Right, Bottom), có tạo prototype không, tạo mấy option.
2. Codex hiện ảnh wireframe, rồi hỏi: **Sửa chữa tiếp** (sửa qua chat), **Làm full màn** hay **Tiếp tục**.
3. Tiếp tục: Codex hỏi đã xong hết các màn chưa. Chưa thì quay lại form cho màn tiếp theo.
4. Làm full màn: form chọn nhiều màn cùng lúc, mỗi màn có mô tả và ảnh ref riêng, thêm yêu cầu chung cho tất cả.
5. Kết quả: ảnh wireframe PNG từng màn, và demo bấm thử nếu có màn chọn prototype.

## Luồng `$mockup`

1. Form tạo mockup cho một màn: màn nào, add wireframe (PNG, ZIP...), có UI kit không (có: add kit; không: add ảnh reference hoặc chọn màu, sáng hay dark theme, UI style), có background sẵn không, tạo mấy option.
2. Codex hiện mockup, rồi hỏi: Sửa chữa tiếp, Làm full màn hay Tiếp tục, như `$wireframe`. Làm full màn dùng setup của màn đầu tiên.
3. Kết quả: ảnh mockup demo. Codex hỏi **Export không?**. Không thì hỏi có sửa tiếp không.
4. Form export: chọn PSD, PNG hoặc cả hai, và chọn các option muốn xuất (có ảnh xem trước). Kết quả luôn kèm JSON hướng dẫn ghép trong Unity.

**Có UI kit:** dùng tối đa element trong kit, chỉ tạo element mới khi không có cái nào hợp, vẽ theo đúng style kit. Sprite của kit giữ tên file gốc làm tên layer trong PSD, nên khi xuất layer không bị lặp resource.

**Không có UI kit:** skill làm màn demo từ reference hoặc từ mô tả, bạn chốt thì lấy làm mốc style. Sau đó skill dựng bộ component nền theo `ui_kit_standard.md` và thêm phần riêng cho từng màn, để màn nào cũng có chi tiết riêng.

**Nền:** màn nào cũng có nền, lấy từ file bạn add, từ UI kit hoặc tạo mới theo art style. HUD có ảnh cảnh gameplay, popup dùng màn cha làm mờ.

## Form

Form mở trên trình duyệt qua localhost. Form có câu chọn một hoặc nhiều đáp án, ô mô tả và nút đính kèm file cho từng lựa chọn, mô tả riêng cho từng file. Câu hỏi hiện theo câu trả lời trước, câu bắt buộc chưa trả lời thì không gửi được, và câu trả lời cũ được điền sẵn khi mở lại. Bấm **Hoàn thành** thì Codex nhận câu trả lời và làm tiếp.

File đính kèm lưu ở `inputs/` trong kit. File trùng nội dung chỉ lưu một lần, file ZIP được giải nén, file bạn bỏ đi thì bị xoá, nên không sinh rác mỗi lần hỏi.

Danh sách thể loại, art style và màn hình lấy từ sheet UI KIT FILTER, lưu ở `game-ui-kit/references/catalog.md`. Câu hỏi của từng form nằm ở `game-ui-kit/forms/*.json`, sửa file đó để đổi câu hỏi. Bộ base và quy tắc đặt tên (`btn_yellow`, `btn_sp_green`, `title_red`, `set_coin_1`, `loading_bar_yellow_a`...) ở `game-ui-kit/references/ui_kit_standard.md`.

## Kết quả

Mọi thứ nằm trong `ui_art/<tên_game>/`: wireframe ở `preview/wireframes/`, mockup ở `preview/mockups/`, demo ở `demo/index.html`, file xuất ở `export/psd/`, `export/png/`, `export/unity/`. PSD có text thật, group theo quan hệ cha con, shape cho hình đủ đơn giản và smart object cho hình phức tạp. Mockup, PSD và JSON chưa phải màn hình dựng trong game engine.
