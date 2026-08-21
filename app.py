from flask import Flask, render_template, request, send_from_directory, session, redirect, url_for, jsonify
import paho.mqtt.client as mqtt
import os
import json

app = Flask(__name__)
# सिक्योरिटी के लिए सीक्रेट चाबी
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

# 🚀 'डायरी' (File) का नाम जहाँ सारे ऑनलाइन नोड्स लिखे जाएंगे
NODES_FILE = 'active_nodes.json'

# यह फंक्शन डायरी में नोड का नाम लिखेगा या मिटाएगा
def update_node_status(node_id, is_online):
    nodes = []
    if os.path.exists(NODES_FILE):
        try:
            with open(NODES_FILE, 'r') as f:
                nodes = json.load(f)
        except:
            pass
    
    nodes_set = set(nodes)
    if is_online:
        nodes_set.add(node_id)
    else:
        nodes_set.discard(node_id)
        
    with open(NODES_FILE, 'w') as f:
        json.dump(list(nodes_set), f)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe("home/device/+/status")
        print("✅ MQTT Connected & Listening for Device Status...")

def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split('/')
        if len(topic_parts) >= 4 and topic_parts[3] == 'status':
            node_id = topic_parts[2]
            payload_str = msg.payload.decode('utf-8')
            data = json.loads(payload_str)
            
            # 🚀 रामबाण तरीका: कोई धड़कन आए या स्विच दबे, तुरंत डायरी में लिखो!
            if data.get("is_online") is True or "channel" in data:
                update_node_status(node_id, True)
                print(f"🟢 Device Online: {node_id}")
            
            elif data.get("is_online") is False:
                update_node_status(node_id, False)
                print(f"🔴 Device Offline: {node_id}")
                
    except Exception as e:
        pass

mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.tls_set()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start() 
except Exception as e:
    print("MQTT Connection Error:", e)

# डायरी पढ़ने का फंक्शन
def get_saved_nodes():
    if os.path.exists(NODES_FILE):
        try:
            with open(NODES_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []

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
        online_nodes = get_saved_nodes() # डायरी से नाम लेगा
        return render_template('index.html', files=files, online_nodes=online_nodes)
    
    return render_template('index.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if not session.get('logged_in'):
        return "❌ Unauthorized Access!"
        
    if 'file' not in request.files:
        return "No file selected!"
    file = request.files['file']
    if file.filename != '':
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    return "✅ Firmware Uploaded Successfully!"

@app.route('/send_ota', methods=['POST'])
def send_ota():
    if not session.get('logged_in'):
        return "❌ Unauthorized Access!"

    node_id = request.form.get('node_id')
    filename = request.form.get('filename')
    
    host_url = request.host_url.replace("http://", "https://")
    firmware_download_url = f"{host_url}firmware/{filename}"
    
    topic = f"home/device/{node_id}/control"
    payload = {
        "action": "OTA_UPDATE",
        "firmware_url": firmware_download_url
    }
    
    try:
        mqtt_client.publish(topic, json.dumps(payload))
        return f"🚀 OTA Update Command Sent to {node_id}! ESP32 will now download: {filename}"
    except Exception as e:
        return f"❌ Error connecting to MQTT: {e}"

@app.route('/firmware/<filename>')
def serve_firmware(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/get_nodes')
def get_nodes_api():
    if not session.get('logged_in'):
        return jsonify([])
    return jsonify(get_saved_nodes()) # जासूस को भी डायरी से नाम देगा

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)