# Chạy SAM 3 local và nhập semantic mask vào CVAT

Pipeline này chạy SAM 3 bên ngoài CVAT, sau đó tạo ZIP `Segmentation mask 1.1` để nhập vào CVAT. Nó không cài SAM 3 vào CVAT server và không cung cấp interactor click/box trong giao diện CVAT.

## 1. Chuẩn bị model

Checkpoint là file trọng số của model, không phải một gói API trả phí. Người dùng cần đăng nhập Hugging Face, xin quyền truy cập model `facebook/sam3`, tải `sam3.pt` về máy và giữ file này local. Việc suy luận của script không gửi ảnh lên dịch vụ tính phí.

Ultralytics yêu cầu checkpoint SAM 3 được tải riêng; xem [tài liệu SAM 3 của Ultralytics](https://docs.ultralytics.com/models/sam-3) và [trang model Hugging Face](https://huggingface.co/facebook/sam3).

## 2. Cài dependency tùy chọn

Từ thư mục gốc repo:

```powershell
py -m pip install -r requirements-sam3.txt
```

Nếu máy có GPU CUDA, nên cài PyTorch phù hợp với CUDA trước khi cài Ultralytics. CPU vẫn được truyền qua `--device cpu` nhưng có thể chậm và cần nhiều RAM.

## 3. Sinh ZIP semantic

Ví dụ với task `easy_semantic`:

```powershell
py scripts/sam3_semantic.py `
  --model C:\models\sam3.pt `
  --images data\tiers\easy_semantic\images `
  --classes data\tiers\easy_semantic\classes.json `
  --output submissions\easy_semantic.zip `
  --device auto `
  --conf 0.25
```

Script dùng từng tên trong `classes.json` làm text prompt. Nếu mask của nhiều class chồng lấn, pixel được gán cho mask có confidence cao hơn; pixel không thuộc mask nào là background/unlabeled.

## 4. Nhập và kiểm trong CVAT

Trong CVAT, tạo task với đúng ảnh và label của `classes.json`, sau đó dùng chức năng import annotations/dataset với ZIP semantic vừa tạo. Mở Job để kiểm tra ranh giới, vùng bỏ sót và class; SAM 3 chỉ tạo gợi ý, không thay thế bước QC thủ công.

Có thể kiểm cấu trúc ZIP trước khi import:

```powershell
py scripts/inspect_submissions.py --task easy_semantic --dir submissions
```

Validator chỉ kiểm hợp đồng file, ảnh, class và mask; nó không chứng minh chất lượng biên mask.
