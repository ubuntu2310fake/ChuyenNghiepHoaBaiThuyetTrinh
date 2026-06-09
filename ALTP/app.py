from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import json
import os
import re
from docx import Document

app = Flask(__name__)
app.config['SECRET_KEY'] = 'altp_pro_winui'
socketio = SocketIO(app, cors_allowed_origins="*")

# Lấy đường dẫn tuyệt đối của thư mục chứa file app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_db_path(filename):
    # Luôn trỏ chính xác về thư mục dự án, bất kể chạy từ VS Code hay IDLE
    return os.path.join(BASE_DIR, filename)

# --- HÀM XỬ LÝ DB TỰ ĐỘNG CHỮA LỖI ---
def load_db(filename):
    filepath = get_db_path(filename)
    # Nếu file chưa tồn tại hoặc bị trống không (0 byte)
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return []

def save_db(filename, data):
    filepath = get_db_path(filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- ROUTES GIAO DIỆN ---
@app.route('/')
def controller():
    return render_template('controller.html')

@app.route('/obs')
def obs():
    return render_template('obs.html')

# --- API CÂU HỎI & XỬ LÝ FILE WORD ---
@app.route('/api/questions', methods=['GET', 'POST'])
def manage_questions():
    questions = load_db('questions.json')
    if request.method == 'POST':
        data = request.json
        new_id = 1 if not questions else max(q['id'] for q in questions) + 1
        data['id'] = new_id
        questions.append(data)
        save_db('questions.json', questions)
        return jsonify({'status': 'success'})
    return jsonify(questions)

@app.route('/api/questions/<int:q_id>', methods=['DELETE'])
def delete_question(q_id):
    questions = [q for q in load_db('questions.json') if q['id'] != q_id]
    save_db('questions.json', questions)
    return jsonify({'status': 'success'})

@app.route('/api/upload_docx', methods=['POST'])
def upload_docx():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'msg': 'Không có file'})
    
    file = request.files['file']
    doc = Document(file)
    questions = load_db('questions.json')
    current_q = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text: continue

        # Phát hiện bắt đầu câu mới
        if re.match(r'^Câu\s*\d+[:.]*', text, re.IGNORECASE):
            if current_q and len(current_q["options"]) >= 2:
                current_q["id"] = 1 if not questions else max(q['id'] for q in questions) + 1
                questions.append(current_q)
            
            lvl = len(questions) + 1
            current_q = {
                "question": text,
                "options": {"A":"", "B":"", "C":"", "D":""},
                "answer": "A", # Mặc định
                "level": lvl,
                "milestone": f"{lvl} ◈ MỐC {lvl}"
            }
            continue

        if current_q:
            # Quét gạch chân để tìm đáp án đúng
            for run in para.runs:
                if run.underline and run.text.strip():
                    for opt in ['A', 'B', 'C', 'D']:
                        if re.search(rf'\b{opt}\b', run.text) or opt in run.text:
                            current_q["answer"] = opt

            # Cắt các đáp án A. B. C. D. bằng Regex (bắt chuẩn kể cả nằm trên 1 dòng)
            options_matches = re.finditer(r'([A-D])\.(.*?)(?=(?:[A-D]\.)|$)', text)
            for match in options_matches:
                opt_key = match.group(1).upper()
                opt_val = match.group(2).strip()
                current_q["options"][opt_key] = opt_val

    # Lưu câu cuối cùng
    if current_q and len(current_q["options"]) >= 2:
        current_q["id"] = 1 if not questions else max(q['id'] for q in questions) + 1
        questions.append(current_q)

    save_db('questions.json', questions)
    return jsonify({'status': 'success', 'msg': 'Đã nạp câu hỏi từ file Word!'})

# --- API HỌC SINH (HỖ TRỢ THÊM HÀNG LOẠT) ---
@app.route('/api/students', methods=['GET'])
def get_students():
    return jsonify(load_db('students.json'))

@app.route('/api/students/bulk', methods=['POST'])
def add_students_bulk():
    names = request.json.get('names', [])
    students = load_db('students.json')
    start_id = 1 if not students else max(s['id'] for s in students) + 1
    
    for name in names:
        if name.strip():
            students.append({'id': start_id, 'name': name.strip()})
            start_id += 1
            
    save_db('students.json', students)
    return jsonify({'status': 'success'})

@app.route('/api/students/<int:s_id>', methods=['DELETE'])
def delete_student(s_id):
    students = [s for s in load_db('students.json') if s['id'] != s_id]
    save_db('students.json', students)
    return jsonify({'status': 'success'})

@socketio.on('obs_command')
def handle_obs_command(data):
    emit('sync_obs', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5002)