import sys
import os

# aura_yerel_motor.py'yi bulabilmek için yol ekleme
_bu_klasor = os.path.dirname(os.path.abspath(__file__))
for _yol in (_bu_klasor, os.path.dirname(_bu_klasor)):
    if _yol not in sys.path:
        sys.path.append(_yol)

from flask import Flask, render_template_string, request, jsonify
from aura_yerel_motor import LocalClient

app = Flask(__name__)

# Yerel GGUF motorunu ve modeli tanımlıyoruz
yerel_motor = LocalClient()
MODEL = "aura-v.gguf"

# Sohbet arayüzü (Tek sayfa, HTML + CSS + JS)
HTML_SOHBET = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Aura Basit Sohbet</title>
    <style>
        body { background: #121212; color: #e0e0e0; font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .chat-container { width: 100%; max-width: 600px; height: 85vh; background: #1e1e1e; border-radius: 12px; display: flex; flex-direction: column; box-shadow: 0 4px 20px rgba(0,0,0,0.5); overflow: hidden; border: 1px solid #333; }
        .chat-header { background: #252525; padding: 15px; text-align: center; font-weight: bold; font-size: 16px; border-bottom: 1px solid #333; color: #4ade80; }
        .chat-messages { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .message { padding: 10px 14px; border-radius: 8px; max-width: 80%; line-height: 1.4; word-wrap: break-word; font-size: 14px; }
        .user { background: #2563eb; color: #fff; align-self: flex-end; }
        .bot { background: #374151; color: #f3f4f6; align-self: flex-start; }
        .chat-input-area { display: flex; padding: 12px; background: #252525; border-top: 1px solid #333; gap: 8px; }
        input { flex: 1; padding: 10px 14px; background: #121212; border: 1px solid #444; color: #fff; border-radius: 6px; outline: none; font-size: 14px; }
        input:focus { border-color: #4ade80; }
        button { background: #4ade80; color: #000; border: none; padding: 10px 18px; font-weight: bold; border-radius: 6px; cursor: pointer; }
        button:hover { background: #22c55e; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">🤖 AURA YEREL SOHBET (aura-v.gguf)</div>
        <div class="chat-messages" id="chat-messages">
            <div class="message bot">Selam Mimar Volkan! Seni dinliyorum, ne konuşmak istiyoruz?</div>
        </div>
        <div class="chat-input-area">
            <input type="text" id="user-input" placeholder="Mesajını yaz..." autofocus>
            <button onclick="mesajGonder()">Gönder</button>
        </div>
    </div>

    <script>
        const inputField = document.getElementById('user-input');
        inputField.addEventListener('keydown', (e) => { if (e.key === 'Enter') mesajGonder(); });

        async function mesajGonder() {
            const text = inputField.value.trim();
            if (!text) return;

            const chatBox = document.getElementById('chat-messages');
            
            // Kullanıcı mesajını ekle
            chatBox.innerHTML += `<div class="message user">${text}</div>`;
            inputField.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            // Bot yanıtı için placeholder
            const botDiv = document.createElement('div');
            botDiv.className = 'message bot';
            botDiv.innerText = 'Düşünüyor...';
            chatBox.appendChild(botDiv);
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const res = await fetch('/api/sohbet', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mesaj: text })
                });
                const data = await res.json();
                botDiv.innerText = data.cevap || '...';
            } catch (err) {
                botDiv.innerText = '⚠️ Bağlantı hatası!';
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_SOHBET)

@app.route('/api/sohbet', methods=['POST'])
def sohbet_api():
    veri = request.get_json()
    mesaj = veri.get('mesaj', '')
    
    try:
        r = yerel_motor.generate(
            model=MODEL,
            prompt = (
    "Sen Mimar Volkan'ın yapay zeka asistanı Aura'sın. "
    "Kullanıcının yazdığı dilde veya senden istediği dilde (örneğin İbranice, İngilizce vb.) cevap ver. "
    "Çeviri istendiğinde birebir istenen dilde yanıt üret. "
    f"Kullanıcı: {mesaj}\nCevap:"
),
            options={"temperature": 0.7, "num_predict": 250},
        )
        cevap = (r["response"] or "").strip() or "..."
        
        # Anlatım bozukluğu filtresi
        cevap = cevap.replace("Seninle nasıl yardımcı olabilirim", "Sana nasıl yardımcı olabilirim")
        cevap = cevap.replace("seninle nasıl yardımcı olabilirim", "sana nasıl yardımcı olabilirim")

    except Exception as e:
        cevap = f"Hata oluştu: {str(e)}"
        
    return jsonify({"cevap": cevap})

if __name__ == '__main__':
    print("🚀 Basit Sohbet Sunucusu Başlatıldı: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
