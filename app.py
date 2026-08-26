from flask import Flask, render_template, request, send_from_directory, session, redirect, url_for, jsonify
import paho.mqtt.client as mqtt
import os
import json
import time

app = Flask(__name__)
# सिक्योरिटी के लिए एक सीक्रेट चाबी 
app.secret_key = "gosmart_super_secret_key_2026" 

# 🔐 एडमिन यूजरनेम और पासवर्ड
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "12345678"

UPLOAD_FOLDER = 'firmwarev2'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MQTT_BROKER = "i26a1c71.ala.asia-southeast1.emqxsl.com"
MQTT_PORT = 8883
MQTT_USER = "smartnest_client"
MQTT_PASS = "D2m9ga8JynJDEM6"

NODES_FILE = 'active_nodes.json'
TELEMETRY_FILE = 'telemetry_data.json'

# लाइव कंसोल के लिए मेमोरी (ताकि डैशबोर्ड को लॉग्स दिखें)
live_logs = []

def add_log(msg):
    global live_logs
    timestamp = time.strftime("%I:%M:%S %p")
    live_logs.append(f"[{timestamp}] {msg}")
    if len(live_logs) > 30: # 30 से ज़्यादा मैसेज मत रखो
        live_logs.pop(0)

# फाइलों को पढ़ने/लिखने के लिए हेल्पर
def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except: pass
    return default

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f)

def update_node_status(node_id, is_online):
    nodes = set(load_json(NODES_FILE, []))
    if is_online:
        nodes.add(node_id)
    else:
        nodes.discard(node_id)
    save_json(NODES_FILE, list(nodes))

def update_telemetry(node_id, data):
    telemetry = load_json(TELEMETRY_FILE, {})
    if node_id not in telemetry:
        telemetry[node_id] = {"channels": {}}
    
    ch = str(data.get("channel", "0"))
    telemetry[node_id]["channels"][ch] = {
        "toggles": data.get("toggles", 0),
        "on_hours": data.get("on_hours", "0.00")
    }
    telemetry[node_id]["boot_count"] = data.get("boot_count", 0)
    telemetry[node_id]["crash_count"] = data.get("crash_count", 0)
    telemetry[node_id]["rssi"] = data.get("rssi", 0)
    telemetry[node_id]["fw_version"] = data.get("fw_version", "Unknown")
    
    save_json(TELEMETRY_FILE, telemetry)

# 📡 बैकग्राउंड MQTT कनेक्शन (डैशबोर्ड को ज़िंदा रखने के लिए)
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe("home/device/+/status")
        client.subscribe("home/device/+/telemetry")
        client.subscribe("smartnest/devices/+/ota/status")
        client.subscribe("smartnest/devices/+/logs")
        print("✅ MQTT Connected & Listening for Telemetry...")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        
        parts = topic.split('/')
        if len(parts) < 3: return
        node_id = parts[2]

        if '/status' in topic and 'ota' not in topic:
            if data.get("is_online") is True or "channel" in data:
                update_node_status(node_id, True)
            elif data.get("is_online") is False:
                update_node_status(node_id, False)

        elif '/telemetry' in topic:
            update_node_status(node_id, True)
            update_telemetry(node_id, data)

        elif '/ota/status' in topic:
            status = str(data.get("status", "")).upper()
            progress = data.get("progress", 0)
            add_log(f"📡 [OTA {node_id}] {status} - {progress}%")

        elif '/logs' in topic:
            add_log(f"💻 [{node_id}] {payload_str}")

    except Exception as e:
        pass

# MQTT क्लाइंट को चालू करना 
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.tls_set()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()  # यह बैकग्राउंड में चलता रहेगा
except Exception as e:
    print("MQTT Connection Error:", e)


@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == ADMIN_USERNAME and pw == ADMIN_PASSWORD:
            session['logged_in'] = True 
            return redirect(url_for('index'))
        else:
            error = "❌ Wrong Username or Password!"

    if session.get('logged_in'):
        files = os.listdir(UPLOAD_FOLDER)
        online_nodes = load_json(NODES_FILE, [])
        return render_template('index.html', files=files, online_nodes=online_nodes)
    return render_template('index.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"})
        
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file selected!"})
    
    file = request.files['file']
    if file.filename != '':
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))
        return jsonify({"status": "success", "message": f"{file.filename} Uploaded!"})
    return jsonify({"status": "error", "message": "Upload failed."})


# 🚀 आपका पुराना और 100% भरोसेमंद OTA लॉजिक (नए डैशबोर्ड के AJAX के साथ)
@app.route('/send_ota', methods=['POST'])
def send_ota():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    node_id = request.form.get('node_id').strip()
    filename = request.form.get('filename')
    
    host_url = request.host_url.replace("http://", "https://")
    firmware_download_url = f"{host_url}firmware/{filename}"
    
    # 🎯 आपका पुराना वाला पक्का टॉपिक
    topic = f"home/device/{node_id}/control"
    
    # 🎯 आपका पुराना वाला पक्का पेलोड (बिना किसी एक्स्ट्रा चीज़ के)
    payload = {
        "action": "OTA_UPDATE",
        "firmware_url": firmware_download_url
    }
    
    try:
        # बैकग्राउंड MQTT का उपयोग करके मैसेज भेजना (ताकि डैशबोर्ड क्रैश न हो)
        mqtt_client.publish(topic, json.dumps(payload))
        
        # डैशबोर्ड की काली स्क्रीन पर मैसेज छापना
        add_log(f"🚀 Sent Firmware {filename} to {node_id}")
        
        # AJAX के लिए JSON रिस्पॉन्स (ताकि पेज रिफ्रेश न हो)
        return jsonify({"status": "success", "message": f"OTA Command Sent to {node_id}!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/firmware/<filename>')
def serve_firmware(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# 🚀 सिंगल API से सारा लाइव डेटा डैशबोर्ड पर भेजने के लिए
@app.route('/api/live_data')
def get_live_data():
    if not session.get('logged_in'):
        return jsonify({})
    return jsonify({
        "nodes": load_json(NODES_FILE, []),
        "telemetry": load_json(TELEMETRY_FILE, {}),
        "logs": live_logs
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)