# Clone the repo locally

git clone <HTTPS_URL> <br>
cd caller <br>
# Livekit Server Instantiation
- Go to LiveKit.io <br>
- create project <br>
- create api keys <br>
- copy api key and secret to jwt.js <br>
- copy livekit URL to /frontend/src/App.js in line 21  <br>
  
# run this inside your python virtual environment
pip install flask flask-cors openai-whisper numpy <br>
python app.py <br>

# in new window run Token Generator 
npm install jsonwebtoken express cors <br>
node jwt.js <br>

# running frontend
cd frontend  <br>
npm install <br>
npm start <br>
