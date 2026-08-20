from flask import Flask, render_template, request, send_from_directory, Response
import paho.mqtt.client as mqtt
import os
import json
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)

# --- 📁 फाइल सेव करने की सेटिंग ---
UPLOAD_FOLDER = 'firmware'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# यह लाइन अपने आप 'firmware' नाम का फोल्डर बना देगी (अगर नहीं होगा तो)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- 🔒 पासवर्ड सिक्योरिटी (Login System) ---
def check_auth(username, password):
    return username == 'admin' and password == '12345678'

def authenticate():
    return Response(
        'नजदीक मत आना! यह एक सुरक्षित सर्वर है।\n', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- 📡 MQTT सेटिंग (ESP32 से बात करने के लिए) ---
MQTT_BROKER = "broker.emqx.io"  # अगर आपका ब्रोकर अलग है, तो इसे बदल लें
MQTT_PORT = 1883
client = mqtt.Client()

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    print("✅ MQTT Broker Connected Successfully!")
except Exception as e:
    print(f"❌ MQTT Connection Error: {e}")

# --- 🌐 वेब पेज (Dashboard) का राऊट ---
@app.route('/')
@requires_auth
def index():
    return render_template('index.html')

# --- 🚀 OTA अपडेट भेजने का राऊट ---
@app.route('/send_ota', methods=['POST'])
@requires_auth
def send_ota():
    try:
        node_id = request.form.get('node_id')
        
        # HTML से फाइल का नाम चाहे 'file' हो या 'firmware', यह दोनों को पकड़ लेगा
        file = request.files.get('file') or request.files.get('firmware')

        if not file or file.filename == '':
            return "❌ Error: कोई फाइल नहीं मिली! कृपया सही .bin फाइल चुनें।", 400

        # फाइल का नाम सुरक्षित करना और उसे सेव करना
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 🔗 ESP32 के लिए डाउनलोड URL बनाना (Render वाला लिंक)
        download_url = f"https://go-smartota.onrender.com/firmware/{filename}"

        # 📨 MQTT मैसेज तैयार करना और भेजना
        payload = json.dumps({"url": download_url})
        topic = f"{node_id}/ota"  # अपना टॉपिक चेक कर लें, यह डिफ़ॉल्ट है
        client.publish(topic, payload)

        print(f"[OTA] Update sent to {node_id}. URL: {download_url}")
        return f"✅ अपडेट सफलतापूर्वक {node_id} को भेज दिया गया! URL: {download_url}"

    except Exception as e:
        return f"❌ Error: {str(e)}"

# --- 📥 ESP32 को फाइल देने (Download) का राऊट ---
@app.route('/firmware/<filename>')
def serve_firmware(filename):
    # यह राऊट ESP32 को .bin फाइल डाउनलोड करवाएगा
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- ⚙️ सर्वर स्टार्ट करना ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)