import os
import re
import urllib.parse
from flask import Flask, render_template_string, request, jsonify
import wikipedia
from google import genai
from google.genai import types

app = Flask(__name__)

# Configure Wikipedia User-Agent so API requests aren't blocked
wikipedia.set_user_agent("VemuVoiceAssistant/1.0 (https://github.com)")

# Initialize Gemini Client
client = genai.Client()

def sanitize_text_for_speech(text):
    """Removes Markdown symbols so text-to-speech reads smoothly."""
    text = re.sub(r'[\*\#\_\`\>]', '', text)
    return text.strip()

def process_search_or_open_command(question_str):
    """
    Detects if the command asks to open a site OR search within a site.
    Returns a dict with 'action', 'url', 'answer' if matched, else None.
    """
    q = question_str.lower().strip()

    search_urls = {
        "youtube": "https://www.youtube.com/results?search_query=",
        "google": "https://www.google.com/search?q=",
        "chrome": "https://www.google.com/search?q=",
        "wikipedia": "https://en.wikipedia.org/wiki/Special:Search?search=",
        "chatgpt": "https://chatgpt.com/?q=",
        "chat gpt": "https://chatgpt.com/?q=",
        "gemini": "https://gemini.google.com",
        "github": "https://github.com/search?q=",
        "amazon": "https://www.amazon.com/s?k=",
        "reddit": "https://www.reddit.com/search/?q="
    }

    known_sites = {
        "whatsapp": "https://web.whatsapp.com",
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "chrome": "https://www.google.com",
        "github": "https://www.github.com",
        "facebook": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "twitter": "https://www.x.com",
        "x": "https://www.x.com",
        "wikipedia": "https://www.wikipedia.org",
        "reddit": "https://www.reddit.com",
        "chatgpt": "https://chatgpt.com",
        "chat gpt": "https://chatgpt.com",
        "gemini": "https://gemini.google.com",
        "amazon": "https://www.amazon.com",
        "netflix": "https://www.netflix.com",
        "linkedin": "https://www.linkedin.com"
    }

    # "open [site] and search for [query]"
    m1 = re.match(r'^(?:open|go to|launch)\s+([\w\s]+?)\s+and\s+(?:search|look)\s+(?:for|about)\s+(.+)$', q)
    # "search [site] for [query]"
    m2 = re.match(r'^search\s+([\w\s]+?)\s+for\s+(.+)$', q)
    # "search for [query] on/in [site]"
    m3 = re.match(r'^search\s+(?:for\s+)?(.+?)\s+(?:on|in)\s+([\w\s]+)$', q)

    site_target, search_query = None, None

    if m1:
        site_target, search_query = m1.group(1).strip(), m1.group(2).strip()
    elif m2:
        site_target, search_query = m2.group(1).strip(), m2.group(2).strip()
    elif m3:
        search_query, site_target = m3.group(1).strip(), m3.group(2).strip()

    if site_target and search_query:
        encoded_query = urllib.parse.quote(search_query)
        if site_target in search_urls:
            base_url = search_urls[site_target]
            url = base_url if site_target == "gemini" else f"{base_url}{encoded_query}"
            return {
                "action": "open_url",
                "url": url,
                "answer": f"Searching for {search_query} on {site_target.capitalize()}"
            }
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote(f'site:{site_target}.com {search_query}')}"
            return {
                "action": "open_url",
                "url": url,
                "answer": f"Searching for {search_query} on {site_target}"
            }

    # Plain "search for [query]"
    m4 = re.match(r'^search\s+(?:for\s+)?(.+)$', q)
    if m4 and not q.startswith("search on") and not q.startswith("search in"):
        search_query = m4.group(1).strip()
        encoded_query = urllib.parse.quote(search_query)
        return {
            "action": "open_url",
            "url": f"https://www.google.com/search?q={encoded_query}",
            "answer": f"Searching Google for {search_query}"
        }

    # Plain "open [site]"
    m5 = re.match(r'^(?:open|launch|go to)\s+(.+)$', q)
    if m5:
        target = m5.group(1).strip()
        target_clean = re.sub(r'[^a-z0-9\.\-]', '', target).strip('.')

        if target_clean in known_sites:
            return {
                "action": "open_url",
                "url": known_sites[target_clean],
                "answer": f"Opening {target_clean.capitalize()}"
            }
        else:
            if re.search(r'\.[a-z]{2,}$', target_clean):
                url = f"https://{target_clean}" if target_clean.startswith("www.") else f"https://www.{target_clean}"
            else:
                url = f"https://www.{target_clean}.com"
            return {
                "action": "open_url",
                "url": url,
                "answer": f"Opening {target_clean}"
            }

    return None


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
                status.innerText = "Speech Recognition not supported. Try Google Chrome.";
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
                    speakText(data.answer, () => {
                        window.open(data.url, '_blank');
                    });
                } else {
                    speakText(data.answer);
                }
            })
            .catch(err => {
                status.innerText = "Server response failed.";
                speakText("Sorry, I could not connect to the server.");
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

    # 1. NAVIGATION & SITE SEARCH COMMANDS
    nav_response = process_search_or_open_command(question)
    if nav_response:
        return jsonify(nav_response)

    # 2. GENERAL AI ANSWERING WITH GEMINI
    sys_instruction = (
        "You are VEMU, a voice-activated AI assistant. "
        "You answer ALL types of questions: general knowledge, science, coding, math, advice, and conversation. "
        "Keep your answers brief, clear, and direct (2-3 sentences max). "
        "Do NOT use markdown symbols like asterisks (*), hashtags (#), or code blocks."
    )

    answer = None

    # Try gemini-2.5-flash then fallback to gemini-2.0-flash
    for model_name in ['gemini-2.5-flash', 'gemini-2.0-flash']:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=question,
                config=types.GenerateContentConfig(
                    system_instruction=sys_instruction,
                    max_output_tokens=250,
                )
            )
            answer = response.text
            if answer:
                break
        except Exception as e:
            print(f"Gemini Model ({model_name}) Error:", e)

    # 3. WIKIPEDIA FALLBACK
    if not answer:
        try:
            search_results = wikipedia.search(question)
            if search_results:
                answer = wikipedia.summary(search_results[0], sentences=2, auto_suggest=False)
            else:
                answer = "I couldn't find a direct answer to that question."
        except wikipedia.exceptions.DisambiguationError as d_err:
            try:
                answer = wikipedia.summary(d_err.options[0], sentences=2, auto_suggest=False)
            except Exception:
                answer = "I ran into multiple matching pages and couldn't narrow down the answer."
        except Exception as wiki_err:
            print("Wikipedia Fallback Error:", wiki_err)
            answer = "I ran into a temporary issue processing that. Please try again."

    answer = sanitize_text_for_speech(answer)
    return jsonify({"action": "speak", "answer": answer})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
