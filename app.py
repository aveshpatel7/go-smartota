from flask import Flask, render_template, request, send_from_directory, session, redirect, url_for
import paho.mqtt.client as mqtt
import os
import json

app = Flask(__name__)
# सिक्योरिटी के लिए एक सीक्रेट चाबी (यह बहुत ज़रूरी है)
app.secret_key = "gosmart_super_secret_key_2026" 

# 🔐 यहाँ अपना एडमिन यूजरनेम और पासवर्ड सेट करें
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "12345678"

UPLOAD_FOLDER = 'firmware'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MQTT_BROKER = "i26a1c71.ala.asia-southeast1.emqxsl.com"
MQTT_PORT = 8883
MQTT_USER = "smartnest_client"
MQTT_PASS = "D2m9ga8JynJDEM6"

mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.tls_set()

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
        return render_template('index.html', files=files)
    
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
    return "✅ Firmware Uploaded Successfully! <br><br> <a href='/'>Go Back to Dashboard</a>"

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
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.publish(topic, json.dumps(payload))
        mqtt_client.disconnect()
        return f"🚀 OTA Update Command Sent to {node_id}! ESP32 will now download: {filename} <br><br> <a href='/'>Go Back to Dashboard</a>"
    except Exception as e:
        return f"❌ Error connecting to MQTT: {e}"

@app.route('/firmware/<filename>')
def serve_firmware(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)