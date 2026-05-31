from flask import Flask, render_template_string, jsonify, request
from obswebsocket import obsws, requests

app = Flask(__name__)

# --- CẤU HÌNH KẾT NỐI OBS ---
OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "299210"  # <--- Đổi lại mật khẩu OBS của bạn nếu cần

def get_obs_client():
    ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
    ws.connect()
    return ws

# --- GIAO DIỆN WEB 2 MÀN HÌNH TỐI ƯU TỐC ĐỘ CAO ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OBS Dual Monitor Matrix</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background-color: #0f1115;
            color: #e2e8f0;
            margin: 0;
            padding: 8px;
        }
        h2 { text-align: center; margin: 8px 0; color: #38bdf8; font-size: 18px; }
        
        /* Bố cục 2 màn hình giám sát song song */
        .monitor-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            max-width: 900px;
            margin: 0 auto 12px auto;
        }
        .monitor-box {
            background-color: #161a22;
            border-radius: 6px;
            padding: 4px;
            text-align: center;
            border: 2px solid #2d3139;
        }
        .monitor-box.preview { border-color: #3b82f6; }
        .monitor-box.program { border-color: #ef4444; }
        .monitor-title { font-size: 10px; font-weight: bold; margin-bottom: 4px; text-transform: uppercase; }
        .monitor-img { 
            width: 100%; 
            aspect-ratio: 16/9; 
            background-color: #000; 
            border-radius: 4px; 
            object-fit: contain; 
        }

        /* Thanh điều khiển phụ */
        .control-bar {
            max-width: 900px;
            margin: 0 auto 12px auto;
            display: flex;
            gap: 10px;
            align-items: center;
            justify-content: space-between;
            background: #1a1f26;
            padding: 8px 12px;
            border-radius: 6px;
        }
        select {
            background: #2d3748;
            color: white;
            border: 1px solid #4a5568;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 13px;
            width: 50%;
        }

        /* Ma trận danh sách nút gạt Source */
        .matrix-container {
            max-width: 900px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .scene-block {
            background-color: #161a22;
            border: 1px solid #2d3139;
            border-radius: 6px;
            overflow: hidden;
        }
        .scene-header {
            background-color: #212631;
            padding: 8px 12px;
            font-weight: bold;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .scene-header.active-program { border-left: 4px solid #ef4444; }
        .scene-header.active-preview { border-left: 4px solid #3b82f6; }
        
        .source-grid {
            padding: 8px;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(135px, 1fr));
            gap: 8px;
        }
        .source-card {
            background: #1f242e;
            padding: 8px;
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid #2d3139;
        }
        .source-name {
            font-size: 11px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            width: 80px;
        }

        /* Công tắc gạt Mini Switch */
        .switch { position: relative; display: inline-block; width: 32px; height: 18px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider {
            position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
            background-color: #4a5568; transition: .15s; border-radius: 18px;
        }
        .slider:before {
            position: absolute; content: ""; height: 12px; width: 12px; left: 3px; bottom: 3px;
            background-color: white; transition: .15s; border-radius: 50%;
        }
        input:checked + .slider { background-color: #10b981; }
        input:checked + .slider:before { transform: translateX(14px); }
    </style>
</head>
<body>

    <h2>OBS MONITOR MATRIX</h2>
    
    <div class="monitor-container">
        <div class="monitor-box preview">
            <div class="monitor-title" style="color: #3b82f6;">PREVIEW (XEM TRƯỚC)</div>
            <img id="img-preview" class="monitor-img" src="" alt="Đang tải Preview...">
        </div>
        <div class="monitor-box program">
            <div class="monitor-title" style="color: #ef4444;">PROGRAM (TONG)</div>
            <img id="img-program" class="monitor-img" src="" alt="Đang tải Program...">
        </div>
    </div>

    <div class="control-bar">
        <label style="font-size: 12px; font-weight: bold;">Chuyển đổi Scene Xem Trước:</label>
        <select id="preview-select" onchange="changeMonitorScene(this.value)">
            </select>
    </div>

    <div class="matrix-container" id="matrix-box"></div>

    <script>
        let isDropdownLoaded = false;

        // Vòng lặp đồng bộ hình ảnh tốc độ cao sử dụng requestAnimationFrame (Thay thế cho luồng Stream OpenCV bị lỗi)
        async function updateScreenshots() {
            try {
                const response = await fetch('/api/screenshots');
                const data = await response.json();
                
                if (data.status === "success") {
                    if (data.preview_img) document.getElementById('img-preview').src = data.preview_img;
                    if (data.program_img) document.getElementById('img-program').src = data.program_img;
                }
            } catch (e) {
                console.error("Lỗi cập nhật ảnh:", e);
            }
            // Tiếp tục vòng lặp chụp ảnh màn hình kế tiếp ngay khi trình duyệt sẵn sàng render
            requestAnimationFrame(updateScreenshots);
        }

        // Đồng bộ hóa cấu trúc nút bấm, công tắc và trạng thái ẩn hiện (Chạy chậm hơn để tiết kiệm CPU)
        async function syncControlMatrix() {
            try {
                const response = await fetch('/api/control-status');
                const data = await response.json();
                
                // Đổ dữ liệu vào thanh Dropdown lựa chọn (chỉ chạy 1 lần đầu)
                const select = document.getElementById('preview-select');
                if(!isDropdownLoaded && data.all_scenes.length > 0) {
                    select.innerHTML = '';
                    data.all_scenes.forEach(sName => {
                        let opt = document.createElement('option');
                        opt.value = sName;
                        opt.innerHTML = sName;
                        if(sName === data.current_preview) opt.selected = true;
                        select.appendChild(opt);
                    });
                    isDropdownLoaded = true;
                }

                // Vẽ sơ đồ danh sách các nút nguồn gạt
                const matrixBox = document.getElementById('matrix-box');
                matrixBox.innerHTML = '';

                data.matrix.forEach(sc => {
                    let isProg = sc.scene_name === data.current_program;
                    let isPrev = sc.scene_name === data.current_preview;
                    
                    let headerClass = "scene-header";
                    if (isProg) headerClass += " active-program";
                    else if (isPrev) headerClass += " active-preview";

                    let statusTag = isProg ? "<span style='color:#ef4444; font-size:10px;'>● PROGRAM (LIVE)</span>" : (isPrev ? "<span style='color:#3b82f6; font-size:10px;'>● PREVIEW</span>" : "");

                    let sceneBlock = document.createElement('div');
                    sceneBlock.className = 'scene-block';
                    
                    let sourceCardsHTML = '';
                    sc.sources.forEach(src => {
                        sourceCardsHTML += `
                            <div class="source-card">
                                <div class="source-name" title="${src.name}">${src.name}</div>
                                <label class="switch">
                                    <input type="checkbox" ${src.visible ? 'checked' : ''} onchange="toggleAnySource('${sc.scene_name}', ${src.id}, ${!src.visible})">
                                    <span class="slider"></span>
                                </label>
                            </div>
                        `;
                    });

                    sceneBlock.innerHTML = `
                        <div class="${headerClass}">
                            <div>${sc.scene_name}</div>
                            ${statusTag}
                        </div>
                        <div class="source-grid">${sourceCardsHTML || '<div style="color:#718096; font-size:11px; padding:2px 5px;">Không chứa nguồn hình ảnh</div>'}</div>
                    `;
                    matrixBox.appendChild(sceneBlock);
                });

            } catch (e) {
                console.error("Lỗi đồng bộ bảng điều khiển:", e);
            }
        }

        async function changeMonitorScene(sceneName) {
            await fetch('/api/change-preview', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ scene_name: sceneName })
            });
            syncControlMatrix();
        }

        async function toggleAnySource(sceneName, itemId, setVisible) {
            await fetch('/api/toggle-any-source', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ scene_name: sceneName, item_id: itemId, visible: setVisible })
            });
            syncControlMatrix();
        }

        // Kích hoạt song song hai luồng xử lý độc lập
        requestAnimationFrame(updateScreenshots); // Khởi động luồng hiển thị 2 màn hình siêu tốc
        setInterval(syncControlMatrix, 2500);       // Đồng bộ lại nút bấm sau mỗi 2.5 giây để tránh thắt nút cổ chai
        syncControlMatrix();
    </script>
</body>
</html>
"""

# --- XỬ LÝ CÁC ĐƯỜNG DẪN TRUY XUẤT API (ROUTES) ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/screenshots', methods=['GET'])
def get_screenshots():
    """Tách biệt phần xử lý ảnh chụp màn hình riêng ra để tối ưu hóa FPS"""
    try:
        ws = get_obs_client()
        scene_list_resp = ws.call(requests.GetSceneList())
        current_program = scene_list_resp.getCurrentProgramSceneName()
        current_preview = scene_list_resp.getCurrentPreviewSceneName()
        
        # Thiết lập độ phân giải nén ảnh tối ưu (Nén chặt kích thước dữ liệu để truyền siêu tốc qua Wi-Fi LAN)
        img_w, img_h, img_q = 480, 270, 45 

        # Chụp luồng Preview
        try:
            p_resp = ws.call(requests.GetSourceScreenshot(
                sourceName=current_preview, imageFormat="jpeg", imageWidth=img_w, imageHeight=img_h, imageCompressionQuality=img_q
            ))
            preview_img = p_resp.getImageData()
        except:
            preview_img = ""

        # Chụp luồng Program (Cảnh TONG)
        try:
            pr_resp = ws.call(requests.GetSourceScreenshot(
                sourceName=current_program, imageFormat="jpeg", imageWidth=img_w, imageHeight=img_h, imageCompressionQuality=img_q
            ))
            program_img = pr_resp.getImageData()
        except:
            program_img = ""

        ws.disconnect()
        return jsonify({
            "status": "success",
            "preview_img": preview_img,
            "program_img": program_img
        })
    except:
        return jsonify({"status": "waiting"}), 200

@app.route('/api/control-status', methods=['GET'])
def get_control_status():
    """Tải cấu trúc mạng lưới ma trận nút bấm của OBS"""
    try:
        ws = get_obs_client()
        scene_list_resp = ws.call(requests.GetSceneList())
        current_program = scene_list_resp.getCurrentProgramSceneName()
        current_preview = scene_list_resp.getCurrentPreviewSceneName()
        
        all_scenes_names = [s['sceneName'] for s in scene_list_resp.getScenes()]
        matrix_data = []

        for s_name in all_scenes_names:
            items_resp = ws.call(requests.GetSceneItemList(sceneName=s_name))
            sources_in_scene = []
            
            for item in items_resp.getSceneItems():
                src_name = item['sourceName']
                src_id = item['sceneItemId']
                src_visible = item['sceneItemEnabled']
                
                # Bỏ qua các định dạng capture âm thanh thuần túy
                if "Audio" in src_name or "wasapi" in item.get('sourceType', ''):
                    continue
                    
                sources_in_scene.append({
                    "id": src_id,
                    "name": src_name,
                    "visible": src_visible
                })
            
            matrix_data.append({
                "scene_name": s_name,
                "sources": sources_in_scene
            })

        ws.disconnect()
        return jsonify({
            "all_scenes": all_scenes_names,
            "current_program": current_program,
            "current_preview": current_preview,
            "matrix": matrix_data
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/change-preview', methods=['POST'])
def change_preview():
    data = request.json
    scene_name = data.get('scene_name')
    try:
        ws = get_obs_client()
        ws.call(requests.SetCurrentPreviewScene(sceneName=scene_name))
        ws.disconnect()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/toggle-any-source', methods=['POST'])
def toggle_any_source():
    data = request.json
    scene_name = data.get('scene_name')
    item_id = data.get('item_id')
    visible = data.get('visible')
    try:
        ws = get_obs_client()
        ws.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=item_id, sceneItemEnabled=visible))
        ws.disconnect()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Chạy Flask đa luồng (threaded=True) để nhận đồng thời dữ liệu điều hướng và dữ liệu ảnh
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)