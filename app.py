from flask import Flask, render_template, request, send_from_directory, session, redirect, url_for
import paho.mqtt.client as mqtt
import os
import json

app = Flask(__name__)
# सिक्योरिटी के लिए एक सीक्रेट चाबी (यह बहुत ज़रूरी है)
app.secret_key = "gosmart_super_secret_key_2026" 

# 🔐 यहाँ अपना एडमिन यूजरनेम और पासवर्ड सेट करें
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "12345678"

UPLOAD_FOLDER = 'firmwarev2'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MQTT_BROKER = "i26a1c71.ala.asia-southeast1.emqxsl.com"
MQTT_PORT = 8883
MQTT_USER = "smartnest_client"
MQTT_PASS = "D2m9ga8JynJDEM6"

# 🚀 ऑनलाइन नोड्स को याद रखने के लिए लिस्ट
active_nodes = set()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        # जैसे ही सर्वर चालू होगा, वह सब नोड्स का स्टेटस सुनना शुरू कर देगा
        client.subscribe("home/device/+/status")

def on_message(client, userdata, msg):
    try:
        # अगर किसी नोड ने "online" भेजा, तो उसका नाम लिस्ट में जुड़ जाएगा
        topic_parts = msg.topic.split('/')
        if len(topic_parts) >= 4 and topic_parts[3] == 'status':
            node_id = topic_parts[2]
            payload = msg.payload.decode('utf-8').strip().lower()
            if payload == "online":
                active_nodes.add(node_id)
    except Exception as e:
        pass

mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.tls_set()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# 🚀 MQTT को बैकग्राउंड में हमेशा चालू रखने के लिए (ताकि ऑनलाइन नोड्स ट्रैक हो सकें)
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start() 
except Exception as e:
    print("MQTT Connection Error:", e)

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    # अगर कोई लॉगिन करने की कोशिश कर रहा है
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        
        if user == ADMIN_USERNAME and pw == ADMIN_PASSWORD:
            session['logged_in'] = True  # ताला खुल गया
            return redirect(url_for('index'))
        else:
            error = "❌ Wrong Username or Password!"

    # अगर लॉगिन है, तो फाइलें दिखाओ
    if session.get('logged_in'):
        files = os.listdir(UPLOAD_FOLDER)
        # 🚀 ऑनलाइन नोड्स की लिस्ट HTML को भेज रहे हैं
        return render_template('index.html', files=files, online_nodes=active_nodes)
    
    # अगर लॉगिन नहीं है, तो सिर्फ लॉगिन पेज दिखाओ
    return render_template('index.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None) # ताला वापस लगा दिया
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
        # 🚀 अब बार-बार कनेक्ट/डिस्कनेक्ट करने की ज़रूरत नहीं, बैकग्राउंड कनेक्शन यूज़ होगा
        mqtt_client.publish(topic, json.dumps(payload))
        return f"🚀 OTA Update Command Sent to {node_id}! ESP32 will now download: {filename} <br><br> <a href='/'>Go Back to Dashboard</a>"
    except Exception as e:
        return f"❌ Error connecting to MQTT: {e}"

@app.route('/firmware/<filename>')
def serve_firmware(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)