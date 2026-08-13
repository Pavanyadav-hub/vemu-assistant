import os
from flask import Flask, render_template_string, request, jsonify
import wikipedia
from google import genai

app = Flask(__name__)

# Initializes automatically using GEMINI_API_KEY from Render Environment Variables
client = genai.Client()

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VEMU Cloud Assistant</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #121212; color: #E0E0E0; margin: 0; padding: 20px; text-align: center; }
        .card { background: #1E1E1E; padding: 25px; border-radius: 16px; max-width: 450px; margin: 20px auto; border: 1px solid #2C2C2C; }
        h1 { color: #BB86FC; margin-bottom: 5px; }
        p { color: #A0A0A0; font-size: 14px; }
        .btn { background: #BB86FC; color: #121212; border: none; padding: 14px 28px; font-size: 16px; font-weight: bold; border-radius: 30px; cursor: pointer; width: 80%; margin: 15px 0; }
        .status { margin-top: 15px; font-weight: 600; color: #03DAC6; }
        #chat { text-align: left; background: #181818; padding: 12px; border-radius: 8px; height: 200px; overflow-y: auto; font-family: monospace; font-size: 13px; margin-top: 15px; border: 1px solid #333; }
    </style>
</head>
<body>
    <div class="card">
        <h1>VEMU CLOUD</h1>
        <p>Voice-Activated AI Companion</p>
        <button class="btn" onclick="startListening()">🎤 Speak to Vemu</button>
        <div class="status" id="status">Tap button and speak</div>
        <div id="chat"></div>
    </div>

    <script>
        const status = document.getElementById('status');
        const chat = document.getElementById('chat');

        function speakText(text) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            window.speechSynthesis.speak(utterance);
        }

        function log(sender, message) {
            chat.innerHTML += `<b>${sender}:</b> ${message}<br><br>`;
            chat.scrollTop = chat.scrollHeight;
        }

        function startListening() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                status.innerText = "Speech Recognition not supported in this browser. Try Chrome.";
                return;
            }

            const recognition = new SpeechRecognition();
            recognition.lang = 'en-US';

            recognition.onstart = () => { status.innerText = "Listening..."; };
            recognition.onspeechend = () => { recognition.stop(); status.innerText = "Processing..."; };

            recognition.onresult = (event) => {
                const command = event.results[0][0].transcript;
                log("You", command);
                askVemu(command);
            };

            recognition.onerror = (e) => {
                status.innerText = "Microphone error. Check permissions.";
            };

            recognition.start();
        }

        function askVemu(query) {
            fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: query })
            })
            .then(res => res.json())
            .then(data => {
                status.innerText = "Ready";
                log("Vemu", data.answer);
                speakText(data.answer);
            })
            .catch(err => {
                status.innerText = "Server response failed.";
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE)

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get("question", "")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=question,
        )
        answer = response.text
    except Exception as e:
        print("Gemini API Error:", e)  # Prints failure reason directly to Render logs
        try:
            answer = wikipedia.summary(question, sentences=2)
        except Exception as wiki_e:
            print("Wikipedia Error:", wiki_e)
            answer = "Sorry, I couldn't find an answer to that."
            
    return jsonify({"answer": answer})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
