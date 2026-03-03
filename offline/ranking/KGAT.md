# KGAT – Giải thích từ A đến Z (không thuật ngữ bừa bãi)

> Tài liệu này giải thích cách mô hình KGAT hoạt động và được huấn luyện,
> dùng ngôn ngữ gần gũi nhất có thể.

---

## 1. Bài toán cần giải

Sau khi hệ thống tìm kiếm lấy ra ~100 sản phẩm từ Neo4j, chúng ta cần **sắp xếp lại** theo từng người dùng — người thích Samsung thì Samsung lên đầu, người thích Xiaomi giá rẻ thì Xiaomi giá rẻ lên đầu.

Đây là bài toán **cá nhân hóa thứ tự** (personalized re-ranking).

---

## 2. Tại sao không dùng cách đơn giản hơn?

### Cách đơn giản: đếm lịch sử

> "User đã mua Samsung 3 lần → ưu tiên Samsung"

Vấn đề: dữ liệu **quá thưa**. Hệ thống có 20.283 user × 1.179 sản phẩm,
nhưng chỉ có 26.167 lượt đánh giá — tức mỗi user trung bình chỉ tương tác với
**1,3 sản phẩm**. Đa số user chưa đụng vào phần lớn catalogue.

### Vấn đề với cách thông thường (Collaborative Filtering)

Collaborative Filtering (CF) hoạt động theo nguyên lý:
> "User A và user B đều thích X → nếu B thích Y thì A có thể cũng thích Y"

Nhưng với dữ liệu thưa như trên, rất ít user có đủ điểm chung để so sánh.
Sản phẩm mới hay ít phổ biến hầu như không được gợi ý.

### Giải pháp: dùng thêm thông tin từ Knowledge Graph

Knowledge Graph (KG) chứa thông tin **bên cạnh** sản phẩm:
- Điện thoại A → do Samsung sản xuất
- Điện thoại A → hỗ trợ 5G
- Điện thoại A → RAM 8GB
- Điện thoại A → thường mua kèm ốp lưng B

Nhờ đó, dù user chưa thấy sản phẩm Y bao giờ, nếu Y cùng brand và cùng tính
năng với X mà user đã thích → model có thể suy luận user sẽ thích Y.

**KGAT là mô hình khai thác được cả hai nguồn thông tin đó.**

---

## 3. Ý tưởng cốt lõi: "mọi thứ đều là điểm trong không gian"

KGAT biểu diễn **mọi thực thể** (user, sản phẩm, brand, tính năng, carrier...)
dưới dạng một **vector số** (gọi là embedding).

```
"Samsung"   →  [0.8, -0.2, 0.5, ...]   # 64 con số
"user_A"    →  [0.7, -0.1, 0.6, ...]
"iPhone 15" →  [-0.3, 0.9, 0.1, ...]
```

Sau khi huấn luyện, hai thứ **liên quan đến nhau** sẽ có vector **gần nhau**
trong không gian. Khi cần tính "user A có thích sản phẩm X không?",
ta chỉ cần đo **độ tương đồng** giữa hai vector đó (nhân chấm — dot product).

---

## 4. Dữ liệu đầu vào (`build_data.py`)

Trước khi train, cần chuẩn bị dữ liệu từ Knowledge Graph đã có trong Neo4j.

### 4.1 Đánh số tất cả mọi thứ

Máy tính không hiểu tên, chỉ hiểu số. Bước đầu tiên là gán một số nguyên cho
từng thực thể:

```
user_A        → 0
user_B        → 1
...
product_X     → 20283   (users được đánh trước, products sau)
product_Y     → 20284
...
Samsung       → 21462
5G            → 21500
```

> **Tại sao users trước?** Để dễ tính offset: tất cả ID từ 0 đến 20282 là users,
> từ 20283 trở đi là sản phẩm.

### 4.2 Lọc tương tác dương

Từ các lượt đánh giá trong KG, chỉ giữ lại đánh giá **≥ 3/5 sao** — coi đó là
"user thích sản phẩm này". Rating thấp hơn bị bỏ qua.

Kết quả: ~26.167 cặp (user, sản phẩm) dương tính.

### 4.3 Xây dựng đồ thị thống nhất (CKG)

Ghép **lịch sử tương tác** và **quan hệ KG** thành một đồ thị duy nhất:

```
CKG = [user đã rate sản phẩm]
    + [sản phẩm do brand sản xuất]
    + [sản phẩm thuộc danh mục]
    + [sản phẩm hỗ trợ công nghệ]
    + ... (10 loại quan hệ KG)
```

Mỗi cạnh đều có **cả hai chiều** (forward + inverse):
- `Samsung → sản xuất → Galaxy S24`
- `Galaxy S24 → được sản xuất bởi → Samsung`

Điều này giúp thông tin lan truyền được theo cả hai hướng.

**Kết quả cuối cùng:** ~95.000 cạnh, ~28.000 nút.

---

## 5. Kiến trúc mô hình (`model.py`)

### 5.1 Bắt đầu: mỗi thực thể có một vector ngẫu nhiên

```
27.989 thực thể × 64 chiều = ma trận embedding ban đầu (ngẫu nhiên)
```

Mục tiêu của quá trình huấn luyện: **điều chỉnh các số này** sao cho
vector của user gần với vector của sản phẩm user thích.

### 5.2 Lan truyền thông tin qua đồ thị (3 lớp)

Đây là điểm mấu chốt của KGAT. Thay vì chỉ dùng thông tin trực tiếp của một
thực thể, mô hình **thu thập thông tin từ hàng xóm** trong đồ thị.

**Ví dụ trực quan:**

```
Lớp 1 (1-hop): Samsung biết được mình sản xuất loại sản phẩm nào
Lớp 2 (2-hop): User A biết được brand và tính năng của sản phẩm đã thích
Lớp 3 (3-hop): User A biết được sản phẩm nào cùng brand với sản phẩm đã thích
```

Sau 3 lớp, vector của user đã "hấp thụ" thông tin từ xa:
`user → sản phẩm → brand → sản phẩm khác cùng brand`.

### 5.3 Cơ chế chú ý (Attention) — không phải mọi hàng xóm đều bằng nhau

Tất cả 10 loại quan hệ trong KG (brand, RAM, shop, carrier, công nghệ, danh mục,
tính năng, phụ kiện, thường mua cùng, danh mục cha) **đều được đưa vào đồ thị**.
Model học **trọng số khác nhau** cho từng loại quan hệ tùy theo từng user:

```
Với user hay chọn theo cấu hình phần cứng:
  - Hàng xóm "RAM = 8GB"             → trọng số CAO
  - Hàng xóm "Brand = Samsung"       → trọng số TRUNG BÌNH
  - Hàng xóm "Accessory = USB Cable" → trọng số THẤP

Với user trung thành với hãng:
  - Hàng xóm "Brand = Samsung"       → trọng số CAO
  - Hàng xóm "RAM = 8GB"             → trọng số THẤP hơn
```

Model tự học các trọng số này qua quá trình train — không cần cấu hình tay.

Công thức tính trọng số:
```
trọng_số(h, quan_hệ, hàng_xóm) = độ_tương_đồng(
    vector_hàng_xóm,
    tanh(vector_h + vector_quan_hệ)   ← "context" hóa h theo loại quan hệ
)
```

Sau đó chuẩn hóa để tổng tất cả trọng số = 1 (softmax).

### 5.4 Vector cuối: ghép tất cả các lớp lại

```
vector_cuối = [vector_lớp_0 | vector_lớp_1 | vector_lớp_2 | vector_lớp_3]
            = 64 + 64 + 64 + 64 = 256 chiều
```

Ghép lại thay vì chỉ lấy lớp cuối vì:
- Lớp 0: thông tin bản thân (0-hop)
- Lớp 1: thông tin hàng xóm trực tiếp
- Lớp 2: thông tin hàng xóm cấp 2
- Lớp 3: thông tin hàng xóm cấp 3

Mỗi mức mang một góc nhìn khác nhau.

---

## 6. Quá trình huấn luyện (`train.py`)

### 6.1 Chia dữ liệu train / val

10% tương tác của mỗi user được giữ lại để **kiểm tra** (validation),
90% còn lại dùng để **huấn luyện**.

Việc chia này được lưu cố định vào file `checkpoints/kgat_split.json` để
mỗi lần train lại đều dùng cùng một tập kiểm tra — kết quả so sánh mới có ý nghĩa.

> Quan trọng: CKG dùng để train chỉ chứa tương tác từ **tập train**,
> không được nhìn vào tập val. Tránh "gian lận" khi đánh giá.

### 6.2 Vòng lặp huấn luyện (mỗi epoch)

Mỗi epoch gồm nhiều **bước nhỏ** (step), mỗi bước:

```
Bước 1: Tính embedding mới cho tất cả 28K thực thể
        (chạy qua toàn bộ 95K cạnh của đồ thị)

Bước 2: Lấy mẫu 1.024 bộ (user, sản phẩm_thích, sản phẩm_không_thích)

Bước 3: Tính loss → cập nhật tham số mô hình

Bước 4: Lặp lại
```

### 6.3 Cách lấy mẫu học (BPR Sampling)

Mô hình học theo kiểu **so sánh cặp**:
> "Score của (user, sản phẩm đã thích) phải CAO HƠN score của (user, sản phẩm ngẫu nhiên)"

Với mỗi bước:
- Chọn ngẫu nhiên một user
- Chọn một sản phẩm user **đã thích** (positive)
- Chọn một sản phẩm user **chưa tương tác** (negative — giả định không thích)

```
Ví dụ:
  user_A thích Galaxy S24  ✓
  user_A chưa thấy Redmi Note 12  ✗ (giả sử)

→ Model học: score(A, Galaxy S24) > score(A, Redmi Note 12)
```

### 6.4 Hàm Loss (BPR Loss) — thước đo "học tốt đến đâu"

```
Loss = -log( sigmoid(score_positive - score_negative) ) + phạt độ lớn vector
```

Hiểu nôm na:
- Nếu `score_positive` >> `score_negative` → Loss nhỏ → tốt
- Nếu `score_positive` ≈ `score_negative` → Loss lớn → cần học thêm
- Phạt độ lớn vector: ngăn các số trong vector phình quá to (overfitting)

### 6.5 Learning rate giảm dần

Tốc độ học giảm một nửa mỗi 10 epoch.
Lý do: giai đoạn đầu cần học nhanh, giai đoạn sau cần điều chỉnh tinh tế hơn.

```
Epoch 1-10:   lr = 5e-5
Epoch 11-20:  lr = 2.5e-5
Epoch 21-30:  lr = 1.25e-5
```

### 6.6 Đánh giá sau mỗi epoch

Sau mỗi epoch, mô hình được đánh giá trên tập val:

**Recall@10**: Trong 10 sản phẩm gợi ý hàng đầu, bao nhiêu % là sản phẩm
user thực sự thích?

**NDCG@10**: Giống Recall@10 nhưng thưởng thêm nếu sản phẩm đúng xuất hiện
ở vị trí càng cao càng tốt (rank 1 > rank 2 > ... > rank 10).

> Sản phẩm đã dùng để train bị **che đi** trước khi đánh giá để không bị đếm
> hai lần (model biết trước nên score rất cao — không công bằng).

**Lưu checkpoint tốt nhất:** mỗi khi Recall@10 trên val cải thiện,
model được lưu vào `checkpoints/best_model.pt`.

---

## 7. Sơ đồ tổng quát quá trình huấn luyện

```
Knowledge Graph (Neo4j)
        │
        ▼
[build_data.py]
  ├── Đánh số 28K thực thể
  ├── Lọc 26K tương tác dương (rating ≥ 3)
  └── Xây CKG: 95K cạnh (KG + tương tác + inverse)
        │
        ▼ data/
[train.py]
  ├── Chia 90% train / 10% val (cố định)
  ├── Khởi tạo 28K × 64 vector ngẫu nhiên
  │
  └── Lặp 20 epochs:
        ├── Forward pass: lan truyền qua 95K cạnh → 3 lớp attention
        ├── BPR sampling: 1024 bộ (user, thích, không_thích)
        ├── Tính loss → cập nhật vector
        ├── Đánh giá Recall@10 / NDCG@10
        └── Lưu best_model.pt nếu cải thiện
        │
        ▼
checkpoints/best_model.pt
```

---

## 8. Sau khi train: dùng model như thế nào (`rerank.py`)

Khi có request tìm kiếm, pipeline trả về danh sách ~100 ASIN từ Neo4j.
`KGATReranker` sắp xếp lại theo từng user:

```python
# 1. Load model một lần duy nhất khi khởi động server
reranker = KGATReranker()   # đọc best_model.pt

# 2. Với mỗi request tìm kiếm
ranked_asins = reranker.rerank(
    user_id="AHATA6X6MYTC3VNBFJ3WIYVK257A",
    product_asins=["B00M78E4MS", "B075QWLV3J", ...],   # 100 candidates
)
# → trả về danh sách đã sắp xếp, phù hợp nhất đứng đầu
```

**Cách tính score:**
```
score(user, sản_phẩm) = vector_user · vector_sản_phẩm   (nhân chấm 256 chiều)
```

Sau đó sort giảm dần theo score.

### Xử lý user mới (cold-start)

Nếu user chưa có trong tập train (user mới đăng ký):
- Không có vector riêng → dùng **vector trung bình** của tất cả users
- Kết quả: gợi ý "phổ thông" thay vì cá nhân hóa
- Chất lượng thấp hơn user cũ, nhưng vẫn tốt hơn random vì
  sản phẩm có nhiều kết nối trong KG vẫn được rank cao hơn

---

## 9. Tóm tắt nhanh

| Câu hỏi | Trả lời |
|---|---|
| Model học cái gì? | Vector số đại diện cho user và sản phẩm |
| Học theo kiểu gì? | So sánh cặp: sản phẩm đã thích > sản phẩm chưa thích |
| Dùng KG để làm gì? | Lan truyền thông tin 3 bước qua đồ thị để hiểu ngữ cảnh |
| Đánh giá bằng gì? | Recall@10 và NDCG@10 trên 10% tương tác giữ lại |
| Dùng lúc inference? | Nhân vector user với vector sản phẩm → sort |
| User mới thì sao? | Dùng vector trung bình của tất cả users |

---

## 10. Các thông số mặc định và lý do chọn

| Thông số | Giá trị | Lý do |
|---|---|---|
| Số chiều vector | 64 | Cân bằng giữa biểu diễn đủ phong phú và tốc độ tính toán với 28K thực thể |
| Số lớp lan truyền | 3 | Bắt được thông tin 3 bước xa: user → sản phẩm → brand → sản phẩm khác |
| Dropout | 0.1 | Ngăn model quá phụ thuộc vào một số đặc trưng cụ thể |
| L2 regularization | 1e-5 | Ngăn vector phình to quá mức |
| Learning rate | 5e-5 | Đủ chậm để ổn định với Adam optimizer |
| Batch size | 1024 | Phù hợp với bộ nhớ CPU/GPU thông thường |
| Ngưỡng rating | 3.0/5 | Trung lập đến tích cực → coi là "thích" |
| Tỷ lệ val | 10% | Đủ để đánh giá mà không lãng phí dữ liệu train |
