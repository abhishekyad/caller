# Clone the repo locally

git clone <HTTPS_URL>
cd caller
# Livekit Server Instantiation
- Go to LiveKit.io
- create project
- create api keys
- copy api key and secret to jwt.js
- copy livekit URL to /frontend/src/App.js in line 21
  
# run this inside your python virtual environment
pip install flask flask-cors openai-whisper numpy
python app.py

# in new window run Token Generator 
npm install jsonwebtoken express cors
node jwt.js

# running frontend
cd frontend
npm install
npm start
