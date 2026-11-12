# Báo cáo thực hành Day 3 — điền trực tiếp trong fork của bạn

**Cách dùng:** Thay mọi dấu `…` bằng bài làm thật của bạn trước khi nộp link fork trên [LMS](https://aithucchien.vinuni.edu.vn). Giữ nguyên bốn mục và bảng để coach đọc nhanh. Viết ngắn, cụ thể theo ảnh/vùng; không cần thuật ngữ chuyên sâu. Ví dụ trong [hướng dẫn mẫu](../../reports/REPORT_TEMPLATE.md) chỉ giúp hiểu cách điền, không phải câu trả lời để chép lại.

- Mã học viên theo lớp: 2A202603268
- Ngày / CVAT local: 12/11/2026 / CVAT local
- Công cụ đã dùng: CVAT local, sam3

Mã học viên là mã lớp cấp; không cần ghi họ tên trong report nếu kênh [LMS](https://aithucchien.vinuni.edu.vn) đã nhận diện bạn. Chỉ ghi công cụ thật sự đã dùng; không có SAM vẫn làm bài bình thường.

## 1. Bài đã nộp

Ghi tên ZIP đúng như file trong `submissions/` và số ảnh đã vẽ, Save. Chưa làm hoặc export lỗi thì ghi `chưa có`, không tạo ZIP rỗng. Cột điểm là điểm tối đa của task, **không phải điểm tự chấm**.

| Task | File ZIP đúng tên | Hoàn thành mấy ảnh | Điểm tối đa (coach chấm sau) |
| --- | --- | ---: | ---: |
| easy_semantic | `easy_semantic.zip` | 3 / 3 | 20 |
| medium_instance | `medium_instance.zip` | 3 / 3 | 32 |
| hard_panoptic | `hard_panoptic.zip` | 2 / 2 | 30 |
| cp1_holes | chưa có | 0 / 1 | 3 |
| cp2_slice | chưa có | 0 / 1 | 3 |
| cp5_occlusion | chưa có | 0 / 1 | 3 |
| cp3_thin | chưa có | 0 / 1 | 3 |
| cp4_curb | chưa có | 0 / 1 | 3 |
| cp6_coverage | chưa có | 0 / 1 | 3 |
| **Tổng tối đa** | | | **100** |

Nếu export lỗi, ghi task, dữ liệu đã Save đến đâu và lỗi đã báo coach.

## 2. Một quyết định trước khi dùng gợi ý

Chọn object đầu tiên bạn tự vẽ ở `medium_instance`, trước khi xem bất kỳ đề xuất tự động nào cho object đó. Ghi ảnh/vị trí đủ để tìm lại; “quy tắc biên” là lý do bạn chọn hoặc dừng mask ở ranh đó.

- Ảnh, vị trí và object Medium đầu tiên tự vẽ: `000000181542.jpg`, người đi bộ mặc áo dài ở gần trung tâm ảnh, trên vạch qua đường.
- Class và quy tắc tôi dùng để chọn biên: class `person`; chỉ vẽ phần cơ thể nhìn thấy, bám theo biên áo, tay, chân và không tự đoán phần bị xe máy hoặc vật khác che.
- Nếu dùng gợi ý sau đó: không dùng; tôi tự kiểm tra lại từng object trong CVAT trước khi Save.
- Nếu không dùng gợi ý: với các xe máy và người đi bộ ở hai bên ảnh, tôi giữ mỗi vật là một instance riêng dù cùng class hoặc bị che một phần, vì Medium là bài instance segmentation.

## 3. Một lỗi tôi tìm thấy và sửa

Chọn một lỗi **có thật** trong bài. Nếu công cụ lỗi khiến bạn chưa sửa được, ghi rõ đã thử gì và cần coach hỗ trợ gì; không ghi “đã sửa” khi chưa sửa.

- Task/ảnh/vùng: `medium_instance`, ảnh `000000181542.jpg`, vùng các xe máy và người ở tiền cảnh.
- Lỗi thuộc loại: gộp-tách và biên.
- Bằng chứng tôi nhìn thấy: các vật ở gần nhau dễ bị nối mask hoặc bị vẽ lấn sang vật bên cạnh; một số phần bị che có thể khiến biên mask bị kéo vào vùng không nhìn thấy.
- Quy tắc và hành động sửa: tôi kiểm tra theo thứ tự từng object, tách các vật cùng class thành instance riêng, xóa phần mask lấn sang vật bên cạnh và chỉ giữ vùng nhìn thấy trước khi Save.
- Sau sửa đã Save và export lại chưa? Đã Save và export lại `medium_instance.zip`; ZIP có 3 ảnh và 158 annotation RLE.

Nếu bạn **đã xem Summary tự đánh giá trên GitHub Actions hoặc tự chạy script**, ghi ngắn một kết quả liên quan lỗi vừa sửa (ví dụ task, metric trước/sau nếu có): chưa xem Summary và chưa có điểm. Scorecard ba tier tối đa **82**, không phải điểm cuối trên 100. Không tự ghi PASS/top 3/bonus; người phụ trách xác nhận theo tiêu chí lớp. Không đưa file ground truth vào fork.

## 4. Ba ca chưa chắc hoặc đã cân nhắc

Mỗi ca là một **vùng cụ thể** khiến bạn phải cân nhắc hai cách hiểu. Ghi dấu hiệu nhìn thấy hoặc quy tắc đã dùng, rồi nêu quyết định hoặc câu hỏi cho coach. Không cần ba lỗi; ca đã quyết định được cũng hợp lệ.

| Ảnh/vị trí | Hai cách hiểu có thể | Quy tắc/chứng cứ | Quyết định hoặc câu hỏi cho coach |
| --- | --- | --- | --- |
| 1. `000000181542.jpg`, người đi bộ ở giữa ảnh bị xe máy che một phần | Có thể tách phần nhìn thấy thành nhiều object, hoặc giữ là một người duy nhất | Cùng một người vẫn là một instance; không vẽ xuyên qua phần bị che và chỉ giữ biên nhìn thấy | Giữ một mask `person` cho người đó, không tách theo các mảng bị che |
| 2. `000000181542.jpg`, các xe máy chạy sát nhau ở tiền cảnh | Có thể gộp thành một mask vì biên giữa hai xe khó thấy, hoặc tách thành hai object | Hai vật khác nhau phải là hai instance dù cùng class; quan sát bánh xe, tay lái và thân xe để tìm biên | Tách từng xe máy, đồng thời bỏ phần mask lấn sang xe bên cạnh |
| 3. `000000373353.jpg`, ranh giữa vùng đường và phần lề/nền ở ảnh giao thông | Có thể chọn theo màu tối/sáng, hoặc theo chức năng của vùng | Với semantic/panoptic, road và sidewalk là các class khác nhau; không quyết định chỉ bằng màu khi ánh sáng thay đổi | Ưu tiên ranh hình học và chức năng sử dụng của vùng; chỗ không chắc thì không tự vẽ quá rộng |
