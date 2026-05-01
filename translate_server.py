# 📁 translate_server.py
from flask import Flask, request, jsonify
from translate import Translator  # pip install translate

app = Flask(__name__)
translator = Translator(to_lang="ko", from_lang="en")

@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "🔁 번역 서버 실행 중입니다."})

@app.route("/translate", methods=["POST"])
def translate_text():
    data = request.json
    text = data.get("text", "")
    try:
        translated = translator.translate(text)
        return jsonify({"translated": translated})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("✅ 번역 서버가 http://localhost:5000 에서 실행 중입니다!")
    app.run(port=5000)