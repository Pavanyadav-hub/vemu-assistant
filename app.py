import os
import re
from flask import Flask, render_template_string, request, jsonify
import wikipedia
from google import genai
from google.genai import types

app = Flask(__name__)

# Initializes automatically using GEMINI_API_KEY from Render Environment Variables
client = genai.Client()

def sanitize_text_for_speech(text):
    """Removes Markdown characters (*, #, `, _, etc.) so TTS sounds smooth and natural."""
    text = re.sub(r'[\*\#\_\`\>]', '', text)
    return text.strip()

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
        #chat { text-align: left; background: #181818; padding: 12px; border-radius: 8px; height: 220px; overflow-y: auto; font-family: sans-serif; font-size: 14px; margin-top: 15px; border: 1px solid #333; line-height: 1.4; }
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

        function speakText(text, onCompleteCallback) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1.0;
            if (onCompleteCallback) {
                utterance.onend = onCompleteCallback;
            }
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
                status.innerText = "Microphone error. Check browser permissions.";
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

                if (data.action === "open_url" && data.url) {
                    // Speak confirmation first, then open the website
                    speakText(data.answer, () => {
                        window.open(data.url, '_blank');
                    });
                } else {
                    speakText(data.answer);
                }
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
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"action": "speak", "answer": "I didn't hear a question. Please try speaking again."})

    lower_q = question.lower()

    # 1. COMMAND DETECTION: Open Websites
    if lower_q.startswith("open ") or lower_q.startswith("launch ") or lower_q.startswith("go to "):
        target = lower_q.replace("open ", "").replace("launch ", "").replace("go to ", "").strip()
        target = re.sub(r'[^\w\.\-]', '', target)  # Clean target string

        # Known shortcuts for popular sites
        known_sites = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "github": "https://www.github.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
            "twitter": "https://www.x.com",
            "x": "https://www.x.com",
            "wikipedia": "https://www.wikipedia.org",
            "reddit": "https://www.reddit.com",
            "chatgpt": "https://chatgpt.com",
            "amazon": "https://www.amazon.com",
            "netflix": "https://www.netflix.com",
            "linkedin": "https://www.linkedin.com"
        }

        if target in known_sites:
            url = known_sites[target]
            site_name = target.capitalize()
        else:
            # Handle generic domain requests like "open stackoverflow" or "open example.org"
            if not re.search(r'\.[a-z]{2,}$', target):
                url = f"https://www.{target}.com"
            else:
                url = f"https://{target}" if target.startswith("www.") or target.startswith("http") else f"https://www.{target}"
            site_name = target

        return jsonify({
            "action": "open_url",
            "url": url,
            "answer": f"Opening {site_name}"
        })

    # 2. GENERAL AI ANSWERING: Using Gemini 2.5 Flash
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are VEMU, a voice-activated AI assistant. "
                    "You answer ALL types of questions: general knowledge, coding, math, science, advice, writing, and casual conversation. "
                    "Keep your answers brief, clear, and direct (2-3 sentences max). "
                    "Do NOT use markdown symbols like asterisks (*), hashtags (#), or code blocks so your response sounds natural when spoken aloud."
                ),
                max_output_tokens=250,
            )
        )
        answer = response.text

    except Exception as e:
        print("Gemini API Error:", e)
        # Wikipedia Fallback Logic
        try:
            search_results = wikipedia.search(question)
            if search_results:
                answer = wikipedia.summary(search_results[0], sentences=2)
            else:
                answer = "I couldn't find a direct answer to that, but feel free to ask me something else."
        except Exception as wiki_err:
            print("Wikipedia Fallback Error:", wiki_err)
            answer = "I ran into a temporary issue processing that. Please try again."

    answer = sanitize_text_for_speech(answer)
    return jsonify({"action": "speak", "answer": answer})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
