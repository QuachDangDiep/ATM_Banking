from flask import Flask, request, jsonify, render_template
from config import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash  # Thêm dòng này
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

# API đăng ký người dùng
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"message": "Name, email, and password are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Kiểm tra xem email đã tồn tại hay chưa
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        return jsonify({"message": "Email already registered"}), 400

    # Lưu mật khẩu trực tiếp (không mã hóa)
    cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", 
                   (name, email, password))

    conn.commit()  # Xác nhận lưu
    cursor.close()
    conn.close()
    
    return jsonify({"message": "Registration successful"}), 201


# API đăng nhập người dùng
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Kiểm tra email có tồn tại trong CSDL không
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        # Kiểm tra mật khẩu
        if user['password'] == password:
            cursor.close()
            conn.close()
            return jsonify({"message": "Login successful", "user": {"id": user["id"], "name": user["name"], "email": user["email"]}})
        else:
            cursor.close()
            conn.close()
            return jsonify({"message": "Invalid password"}), 400
    else:
        cursor.close()
        conn.close()
        return jsonify({"message": "User not found"}), 404

# API Thay đổi mật khẩu
@app.route('/change_password', methods=['POST'])
def change_password():
    data = request.json
    email = data.get('email')
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not email or not current_password or not new_password:
        return jsonify({"message": "Email, current password, and new password are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Kiểm tra người dùng có tồn tại hay không
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        # Kiểm tra mật khẩu hiện tại có đúng không
        if user['password'] == current_password:
            # Cập nhật mật khẩu mới
            cursor.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"message": "Password changed successfully"})
        else:
            cursor.close()
            conn.close()
            return jsonify({"message": "Current password is incorrect"}), 400
    else:
        cursor.close()
        conn.close()
        return jsonify({"message": "User not found"}), 404


@app.route('/balance/<int:account_id>', methods=['GET'])
def get_balance(account_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT balance FROM accounts WHERE account_id = %s",(account_id,))
    account = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if account:
        return jsonify(account)
    return jsonify({"error": "account not found",}),404

# API deposit(nap tien)
@app.route('/deposit', methods=['POST'])
def deposit():
    data = request.json
    account_id = data['account_id']
    amount = data['amount']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    
    cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_id = %s",(amount,account_id))
    cursor.execute("INSERT INTO transactions (account_id, transaction_type, amount) VAlUES(%s, %s, %s)"
                   ,(account_id,'deposit',amount))
    
    # Lấy thông tin email người dùng
    cursor.execute("SELECT email FROM users WHERE account_id = %s", (account_id,))
    user = cursor.fetchone()
    
    conn.commit() # commit Xác nhận hoàn thành 1 transaction
    cursor.close()
    conn.close()
    
    # Gửi email thông báo
    if user:
        subject = "Deposit Successful"
        message = f"Dear {user['email']},\n\nYou have successfully deposited {amount} into your account."
        send_email_notification(user['email'], subject, message)
    
    return jsonify({"message": "Deposit successful"})
    
# API withdraw(rut tien)
@app.route('/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    account_id = data['account_id']
    amount = data['amount']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT balance FROM accounts WHERE account_id = %s", (account_id,))
    account = cursor.fetchone()
    
    if account and account['balance'] >= amount:
        new_balance = account['balance'] - amount
        cursor.execute("UPDATE accounts SET balance = %s WHERE account_id = %s", (new_balance,account_id))
        cursor.execute("INSERT INTO transactions(account_id,transaction_type,amount) VALUE(%s, %s, %s)"
                   ,(account_id, 'withdraw',amount))
        conn.commit()
        
        # Lấy thông tin email người dùng
        cursor.execute("SELECT email FROM users WHERE account_id = %s", (account_id,))
        user = cursor.fetchone()
    
        cursor.close()
        conn.close()
        
         # Gửi email thông báo
        if user:
            subject = "Withdraw Successful"
            message = f"Dear {user['email']},\n\nYou have successfully withdrawn {amount} from your account."
            send_email_notification(user['email'], subject, message)
            
        return jsonify({"message": "Withdraw successful","new_balance":new_balance})

    cursor.close()
    conn.close()
    return jsonify({"message": "Insufficient funds"}),400

# API Lấy ra lịch sử giao dịch
@app.route('/transactions/<int:account_id>', methods=['GET'])
def get_transactions(account_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM transactions WHERE account_id = %s ORDER BY date DESC",(account_id,))
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if transactions:
        return jsonify({"transactions": transactions})
    return jsonify({"errer": "No transaction found"}),404

# API Chuyển tiền giữa các tài khoản
@app.route('/transfer', methods=['POST'])
def transfer():
    data = request.json
    from_account_id = data['account_id']
    to_account_id = data['account_id']
    amount = data['amount']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Kiểm tra số dư của tài khoản nguồn
    cursor.execute("SELECT balance FROM accounts WHERE account_id = %s", (from_account_id,))
    account = cursor.fetchone()
    
    if account and account['balance'] >= amount:
       new_balance = account['balance'] - amount
       
       #Cập nhật tài khoản nguồn
       cursor.execute("UPDATE accounts SET balance = %s WHERE account_id = %s", (new_balance, from_account_id,))
       
       #Cập nhật tài khoản đích
       cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_id = %s", (amount,to_account_id))
       
       # Ghi lại giao dịch
       cursor.execute("INSERT INTO transactions (account_id, transaction_type, amount) VALUES (%s, %s, %s)", (from_account_id, 'transfer_out', amount))
       cursor.execute("INSERT INTO transactions (account_id, transaction_type, amount) VALUES (%s, %s, %s)", (to_account_id, 'transfer_in', amount))
       
       # Lấy thông tin email người dùng
       cursor.execute("SELECT email FROM users WHERE account_id = %s", (from_account_id,))
       from_user = cursor.fetchone()
        
       cursor.execute("SELECT email FROM users WHERE account_id = %s", (to_account_id,))
       to_user = cursor.fetchone()
       
       conn.commit()
       cursor.close()
       conn.close()
       
       # Gửi email thông báo
       if from_user and to_user:
            subject = "Transfer Successful"
            message = f"Dear {from_user['email']},\n\nYou have successfully transferred {amount} to {to_user['email']}."
            send_email_notification(from_user['email'], subject, message)
            
            subject_to = "Received Transfer"
            message_to = f"Dear {to_user['email']},\n\nYou have received {amount} from {from_user['email']}."
            send_email_notification(to_user['email'], subject_to, message_to)
       
       return jsonify({"message": "Transfer successful", "new_from_balance":new_balance})
    
    cursor.close()
    conn.close()
    return jsonify({"message": "Insufficient funds funds or account not found"}),400   

# Hàm gửi email thông báo
def send_email_notification(to_email, subject, message):
    sender_email = "your-email@gmail.com"
    sender_password = "your-password"
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == '__main__':
    app.run(debug=True)