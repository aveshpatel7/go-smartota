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

# 🚀 ऑनलाइन नोड्स को याद रखने के लिए (यह लिस्ट अपने आप अपडेट होगी)
active_nodes = set()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        # सर्वर चालू होते ही सभी कस्टमर्स के status टॉपिक को सुनना शुरू कर देगा
        client.subscribe("home/device/+/status")
        print("✅ MQTT Connected & Listening for Device Status...")

def on_message(client, userdata, msg):
    try:
        # टॉपिक से Node ID निकालना (जैसे: home/device/4L-NODE-2FD6E4/status)
        topic_parts = msg.topic.split('/')
        if len(topic_parts) >= 4 and topic_parts[3] == 'status':
            node_id = topic_parts[2]
            payload_str = msg.payload.decode('utf-8')
            
            # ESP32 के JSON डेटा को पढ़ना
            data = json.loads(payload_str)
            
            # अगर डिवाइस ऑनलाइन है, तो लिस्ट में डाल दो
            if data.get("is_online") is True:
                active_nodes.add(node_id)
                print(f"🟢 Device Online: {node_id}")
            
            # अगर डिवाइस ऑफलाइन हो गया, तो लिस्ट से हटा दो
            elif data.get("is_online") is False:
                if node_id in active_nodes:
                    active_nodes.remove(node_id)
                print(f"🔴 Device Offline: {node_id}")
                
    except Exception as e:
        pass # अगर कोई कचरा मैसेज आए तो उसे इग्नोर कर दो

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
        # 🚀 ऑनलाइन नोड्स की लिस्ट HTML (डैशबोर्ड) को भेज रहे हैं
        return render_template('index.html', files=files, online_nodes=active_nodes)
    
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

# 🚀 नया फंक्शन: HTML के जासूस को ऑनलाइन नोड्स की लिस्ट देने के लिए
@app.route('/get_nodes')
def get_nodes():
    if not session.get('logged_in'):
        return jsonify([])
    return jsonify(list(active_nodes))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)