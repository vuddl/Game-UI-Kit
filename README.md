# Game UI Kit

Skill cho Codex để làm wireframe, UI visual mockup và xuất file thiết kế cho game. Mọi câu hỏi lớn đều hỏi bằng form trong trình duyệt. Skill tạo bộ artwork UI (nút kèm trạng thái, panel, thanh, khung, icon) thành PNG trong suốt có tên rõ ràng và dữ liệu 9-slice, ghép mockup từ chính các sprite, rồi xuất PSD, PNG và JSON hướng dẫn ghép trong Unity. Skill không dựng màn hình trong game engine.

Skill tạo ảnh bằng `image_gen` có sẵn trong Codex, chạy trên tài khoản Codex đang đăng nhập, không cần API key.

## Cài đặt

Trong PowerShell, lệnh này cài hoặc cập nhật skill chính và 6 lệnh `$setup`, `$wireframe`, `$mockup`, `$export`, `$reset`, `$info`. Lệnh cũng xoá các lệnh `$gui-...` cũ:

```powershell
py -3 -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/vuddl/Game-UI-Kit/main/game-ui-kit/scripts/update.py').read())"
```

Script cần Python 3 kèm Pillow và numpy:

```powershell
py -3 -m pip install pillow numpy
```

Sau đó mở một phiên Codex mới. Gõ `$setup` để bắt đầu thiết kế, hoặc `$export` nếu đã có ảnh mockup UI. Xuất PSD sửa được cần cài Photoshop trên máy. Bảng chọn bấm được giữa các bước cần app Codex Desktop; nơi khác thì Codex hỏi bằng lựa chọn đánh số.

## Lệnh

| Lệnh | Tác dụng |
|---|---|
| `$setup` | Form định hình game: màn dọc, ngang hay tự nhập kích thước; thể loại game; gameplay. Cần cho `$wireframe` và `$mockup`; `$export` chạy độc lập |
| `$wireframe` | Làm wireframe từng màn hoặc nhiều màn cùng lúc. Kết quả là ảnh PNG |
| `$mockup` | Làm UI visual mockup từng màn hoặc nhiều màn cùng lúc. Khi hoàn tất, có thể chuyển sang quy trình `$export` |
| `$export` | Xuất từ ảnh mockup có sẵn hoặc màn trong kit; chọn nhiều loại file cùng lúc. Không cần `$setup`, `$wireframe` hay `$mockup` trước đó |
| `$reset` | Xoá hết những gì lệnh đang làm đã tạo, rồi làm lại lệnh đó từ đầu. Reset khi đang ở `$setup` thì xoá luôn setup |
| `$info` | Thông báo những gì đã lưu: setup (kích thước, hướng màn, thể loại, gameplay), câu trả lời từng màn của wireframe và mockup, ảnh kết quả, file export, và lệnh đang làm tới bước nào. Không thay đổi gì |

Codex trả lời bằng tiếng Việt. Nội dung hiển thị trên wireframe, concept, mockup và prototype dùng tiếng Anh.

Quy tắc chuyển lệnh (`$info` chỉ xem, không tính là chuyển lệnh):

- Gõ lệnh khác khi đang làm dở: bỏ lệnh cũ, sang ngay lệnh mới. Phần đã làm vẫn giữ.
- Gõ lại đúng lệnh đang làm: không có gì thay đổi, làm tiếp từ chỗ dở.
- Quay lại một lệnh đã bỏ dở: làm tiếp từ chỗ dở của lệnh đó.

## Luồng `$wireframe`

1. Chọn **Làm 1 màn · Chi tiết hơn** hoặc **Làm nhiều màn · Ít chi tiết hơn** ngay từ đầu, sau `$setup`. Wireframe không cần làm một màn trước hay chốt style art. Form một màn hỏi: màn gì, chức năng, mô tả từng vùng (dọc: Top, Middle, Bottom; ngang: Top, Left, Right, Bottom), có tạo prototype không, tạo mấy option. Form nhiều màn cho chọn màn, mô tả/ảnh tham chiếu, có tạo prototype mô phỏng luồng không và số option cho mỗi màn (1–5).
   Ô chức năng gợi ý một mô tả chung ngắn theo màn đã chọn để bạn duyệt; chi tiết từng vùng điền ở các trường bên dưới.
   Mô tả chung và từng vùng có thể đính kèm ảnh. Dán ảnh chụp màn hình hoặc ảnh đã copy bằng **Ctrl+V** vào ô mô tả hoặc khu vực tải file; form hiện ảnh xem trước và cho phép ghi chú, xóa ảnh. Các khu vực tải file trong các form khác cũng hỗ trợ dán ảnh.
   Bấm vào ảnh thu nhỏ để xem ảnh lớn ngay trên form. Bấm **Đóng**, nhấn **Esc** hoặc bấm nền tối để quay lại nội dung đang điền.
2. Sau khi hiện wireframe một màn hoặc hàng loạt, Codex mở bảng hỏi **Bạn có muốn chỉnh sửa tiếp không?** với hai lựa chọn **Có / Không**.
3. **Có** mở form sửa có ảnh xem trước. Bạn chọn các bản cần sửa, ghi yêu cầu và đính kèm ảnh minh họa cho từng bản. Sửa xong, Codex hiện kết quả và hỏi lại.
4. Khi bạn yêu cầu làm thêm màn, có thể chọn **Làm nhiều màn · Ít chi tiết hơn** hoặc **Làm 1 màn · Chi tiết hơn**.
5. **Không** hoàn tất ảnh PNG và demo bấm thử nếu đã chọn tạo prototype; lúc này Codex mới gợi ý dùng `$mockup` để thiết kế hình ảnh.

Wireframe được dựng bằng HTML rồi chụp bằng Edge hoặc Chrome chạy ngầm. Màn có thẻ bo góc, icon, chữ dễ đọc, thanh tiến độ và thanh điều hướng có tab đang chọn. Các liên kết chuyển màn được thêm khi bạn chọn làm prototype.

## Luồng `$mockup`

1. Form tạo mockup: add wireframe (PNG, ZIP...), mỗi file là một màn, có ô **Tên màn** (gợi ý thả xuống, để trống thì Codex tự đoán) và ô **Mô tả màn**. Wireframe làm từ `$wireframe` được điền sẵn. Tiếp theo: có UI kit không (có: add kit; không: add ảnh reference hoặc tự sáng tạo), màu, sáng hay dark theme, UI style (có reference thì các câu này không bắt buộc, để trống thì lấy theo reference), có background sẵn không, tạo mấy option.
2. Chỉ có một ô **Tạo mấy option demo cho mỗi màn?** (1–5), áp dụng cho cả màn đầu chọn style và các màn làm tiếp. Sau mỗi lần chốt demo, chọn **Làm tiếp demo màn khác**, **Tạo UI kit sprite** hoặc **Dừng tại demo**. Có thể làm demo một màn hoặc nhiều màn tiếp theo theo style màn đầu; mỗi màn được duyệt riêng. Chốt demo chưa bắt đầu tạo sprite.
3. Khi bạn yêu cầu **Tạo UI kit sprite**, Codex mới tạo bộ sprite dùng chung và riêng cho các màn có demo đã duyệt, rồi ghép lại bám theo bố cục và hình thức của từng demo đã chốt. Demo thiết kế và kết quả ghép sprite được lưu riêng để đối chiếu.
4. Sau khi kiểm tra kết quả ghép sprite, Codex hỏi **Export không?**. Nếu có, chuyển sang cùng quy trình `$export` bên dưới và chỉ xuất các loại file bạn đã chọn. Dừng tại demo thì lưu tiến độ và ảnh đã duyệt để làm tiếp sau.

## Luồng `$export`

Gọi trực tiếp khi có sẵn một hoặc nhiều ảnh UI mockup. Form nhận ảnh PNG/JPG/WebP/PSD hoặc ZIP, tên màn và ghi chú; ảnh đã gửi trong chat được điền sẵn. Skill đọc kích thước riêng của từng ảnh, nhận diện và dựng lại component, chữ, artwork và background để xuất file. Không cần tạo setup game hay chạy các lệnh thiết kế trước.

Khi chọn xuất PSD, chọn bản Photoshop ngay trong form để tự kiểm tra và cấu hình tắt cảnh báo chạy script. Nếu Photoshop đang chạy với cấu hình cũ, form yêu cầu mở lại một lần rồi bấm **Kiểm tra lại**; chưa chạy script khi cấu hình chưa sẵn sàng.

**Bạn muốn xuất những file nào?** Có thể chọn nhiều mục cùng lúc:

| Lựa chọn | Chú thích |
|---|---|
| **Bộ UI kit và ảnh demo** | Tạo UI kit từ ảnh demo, gồm sprite dùng chung, element riêng từng màn và ảnh PNG ghép UI hoàn chỉnh. |
| **Bộ UI kit (PSD)** | Gom các thành phần UI vào `components.psd`, chia layer để chỉnh sửa trong Photoshop. |
| **PSD từng màn** | Mỗi màn một file Photoshop, tách riêng nhóm UI, chữ và artwork. |
| **Dữ liệu ghép Unity (JSON)** | Lưu cấu trúc, vị trí, kích thước, anchors và thông tin tài nguyên để ghép màn trong Unity. |
| **Gói ZIP và báo cáo** | Đóng gói các file đã chọn, kèm danh sách tài nguyên, kết quả kiểm tra và những hạn chế còn lại. Chọn cùng ít nhất một loại file khác. |

Với một trong hai lựa chọn PSD, form dò các bản Photoshop trên máy người dùng, liệt kê phiên bản và đường dẫn để chọn trước khi tạo file. Mỗi lần export phải chọn lại, kể cả khi chỉ có một bản. Skill dùng đúng bản đã chọn; khi không chạy được sẽ báo lỗi. Có thể nhập đường dẫn tới bản Photoshop mà bộ dò chưa tìm thấy. Các lựa chọn khác không yêu cầu Photoshop.

Gói UI kit và demo có cấu trúc `UI/Base/<nhóm dùng chung>/...` và `UI/<tên màn>/demo/...`, cùng element riêng trong folder màn tương ứng. Tên nhóm trong `Base` được chọn theo tài nguyên thực tế của từng game, không tạo sẵn bộ thư mục cố định hay thư mục rỗng. Mỗi tài nguyên giống nhau chỉ xuất một lần; các màn dùng chung tham chiếu về tài nguyên đã có. [Quy trình export độc lập](game-ui-kit/references/export.md).

**Có UI kit:** dùng tối đa element trong kit, chỉ tạo element mới khi không có cái nào hợp, vẽ theo đúng style kit. Sprite của kit giữ tên file gốc làm tên group trong PSD, nên khi xuất layer không bị lặp resource.

**Không có UI kit:** skill làm màn demo từ reference hoặc từ mô tả, bạn chốt thì lấy làm mốc style. Sau đó skill dựng bộ component nền theo `ui_kit_standard.md` và thêm phần riêng cho từng màn, để màn nào cũng có chi tiết riêng.

**Nền:** màn nào cũng có nền, lấy từ file bạn add, từ UI kit hoặc tạo mới theo art style. HUD có ảnh cảnh gameplay, popup dùng màn cha làm mờ.

Khi nhận ảnh demo mockup UI, skill nhận diện phần nền, UI và các vật thể cần tách riêng, làm sạch nền và bổ sung phần bị UI che. Sau đó skill tính vùng cần vẽ mở rộng theo các kích thước màn hình cần hỗ trợ, giữ hình ảnh chính trong vùng nhìn thấy và kiểm tra cả nền sạch lẫn bản ghép UI. Nền dùng scale đồng tỷ lệ, crop phần dư; file Unity kèm kích thước master, cách căn và dữ liệu kiểm tra. Có thể điền phạm vi màn hình trong form mockup; nếu để trống, skill nêu rõ phạm vi mặc định theo hướng dọc/ngang. Các trường hợp cần tách lớp hoặc dùng nhiều biến thể sẽ được báo cụ thể. [Quy trình background multisize](game-ui-kit/references/backgrounds.md).

## Form

Form mở trên trình duyệt qua localhost. Form có câu chọn một hoặc nhiều đáp án, ô mô tả và nút đính kèm file cho từng lựa chọn, mô tả riêng cho từng file. Câu hỏi hiện theo câu trả lời trước, câu bắt buộc chưa trả lời thì không gửi được, và câu trả lời cũ được điền sẵn khi mở lại. Bấm **Hoàn thành** thì Codex nhận câu trả lời và làm tiếp.

File đính kèm lưu ở `inputs/` trong kit. File trùng nội dung chỉ lưu một lần, file ZIP được giải nén, file bạn bỏ đi thì bị xoá, nên không sinh rác mỗi lần hỏi.

Danh sách thể loại, art style và màn hình lấy từ sheet UI KIT FILTER, lưu ở `game-ui-kit/references/catalog.md`. Câu hỏi của từng form nằm ở `game-ui-kit/forms/*.json`, sửa file đó để đổi câu hỏi. Bộ base và quy tắc đặt tên (`btn_yellow`, `btn_sp_green`, `title_red`, `set_coin_1`, `loading_bar_yellow_a`...) ở `game-ui-kit/references/ui_kit_standard.md`.

Các ô mô tả gameplay, art style và màn hình có danh sách gợi ý từ UI KIT FILTER. Chọn một gợi ý để điền rồi chỉnh sửa trực tiếp trong ô. Form đọc dữ liệu đã lưu trong `game-ui-kit/references/form_suggestions.json`.

Nhóm **Mẫu bạn đã dùng** đọc các brief Game UI Kit đã gửi trên máy để gợi ý theo thể loại game, art style hoặc màn và vùng tương ứng. Mẫu dùng trong nhiều bộ UI được ưu tiên. Chỉ mục lịch sử lưu đường dẫn tới các bộ UI trên máy, còn nội dung vẫn nằm trong brief của từng bộ.

## Kết quả

Mọi thứ nằm trong `ui_art/<tên_game>/`: wireframe ở `preview/wireframes/`, mockup ở `preview/mockups/`, prototype ở `demo/index.html`. Các file bàn giao đã chọn nằm trong `export/delivery/`; file dựng và báo cáo nội bộ ở những thư mục export còn lại. `$info` xem được phiên export ngay cả khi không có setup; `$reset` cũng áp dụng cho `$export`. Mockup, PSD và JSON chưa phải màn hình dựng trong game engine.

## File PSD

- Button, popup, panel, frame và các component tái sử dụng dùng Shape Layers và Layer Effects chỉnh được trong Photoshop. Bản dựng phải đạt ít nhất 95% độ giống demo đã chốt. Codex kiểm tra bằng ảnh render từ Photoshop.
- Icon và decor phức tạp, cụm minh họa và VFX giữ ảnh nguồn chất lượng cao trong Smart Object trước khi thu nhỏ. Icon silhouette một màu hoặc hình đơn giản dùng shape và effect. Ảnh trong khung giữ nguyên ảnh vuông hoặc chữ nhật và clip vào shape riêng. Chữ UI là text layer.
- Khi chọn **Bộ UI kit (PSD)**, Codex tạo `components.psd`. Mỗi sprite có canvas trong suốt cắt sát, chiều rộng và chiều cao chia hết cho 4, và được kiểm tra 9-slice nếu cần co giãn.

[Quy tắc dựng và xuất Photoshop](game-ui-kit/references/photoshop.md)
