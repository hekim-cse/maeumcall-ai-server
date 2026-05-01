#!/bin/bash

# 🧠 1) 가상환경 활성화
source /Users/khe/Graduation/venv/bin/activate

# 🌿 2) .env 환경변수 로드 (이 한 줄 추가!)
set -a; source /Users/khe/Graduation/.env; set +a

# 🎯 3) 서버 포트 설정
PORT=8001

# 🚀 4) FastAPI 서버 백그라운드 실행
echo "▶️ FastAPI 서버를 실행합니다..."
uvicorn main:app --host 0.0.0.0 --port $PORT &

SERVER_PID=$!

# 🌍 5) ngrok 실행
echo "🌐 ngrok을 실행합니다..."
ngrok http $PORT &

NGROK_PID=$!

echo ""
echo "✅ 서버와 ngrok이 실행 중입니다."
echo "⛔️ 중지하려면 [Ctrl + C] 를 누르세요."

# 🧹 Ctrl+C 시 프로세스 종료
trap "echo ''; echo '🛑 서버 중지 중...'; kill $SERVER_PID $NGROK_PID" INT

wait