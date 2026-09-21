import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'ma_bao_mat_danh_cho_gio_hang_va_dang_nhap'

# Cấu hình thư mục lưu ảnh QR tải lên
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Cấu hình Cơ sở dữ liệu SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- BẢNG DỮ LIỆU (MODELS) ---

class MonAn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ten = db.Column(db.String(100), nullable=False)
    gia = db.Column(db.Integer, nullable=False)
    hinh = db.Column(db.String(255), nullable=False)
    loai = db.Column(db.String(50), nullable=False, default='Đồ ăn')

class DonHang(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ten_khach = db.Column(db.String(100), nullable=False)
    sdt = db.Column(db.String(20), nullable=False)
    diachi = db.Column(db.String(200), nullable=False)
    tong_tien = db.Column(db.Integer, nullable=False)
    trang_thai = db.Column(db.String(50), nullable=False, default='Chờ xử lý')
    ngay_dat = db.Column(db.DateTime, default=datetime.now)

class NguoiDung(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tai_khoan = db.Column(db.String(50), unique=True, nullable=False)
    mat_khau = db.Column(db.String(50), nullable=False)
    vai_tro = db.Column(db.String(20), nullable=False, default='NhanVien')

class CauHinhNganHang(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.String(20), nullable=False, default="MB")
    account_no = db.Column(db.String(50), nullable=False, default="0987654321")
    account_name = db.Column(db.String(100), nullable=False, default="NGUYEN VAN A")
    qr_custom_url = db.Column(db.String(500), nullable=True, default="")

# Khởi tạo CSDL và dữ liệu mặc định
with app.app_context():
    db.create_all()
    if CauHinhNganHang.query.count() == 0:
        db.session.add(CauHinhNganHang(bank_id="MB", account_no="0987654321", account_name="NGUYEN VAN A", qr_custom_url=""))
        db.session.commit()

    if MonAn.query.count() == 0:
        danh_sach_mau = [
            MonAn(ten="Cơm Tấm Sườn Bì Chả", gia=45000, hinh="https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=300&q=80", loai="Đồ ăn"),
            MonAn(ten="Bún Bò Huế", gia=50000, hinh="https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=300&q=80", loai="Đồ ăn"),
            MonAn(ten="Trà Sữa Thái Xanh", gia=25000, hinh="https://images.unsplash.com/photo-1558857563-b371033873b8?auto=format&fit=crop&w=300&q=80", loai="Đồ uống"),
            MonAn(ten="Mì Ý Sốt Bò Băm", gia=55000, hinh="https://images.unsplash.com/photo-1551183053-bf91a1d81141?auto=format&fit=crop&w=300&q=80", loai="Đồ ăn")
        ]
        db.session.add_all(danh_sach_mau)
        db.session.commit()
    
    if NguoiDung.query.filter_by(tai_khoan='admin').first() is None:
        db.session.add(NguoiDung(tai_khoan='admin', mat_khau='123456', vai_tro='Admin'))
        db.session.commit()

# --- ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        tai_khoan = request.form.get('tai_khoan')
        mat_khau = request.form.get('mat_khau')
        user = NguoiDung.query.filter_by(tai_khoan=tai_khoan, mat_khau=mat_khau).first()
        if user:
            session['user_id'] = user.id
            session['user_name'] = user.tai_khoan
            session['user_role'] = user.vai_tro
            return redirect(url_for('admin_page') if user.vai_tro == 'Admin' else url_for('quan_ly_don_hang'))
        else:
            flash('Tài khoản hoặc mật khẩu không chính xác!')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        tai_khoan = request.form.get('tai_khoan')
        mat_khau = request.form.get('mat_khau')
        vai_tro = request.form.get('vai_tro')
        if NguoiDung.query.filter_by(tai_khoan=tai_khoan).first():
            flash('Tên tài khoản này đã tồn tại!')
        else:
            db.session.add(NguoiDung(tai_khoan=tai_khoan, mat_khau=mat_khau, vai_tro=vai_tro))
            db.session.commit()
            flash(f'Đăng ký tài khoản {vai_tro} thành công!')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('trang_chu'))

@app.route('/')
def trang_chu():
    tu_khoa = request.args.get('tu_khoa', '')
    danh_muc = request.args.get('danh_muc', '')
    query = MonAn.query
    if tu_khoa: query = query.filter(MonAn.ten.contains(tu_khoa))
    if danh_muc: query = query.filter(MonAn.loai == danh_muc)
    return render_template('index.html', mon_an=query.all(), tu_khoa=tu_khoa, danh_muc=danh_muc, user_name=session.get('user_name'), user_role=session.get('user_role'))

@app.route('/them-gio-hang/<int:id_mon>')
def them_gio_hang(id_mon):
    if 'cart' not in session: session['cart'] = {}
    gio_hang = session['cart']
    str_id = str(id_mon)
    gio_hang[str_id] = gio_hang.get(str_id, 0) + 1
    session.modified = True
    return redirect(url_for('xem_gio_hang'))

@app.route('/gio-hang')
def xem_gio_hang():
    gio_hang = session.get('cart', {})
    danh_sach_mua = []
    tong_tien = 0
    for str_id, so_luong in gio_hang.items():
        mon = MonAn.query.get(int(str_id))
        if mon:
            thanh_tien = mon.gia * so_luong
            tong_tien += thanh_tien
            danh_sach_mua.append({'id': mon.id, 'ten': mon.ten, 'gia': mon.gia, 'so_luong': so_luong, 'thanh_tien': thanh_tien})
    return render_template('cart.html', danh_sach_mua=danh_sach_mua, tong_tien=tong_tien)

@app.route('/cap-nhat-gio-hang/<int:id_mon>/<string:hanh_dong>')
def cap_nhat_gio_hang(id_mon, hanh_dong):
    if 'cart' in session:
        gio_hang = session['cart']
        str_id = str(id_mon)
        if str_id in gio_hang:
            if hanh_dong == 'tang': gio_hang[str_id] += 1
            elif hanh_dong == 'giam':
                gio_hang[str_id] -= 1
                if gio_hang[str_id] <= 0: del gio_hang[str_id]
            elif hanh_dong == 'xoa': del gio_hang[str_id]
            session.modified = True
    return redirect(url_for('xem_gio_hang'))

@app.route('/xoa-gio-hang')
def xoa_gio_hang():
    session.pop('cart', None)
    return redirect(url_for('xem_gio_hang'))

# Route Đặt hàng
@app.route('/dat-hang', methods=['POST'])
def dat_hang():
    ten_khach = request.form.get('ten_khach')
    sdt = request.form.get('sdt')
    diachi = request.form.get('diachi')
    
    gio_hang = session.get('cart', {})
    tong_tien = 0
    for str_id, so_luong in gio_hang.items():
        mon = MonAn.query.get(int(str_id))
        if mon: tong_tien += mon.gia * so_luong

    if tong_tien == 0: return redirect(url_for('trang_chu'))

    don_hang_moi = DonHang(ten_khach=ten_khach, sdt=sdt, diachi=diachi, tong_tien=tong_tien, trang_thai='Chờ xử lý')
    db.session.add(don_hang_moi)
    db.session.commit()

    bank_info = CauHinhNganHang.query.first()
    nh_bank = bank_info.bank_id if bank_info else "MB"
    nh_account = bank_info.account_no if bank_info else "0987654321"
    nh_name = bank_info.account_name if bank_info else "NGUYEN VAN A"
    noi_dung_ck = f"DH{don_hang_moi.id} {sdt}"

    if bank_info and bank_info.qr_custom_url and bank_info.qr_custom_url.strip():
        qr_url = bank_info.qr_custom_url.strip()
    else:
        qr_url = f"https://img.vietqr.io/image/{nh_bank}-{nh_account}-compact2.png?amount={tong_tien}&addInfo={noi_dung_ck}&accountName={nh_name}"

    session.pop('cart', None)

    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Thanh Toán Đơn Hàng #{don_hang_moi.id}</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .card {{ max-width: 480px; margin: 20px auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; }}
            .title {{ color: #28a745; margin-bottom: 5px; }}
            .qr-code {{ max-width: 280px; max-height: 350px; border: 1px solid #eee; padding: 10px; border-radius: 8px; margin: 15px 0; object-fit: contain; }}
            .info-box {{ background: #f8f9fa; text-align: left; padding: 15px; border-radius: 8px; font-size: 14px; line-height: 1.8; margin-bottom: 20px; }}
            .highlight {{ color: #dc3545; font-weight: bold; }}
            .btn-copy {{ padding: 2px 8px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; margin-left: 5px; }}
            .btn-home {{ display: inline-block; padding: 10px 25px; background: #ff5722; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2 class="title">🎉 ĐẶT HÀNG THÀNH CÔNG!</h2>
            <p style="margin-top:0; color:#666;">Mã đơn hàng: <b>#{don_hang_moi.id}</b></p>
            
            <p style="font-size: 14px; color: #333; margin-bottom: 5px;">Quét mã QR bằng App Ngân hàng hoặc Chuyển khoản theo thông tin:</p>
            <img src="{qr_url}" alt="Mã QR Thanh Toán" class="qr-code">
            
            <div class="info-box">
                <div><b>Ngân hàng:</b> {nh_bank}</div>
                <div><b>Số TK:</b> <span id="stk">{nh_account}</span> <button class="btn-copy" onclick="copyText('stk')">Copy</button></div>
                <div><b>Chủ TK:</b> {nh_name}</div>
                <div><b>Số tiền:</b> <span class="highlight">{tong_tien:,} VNĐ</span></div>
                <div><b>Nội dung CK:</b> <span class="highlight" id="ndck">{noi_dung_ck}</span> <button class="btn-copy" onclick="copyText('ndck')">Copy</button></div>
            </div>

            <a href="/" class="btn-home">Quay về Trang chủ</a>
        </div>

        <script>
            function copyText(elementId) {{
                var text = document.getElementById(elementId).innerText;
                navigator.clipboard.writeText(text);
                alert("Đã sao chép: " + text);
            }}
        </script>
    </body>
    </html>
    """

# --- ROUTES ADMIN ---

@app.route('/admin')
def admin_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    if session.get('user_role') != 'Admin':
        flash('Tài khoản Nhân viên không có quyền truy cập trang Quản lý Món ăn!')
        return redirect(url_for('quan_ly_don_hang'))
        
    danh_sach_mon = MonAn.query.all()
    bank_info = CauHinhNganHang.query.first()
    
    tong_don = DonHang.query.count()
    don_hoan_thanh = DonHang.query.filter_by(trang_thai='Hoàn thành').all()
    tong_doanh_thu = sum(dh.tong_tien for dh in don_hoan_thanh)
    
    cho_xu_ly = DonHang.query.filter_by(trang_thai='Chờ xử lý').count()
    dang_giao = DonHang.query.filter_by(trang_thai='Đang giao').count()
    hoan_thanh = len(don_hoan_thanh)
    da_huy = DonHang.query.filter_by(trang_thai='Đã hủy').count()

    return render_template('admin.html', mon_an=danh_sach_mon, bank_info=bank_info, user_name=session.get('user_name'), user_role=session.get('user_role'), tong_don=tong_don, tong_doanh_thu=tong_doanh_thu, cho_xu_ly=cho_xu_ly, dang_giao=dang_giao, hoan_thanh=hoan_thanh, da_huy=da_huy)

# Route cập nhật Ngân hàng & Tải lên file ảnh QR
@app.route('/admin/cap-nhat-ngan-hang', methods=['POST'])
def cap_nhat_ngan_hang():
    if 'user_id' not in session or session.get('user_role') != 'Admin': return redirect(url_for('login'))
        
    bank_info = CauHinhNganHang.query.first()
    if not bank_info:
        bank_info = CauHinhNganHang()
        db.session.add(bank_info)
        
    bank_info.bank_id = request.form.get('bank_id').upper().strip()
    bank_info.account_no = request.form.get('account_no').strip()
    bank_info.account_name = request.form.get('account_name').upper().strip()
    
    # Xử lý Tải File Ảnh Mã QR từ máy tính
    file_qr = request.files.get('qr_file')
    if file_qr and file_qr.filename != '':
        filename = secure_filename(file_qr.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file_qr.save(save_path)
        bank_info.qr_custom_url = f"/static/uploads/{filename}"
    elif request.form.get('clear_qr') == 'true':
        bank_info.qr_custom_url = "" # Reset về VietQR tự động
    
    db.session.commit()
    flash('Cập nhật thông tin Ngân hàng & Mã QR thành công!')
    return redirect(url_for('admin_page'))

@app.route('/admin/them-mon', methods=['POST'])
def them_mon_moi():
    if 'user_id' not in session or session.get('user_role') != 'Admin': return redirect(url_for('login'))
    db.session.add(MonAn(ten=request.form.get('ten'), gia=int(request.form.get('gia')), hinh=request.form.get('hinh'), loai=request.form.get('loai')))
    db.session.commit()
    return redirect(url_for('admin_page'))

@app.route('/admin/xoa-mon/<int:id_mon>')
def xoa_mon(id_mon):
    if 'user_id' not in session or session.get('user_role') != 'Admin': return redirect(url_for('login'))
    mon = MonAn.query.get_or_404(id_mon)
    db.session.delete(mon)
    db.session.commit()
    return redirect(url_for('admin_page'))

@app.route('/admin/sua-mon/<int:id_mon>')
def sua_mon_page(id_mon):
    if 'user_id' not in session or session.get('user_role') != 'Admin': return redirect(url_for('login'))
    return render_template('edit.html', mon=MonAn.query.get_or_404(id_mon))

@app.route('/admin/cap-nhat-mon/<int:id_mon>', methods=['POST'])
def cap_nhat_mon(id_mon):
    if 'user_id' not in session or session.get('user_role') != 'Admin': return redirect(url_for('login'))
    mon = MonAn.query.get_or_404(id_mon)
    mon.ten = request.form.get('ten')
    mon.gia = int(request.form.get('gia'))
    mon.hinh = request.form.get('hinh')
    mon.loai = request.form.get('loai')
    db.session.commit()
    return redirect(url_for('admin_page'))

@app.route('/admin/don-hang')
def quan_ly_don_hang():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('orders.html', don_hang=DonHang.query.order_by(DonHang.ngay_dat.desc()).all(), user_name=session.get('user_name'), user_role=session.get('user_role'))

@app.route('/admin/cap-nhat-don-hang/<int:id_don>', methods=['POST'])
def cap_nhat_don_hang(id_don):
    if 'user_id' not in session: return redirect(url_for('login'))
    don_hang = DonHang.query.get_or_404(id_don)
    don_hang.trang_thai = request.form.get('trang_thai')
    db.session.commit()
    return redirect(url_for('quan_ly_don_hang'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)