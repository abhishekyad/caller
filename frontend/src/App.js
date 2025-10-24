import { Room, createLocalTracks } from "livekit-client";
import React, { useState, useRef } from "react";

export default function App() {
  const [connected, setConnected] = useState(false);
  const [transcript, setTranscript] = useState("");
  const roomRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);

  const joinRoom = async () => {
    try {
      const room = new Room();
      roomRef.current = room;

      // Get token
      const tokenResp = await fetch("http://localhost:3001/get_token");
      const { token } = await tokenResp.json();

      await room.connect("wss://<YOUR_PROJECT>.livekit.cloud", token);

      // Local mic
      const [audioTrack] = await createLocalTracks({ audio: true });
      await room.localParticipant.publishTrack(audioTrack);

      // Capture mic into buffer
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(
        new MediaStream([audioTrack.mediaStreamTrack])
      );

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      source.connect(processor);
      processor.connect(audioContext.destination);

      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        // Store Float32 data
        audioChunksRef.current.push(new Float32Array(input));
      };

      setConnected(true);
      console.log("🎤 Recording started...");
    } catch (err) {
      console.error("Failed to join room:", err);
    }
  };

  const leaveRoom = async () => {
    console.log("⏹ Stopping recording and sending audio...");

    if (processorRef.current) processorRef.current.disconnect();
    if (audioContextRef.current) audioContextRef.current.close();
    if (roomRef.current) roomRef.current.disconnect();

    // Convert buffered Float32 chunks → PCM16 WAV blob
    const allSamples = mergeFloat32Chunks(audioChunksRef.current);
    const wavBlob = encodeWAV(allSamples, 44100);

    // Send to backend
    const res = await fetch("http://127.0.0.1:5000/call", {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: await wavBlob.arrayBuffer(),
    });

    const data = await res.json();
    setTranscript(data.response || data.text || "I need to check with my supervisor");
    console.log("✅ Sent to backend:", data);

    // Reset
    audioChunksRef.current = [];
    setConnected(false);
  };

  // Helper: merge all Float32 chunks
  const mergeFloat32Chunks = (chunks) => {
    const totalLength = chunks.reduce((acc, cur) => acc + cur.length, 0);
    const result = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.length;
    }
    return result;
  };

  // Helper: encode to WAV PCM16
  const encodeWAV = (samples, sampleRate) => {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    // WAV header
    writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, "WAVE");
    writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, "data");
    view.setUint32(40, samples.length * 2, true);

    floatTo16BitPCM(view, 44, samples);

    return new Blob([view], { type: "audio/wav" });
  };

  const floatTo16BitPCM = (view, offset, input) => {
    for (let i = 0; i < input.length; i++, offset += 2) {
      let s = Math.max(-1, Math.min(1, input[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
  };

  const writeString = (view, offset, string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  };

  return (
    <div className="p-6 text-center">
      <h1 className="text-2xl font-bold mb-4">🎙️ LiveKit Voice Recorder</h1>

      {!connected ? (
        <button
          className="bg-blue-500 text-white px-4 py-2 rounded"
          onClick={joinRoom}
        >
          Join Room / Start Recording
        </button>
      ) : (
        <button
          className="bg-red-500 text-white px-4 py-2 rounded"
          onClick={leaveRoom}
        >
          Leave Room / Stop & Send
        </button>
      )}

      <div className="mt-4">
        <strong>Last transcription:</strong>
        <div className="p-2 mt-2 border border-gray-300 rounded h-20 overflow-auto bg-gray-100">
          {transcript || "Waiting for speech..."}
        </div>
      </div>
    </div>
  );
}
