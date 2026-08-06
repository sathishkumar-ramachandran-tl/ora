import React, { useEffect, useRef, useState } from 'react';
import { Mic, MicOff, X, Activity, Volume2, AlertCircle } from 'lucide-react';
import { trackEvent } from '../../services/analytics';
import axios from 'axios';
import { API_BASE_URL, getAuthHeader } from '../../config';

interface LiveVoiceAssistantProps {
  isOpen: boolean;
  onClose: () => void;
  persona: string;
}

export const LiveVoiceAssistant: React.FC<LiveVoiceAssistantProps> = ({ isOpen, onClose, persona }) => {
  const [isActive, setIsActive] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

  useEffect(() => {
    if (isOpen) {
      trackEvent('AI_VOICE_SESSION_START');
      const timer = setTimeout(() => startSession(), 500);
      return () => clearTimeout(timer);
    } else {
      stopSession();
    }
  }, [isOpen]);

  const startSession = async () => {
    setIsActive(true);
    setError(null);

    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true
      }});
      streamRef.current = stream;

      // Setup audio context
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const audioContext = new AudioContextClass({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      // Setup audio processing and capture
      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;
      
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      
      // Send audio chunks to backend
      processor.onaudioprocess = async (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        const pcmData = floatTo16BitPCM(inputData);
        const base64Data = arrayBufferToBase64(pcmData);
        
        try {
          // Call backend voice endpoint
          const response = await axios.post(
            `${API_BASE_URL}/agent/voice`,
            { audio: base64Data, persona },
            { headers: getAuthHeader() }
          );
          
          if (response.data.audio) {
            setIsSpeaking(true);
            await playAudioChunk(response.data.audio);
            setIsSpeaking(false);
          }
        } catch (err: any) {
          console.error("Voice API error:", err);
          setError("Connection interrupted");
        }
      };
      
      source.connect(processor);
      processor.connect(audioContext.destination);
      
      trackEvent('AI_VOICE_SESSION_START');
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Audio/Network unavailable");
      setIsActive(false);
    }
  };

  const stopSession = () => {
    // Cleanup Audio Nodes
    if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
    }
    if (sourceRef.current) {
        sourceRef.current.disconnect();
        sourceRef.current = null;
    }
    if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
        audioContextRef.current = null;
    }

    setIsActive(false);
    setIsSpeaking(false);
    trackEvent('AI_AGENT_COMPLETE', { agent: 'VoiceAssistant' });
  };

  const playAudioChunk = async (base64Audio: string) => {
      // Create a fresh context for output to avoid rate mismatches if necessary, or reuse a dedicated output context
      // Note: Live API output is 24kHz. Browser context might be 44.1 or 48.
      const outputCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      
      const binaryString = atob(base64Audio);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
          bytes[i] = binaryString.charCodeAt(i);
      }
      
      const float32Data = new Float32Array(bytes.length / 2);
      const dataView = new DataView(bytes.buffer);
      
      for (let i = 0; i < float32Data.length; i++) {
          // Little Endian
          float32Data[i] = dataView.getInt16(i * 2, true) / 32768.0;
      }
      
      const buffer = outputCtx.createBuffer(1, float32Data.length, 24000);
      buffer.getChannelData(0).set(float32Data);
      
      const source = outputCtx.createBufferSource();
      source.buffer = buffer;
      source.connect(outputCtx.destination);
      source.start(0);
      
      // Wait for playback to finish
      await new Promise(r => setTimeout(r, buffer.duration * 1000));
      
      outputCtx.close();
  };

  // Utilities
  function floatTo16BitPCM(input: Float32Array) {
    const output = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return output.buffer;
  }

  function arrayBufferToBase64(buffer: ArrayBuffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/80 backdrop-blur-md animate-in fade-in">
      <div className="bg-black/90 text-white rounded-3xl p-8 w-full max-w-sm flex flex-col items-center relative shadow-2xl border border-slate-700/50">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors">
            <X size={24} />
        </button>

        <div className="mb-8 mt-4 relative">
            {/* Ambient Glow */}
            <div className={`absolute inset-0 bg-blue-500 rounded-full blur-3xl opacity-20 transition-all duration-500 ${isSpeaking ? 'scale-150 opacity-40' : 'scale-100'}`}></div>
            
            <div className={`w-32 h-32 rounded-full flex items-center justify-center transition-all duration-300 relative z-10 ${isSpeaking ? 'bg-slate-800 scale-105 border-2 border-blue-500/50' : 'bg-slate-800 border border-slate-700'}`}>
                {isSpeaking ? (
                    <Activity className="w-16 h-16 text-blue-500 animate-pulse" />
                ) : (
                    <Mic className="w-12 h-12 text-slate-500" />
                )}
            </div>
        </div>

        <h3 className="text-xl font-bold mb-1 tracking-tight">Ora Voice</h3>
        <p className="text-slate-400 text-sm mb-8 text-center px-4 font-light">
            {error ? (
                <span className="text-red-400 flex items-center gap-1 justify-center"><AlertCircle size={14}/> {error}</span>
            ) : (
                isActive ? "Listening..." : "Initializing..."
            )}
            <br/>
            <span className="text-[10px] text-slate-600 uppercase tracking-widest mt-2 block">{persona.replace('_', ' ')} MODE</span>
        </p>

        <div className="flex gap-4">
             <button 
                onClick={isActive ? stopSession : startSession}
                className={`p-4 rounded-full transition-all duration-300 ${isActive ? 'bg-red-500/20 text-red-500 hover:bg-red-500/30' : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/50'}`}
             >
                {isActive ? <MicOff size={24} /> : <Mic size={24} />}
             </button>
        </div>
      </div>
    </div>
  );
};