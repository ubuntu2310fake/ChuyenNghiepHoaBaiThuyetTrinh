import json
import os
import random
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

DB_FILE = 'database.json'
STATIC_DIR = 'static'

DEFAULT_DATA = {
    "active_id": "wheel_1",
    "wheels": {
        "wheel_1": {
            "name": "Vòng quay mặc định",
            "spin_sound": "",
            "items": [
                {"name": "Chúc may mắn lần sau", "weight": 50, "color": "#e81123", "sound": ""},
                {"name": "Voucher 50K", "weight": 30, "color": "#0078d4", "sound": ""},
                {"name": "Iphone 15 Pro Max", "weight": 5, "color": "#107c41", "sound": ""}
            ]
        }
    }
}

def load_db():
    if not os.path.exists(DB_FILE):
        save_db(DEFAULT_DATA)
        return DEFAULT_DATA
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'wheels' not in data: return DEFAULT_DATA
            return data
    except:
        return DEFAULT_DATA

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)
    sounds = [f for f in os.listdir(STATIC_DIR) if f.endswith('.mp3')]
    return render_template('index.html', sounds=sounds)

@app.route('/obs')
def obs():
    return render_template('obs.html')

@app.route('/api/config')
def get_config():
    return jsonify(load_db())

@socketio.on('update_config')
def handle_update(data):
    save_db(data)
    emit('config_updated', data, broadcast=True)

# ĐÃ SỬA: Nhận thêm thời lượng nhạc từ Frontend
@socketio.on('trigger_spin')
def handle_spin(client_data):
    duration = client_data.get('duration', 10000) if client_data else 10000
    
    db = load_db()
    active_wheel = db['wheels'][db['active_id']]
    items = active_wheel.get('items', [])
    
    if not items: return
    weights = [float(item.get('weight', 1)) for item in items]
    chosen_item = random.choices(items, weights=weights, k=1)[0]
    index = items.index(chosen_item)
    
    emit('start_spinning', {
        'index': index, 
        'name': chosen_item['name'],
        'color': chosen_item['color'],
        'sound': chosen_item['sound'],
        'duration': duration  # Truyền thời lượng qua cho OBS
    }, broadcast=True)

@socketio.on('close_all_popups')
def handle_close():
    emit('hide_popup', broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True, port=5001)
