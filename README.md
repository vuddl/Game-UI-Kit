# Game UI Kit

Skill cho Codex để làm wireframe, UI visual mockup và xuất file thiết kế cho game. Mọi câu hỏi lớn đều hỏi bằng form trong trình duyệt. Skill tạo bộ artwork UI (nút kèm trạng thái, panel, thanh, khung, icon) thành PNG trong suốt có tên rõ ràng và dữ liệu 9-slice, ghép mockup từ chính các sprite, rồi xuất PSD, PNG và JSON hướng dẫn ghép trong Unity. Skill không dựng màn hình trong game engine.

Skill tạo ảnh bằng `image_gen` có sẵn trong Codex, chạy trên tài khoản Codex đang đăng nhập, không cần API key.

## Cài đặt

Trong PowerShell, lệnh này cài hoặc cập nhật skill chính và 5 lệnh `$setup`, `$wireframe`, `$mockup`, `$reset`, `$info`. Lệnh cũng xoá các lệnh `$gui-...` cũ:

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
| `$info` | Thông báo những gì đã lưu: setup (kích thước, hướng màn, thể loại, gameplay), câu trả lời từng màn của wireframe và mockup, ảnh kết quả, file export, và lệnh đang làm tới bước nào. Không thay đổi gì |

Codex trả lời bằng tiếng Việt. Nội dung hiển thị trên wireframe, concept, mockup và prototype dùng tiếng Anh.

Quy tắc chuyển lệnh (`$info` chỉ xem, không tính là chuyển lệnh):

- Gõ lệnh khác khi đang làm dở: bỏ lệnh cũ, sang ngay lệnh mới. Phần đã làm vẫn giữ.
- Gõ lại đúng lệnh đang làm: không có gì thay đổi, làm tiếp từ chỗ dở.
- Quay lại một lệnh đã bỏ dở: làm tiếp từ chỗ dở của lệnh đó.

## Luồng `$wireframe`

1. Form tạo wireframe cho một màn: màn gì, chức năng, mô tả từng vùng (dọc: Top, Middle, Bottom; ngang: Top, Left, Right, Bottom), có tạo prototype không, tạo mấy option.
2. Codex hiện ảnh wireframe, rồi hỏi: **Sửa chữa tiếp**, **Làm full màn** hay **Tiếp tục**.
3. Sửa chữa tiếp: mở form sửa. Tick các bản cần sửa (có ảnh xem trước), ghi ý sửa cho từng bản, gắn ảnh minh họa kèm ghi chú.
4. Tiếp tục: Codex hiện lại ảnh các màn đã làm và hỏi **Có muốn làm thêm màn hình khác không?** Có thì mở form cho màn tiếp theo.
5. Làm full màn: form chọn nhiều màn cùng lúc, mỗi màn có mô tả và ảnh ref riêng, thêm yêu cầu chung cho tất cả.
6. Kết quả: ảnh wireframe PNG từng màn, và demo bấm thử nếu có màn chọn prototype.

Wireframe được dựng bằng HTML rồi chụp bằng Edge hoặc Chrome chạy ngầm. Màn có thẻ bo góc, icon, chữ dễ đọc, thanh tiến độ và thanh điều hướng có tab đang chọn. Các liên kết chuyển màn được thêm khi bạn chọn làm prototype.

## Luồng `$mockup`

1. Form tạo mockup: add wireframe (PNG, ZIP...), mỗi file là một màn, có ô **Tên màn** (gợi ý thả xuống, để trống thì Codex tự đoán) và ô **Mô tả màn**. Wireframe làm từ `$wireframe` được điền sẵn. Tiếp theo: có UI kit không (có: add kit; không: add ảnh reference hoặc tự sáng tạo), màu, sáng hay dark theme, UI style (có reference thì các câu này không bắt buộc, để trống thì lấy theo reference), có background sẵn không, tạo mấy option.
2. Codex hiện mockup, rồi hỏi: Sửa chữa tiếp (form sửa có gắn ảnh), Làm full màn hay Tiếp tục, như `$wireframe`. Làm full màn dùng setup của màn đầu tiên.
3. Kết quả: ảnh mockup demo. Codex hỏi **Export không?**. Không thì hỏi có sửa tiếp không.
4. Form export: chọn PSD, PNG hoặc cả hai, chọn các option muốn xuất (có ảnh xem trước), và với PSD thì hỏi lại mỗi lần: background vẽ lại hay để một layer ảnh. Kết quả luôn kèm JSON hướng dẫn ghép trong Unity.

**Có UI kit:** dùng tối đa element trong kit, chỉ tạo element mới khi không có cái nào hợp, vẽ theo đúng style kit. Sprite của kit giữ tên file gốc làm tên group trong PSD, nên khi xuất layer không bị lặp resource.

**Không có UI kit:** skill làm màn demo từ reference hoặc từ mô tả, bạn chốt thì lấy làm mốc style. Sau đó skill dựng bộ component nền theo `ui_kit_standard.md` và thêm phần riêng cho từng màn, để màn nào cũng có chi tiết riêng.

**Nền:** màn nào cũng có nền, lấy từ file bạn add, từ UI kit hoặc tạo mới theo art style. HUD có ảnh cảnh gameplay, popup dùng màn cha làm mờ.

## Form

Form mở trên trình duyệt qua localhost. Form có câu chọn một hoặc nhiều đáp án, ô mô tả và nút đính kèm file cho từng lựa chọn, mô tả riêng cho từng file. Câu hỏi hiện theo câu trả lời trước, câu bắt buộc chưa trả lời thì không gửi được, và câu trả lời cũ được điền sẵn khi mở lại. Bấm **Hoàn thành** thì Codex nhận câu trả lời và làm tiếp.

File đính kèm lưu ở `inputs/` trong kit. File trùng nội dung chỉ lưu một lần, file ZIP được giải nén, file bạn bỏ đi thì bị xoá, nên không sinh rác mỗi lần hỏi.

Danh sách thể loại, art style và màn hình lấy từ sheet UI KIT FILTER, lưu ở `game-ui-kit/references/catalog.md`. Câu hỏi của từng form nằm ở `game-ui-kit/forms/*.json`, sửa file đó để đổi câu hỏi. Bộ base và quy tắc đặt tên (`btn_yellow`, `btn_sp_green`, `title_red`, `set_coin_1`, `loading_bar_yellow_a`...) ở `game-ui-kit/references/ui_kit_standard.md`.

Các ô mô tả gameplay, art style và màn hình có danh sách gợi ý từ UI KIT FILTER. Chọn một gợi ý để điền rồi chỉnh sửa trực tiếp trong ô. Form đọc dữ liệu đã lưu trong `game-ui-kit/references/form_suggestions.json`.

Nhóm **Mẫu bạn đã dùng** đọc các brief Game UI Kit đã gửi trên máy để gợi ý theo thể loại game, art style hoặc màn và vùng tương ứng. Mẫu dùng trong nhiều bộ UI được ưu tiên. Chỉ mục lịch sử lưu đường dẫn tới các bộ UI trên máy, còn nội dung vẫn nằm trong brief của từng bộ.

## Kết quả

Mọi thứ nằm trong `ui_art/<tên_game>/`: wireframe ở `preview/wireframes/`, mockup ở `preview/mockups/`, demo ở `demo/index.html`, file xuất ở `export/psd/`, `export/png/`, `export/unity/`. Mockup, PSD và JSON chưa phải màn hình dựng trong game engine.

## File PSD

Mục tiêu: bạn sửa lại được mọi layer, effect và ảnh trong file, và dùng file làm bản gốc.

- **Vẽ lại bằng shape và layer effect.** Trước khi xuất, mỗi sprite UI được dựng lại theo một "recipe" (`style/recipes/<element>.json`): các lớp fill, stroke, highlight, bóng là shape riêng, với Stroke, Bevel & Emboss, Drop/Inner Shadow, Glow, Gradient/Color Overlay thật, fill opacity, blend mode và clipping mask. Hình chữ nhật và ellipse là live shape, sửa được kích thước và bo góc trong Properties. Ví dụ một khung: group `frame_activity_home` gồm `fill_rounded_rectangle` (Bevel & Emboss), group `stroke` (Bevel & Emboss) chứa `stroke_rounded_rectangle` (fill 0%, Stroke), và `highlight_top_left`.
- **So với ảnh gốc.** `uikit.py recipe` tự đoán recipe đầu tiên, rồi vẽ ảnh so sánh ảnh gốc, bản dựng lại và chỗ khác ở `preview/recipes/`. Codex chỉnh recipe đến khi khớp.
- **Tên layer** theo mẫu `(chức năng)_(mô tả)_(màu)_(màn)`, màu và màn có thể bỏ, như `icon_settings`, `button_normal_blue`, `bg_character_battle`.
- **Chữ là text layer thật.** Font chưa cài thì dùng Arial và báo lại.
- **Ảnh** (nhân vật, cảnh, chi tiết phức tạp) là smart object giữ ảnh gốc kích thước lớn rồi mới thu nhỏ, phóng lại không vỡ.
- **Group theo quan hệ cha con:** popup chứa panel, panel chứa nút, nút chứa shape, icon và chữ của nó.
- Photoshop không cho script tạo pattern mới, nên bề mặt có hoa văn được vẽ bằng shape hoặc để một layer ảnh clip vào shape, và Codex sẽ báo.
