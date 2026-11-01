import { useState, useCallback } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useNeoChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(async (text) => {
    setIsLoading(true);
    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    
    const assistantMsg = { role: 'assistant', content: '', log: [] };
    setMessages(prev => [...prev, assistantMsg]);
    
    try {
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: messages.slice(-10) })
      });
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      
      while (!done) {
        const { value, done: streamDone } = await reader.read();
        done = streamDone;
        const chunk = decoder.decode(value, { stream: true });
        
        // Parse SSE lines: data: {...}
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'token') {
                setMessages(prev => {
                  const last = prev[prev.length - 1];
                  return [
                    ...prev.slice(0, -1),
                    { ...last, content: last.content + data.content }
                  ];
                });
              } else if (data.type === 'complete') {
                setMessages(prev => {
                  const last = prev[prev.length - 1];
                  return [
                    ...prev.slice(0, -1),
                    { ...last, log: data.log, stats: data.stats }
                  ];
                });
              }
            } catch (e) {
              // ignore parse errors from partial chunks
            }
          }
        }
      }
    } catch (err) {
      console.error('Stream error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [messages]);

  return { messages, sendMessage, isLoading };
}