from flask import Flask, render_template, request, send_from_directory, Response
import paho.mqtt.client as mqtt
import os
import json
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)

# --- फाइल सेविंग सेटिंग ---
UPLOAD_FOLDER = 'firmware'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # रेंडर पर एरर रोकने के लिए

# --- पासवर्ड सिक्योरिटी ---
def check_auth(username, password):
    return username == 'admin' and password == '12345678'

def authenticate():
    return Response(
        'Login Required\n', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- MQTT सेटिंग ---
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
client = mqtt.Client()

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    print("MQTT Connected!")
except Exception as e:
    print(f"MQTT Error: {e}")

# --- वेब पेज राऊट ---
@app.route('/')
@requires_auth
def index():
    return render_template('index.html')

# --- OTA भेजने का राऊट ---
@app.route('/send_ota', methods=['POST'])
@requires_auth
def send_ota():
    try:
        node_id = request.form.get('node_id')
        file = request.files.get('file')

        if not file or file.filename == '':
            return "Error: No file selected!", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # डाउनलोड URL बनाना
        download_url = f"https://go-smartota.onrender.com/firmware/{filename}"

        # MQTT मैसेज भेजना
        payload = json.dumps({"url": download_url})
        topic = f"{node_id}/ota"
        client.publish(topic, payload)

        return f"Success! Update sent to {node_id}. URL: {download_url}"

    except Exception as e:
        return f"Error: {str(e)}"

# --- फाइल डाउनलोड राऊट ---
@app.route('/firmware/<filename>')
def serve_firmware(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)