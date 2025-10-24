// import { connect } from 'livekit-client';

const url = 'wss://alpha-kojiftd1.livekit.cloud'; // your LiveKit server
//const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NjEyOTE4MDEsImlkZW50aXR5IjoibmV3IHRva2VuIiwiaXNzIjoiQVBJdU1EZHdXRFRtV1p5IiwibmJmIjoxNzYxMjkwOTAxLCJzdWIiOiJuZXcgdG9rZW4iLCJ2aWRlbyI6eyJjYW5QdWJsaXNoIjp0cnVlLCJjYW5QdWJsaXNoRGF0YSI6dHJ1ZSwiY2FuU3Vic2NyaWJlIjp0cnVlLCJyb29tIjoibXktcm9vbSIsInJvb21Kb2luIjp0cnVlfX0.mfdyJrOcmLejS3LepOT7ptbrSIAp3-e39xUJJ42CJOA';

import { AccessToken, VideoGrant } from 'livekit-server-sdk';

const roomName = 'my-room';
const participantName = 'Abhishek';

const at = new AccessToken(process.env.LIVEKIT_API_KEY, process.env.LIVEKIT_API_SECRET, {
  identity: participantName,
});

const videoGrant=new VideoGrant( {
  room: roomName,
  roomJoin: true,
  canPublish: true,
  canSubscribe: true,
});

at.addGrant(videoGrant);

const token = await at.toJwt();
console.log('access token', token);