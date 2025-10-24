import jwt from "jsonwebtoken";
import express from "express";
import cors from "cors"

const API_KEY = "<YOUR_LIVEKIT_API_KEY>"
const API_SECRET = "<YOUR_LIVEKIT_SECRET>"

const app = express();
app.use(cors({
  origin: "http://localhost:3000"
}));
app.get("/get_token", (req, res) => {
  const payload = {
    iss: API_KEY,
    sub: "user-" + Math.floor(Math.random() * 1000), // participant identity
    exp: Math.floor(Date.now() / 1000) + 3600,        // 1 hour expiry
    video: {
      room: "test1",
      roomJoin: true,
      roomCreate: true,
      canPublish: true,
      canPublishData: true
    }
  };

  const token = jwt.sign(payload, API_SECRET);
  res.json({ token });
});

app.listen(3001, () => console.log("Token server running on port 3001"));
