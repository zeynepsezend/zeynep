import React, { useRef, useEffect, useState, useCallback } from 'react';
import GlassPanel from '../common/GlassPanel';
import MessageBubble, { Message } from './MessageBubble';

export type { Message };

export interface ChatPanelProps {
  messages: Message[];
  onSend: (text: string) => void;
  isAgentRunning: boolean;
}

const TypingIndicator: React.FC = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '8px 0 4px 8px',
  }}>
    <style>{`
      @keyframes typingBounce {
        0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
        40% { transform: translateY(-4px); opacity: 1; }
      }
    `}</style>
    {[0, 1, 2].map(i => (
      <span key={i} style={{
        display: 'inline-block',
        width: '6px',
        height: '6px',
        borderRadius: '50%',
        background: '#00E5FF',
        animation: `typingBounce 1.2s ease-in-out ${i * 0.2}s infinite`,
      }} />
    ))}
    <span style={{
      color: '#6b7b8d',
      fontSize: '12px',
      marginLeft: '4px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
    }}>
      Agent is thinking
    </span>
  </div>
);

const SendIcon: React.FC = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const ChatPanel: React.FC<ChatPanelProps> = ({ messages, onSend, isAgentRunning }) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAgentRunning]);

  const handleSend = useCallback(() => {
    const text = inputValue.trim();
    if (!text || isAgentRunning) return;
    onSend(text);
    setInputValue('');
  }, [inputValue, isAgentRunning, onSend]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const panelStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    padding: 0,
    overflow: 'hidden',
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '14px 16px 12px',
    borderBottom: '1px solid rgba(0, 229, 255, 0.1)',
    flexShrink: 0,
  };

  const headerTitleStyle: React.CSSProperties = {
    color: '#e0e6ed',
    fontSize: '13px',
    fontWeight: 600,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const statusDotStyle: React.CSSProperties = {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    background: isAgentRunning ? '#FF9500' : '#00C853',
    boxShadow: isAgentRunning ? '0 0 6px #FF9500' : '0 0 6px #00C853',
    animation: isAgentRunning ? 'agentPulse 1s ease-in-out infinite' : 'none',
  };

  const messagesAreaStyle: React.CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: '14px 16px',
    scrollbarWidth: 'thin',
    scrollbarColor: 'rgba(0,229,255,0.2) transparent',
  };

  const inputAreaStyle: React.CSSProperties = {
    borderTop: '1px solid rgba(0, 229, 255, 0.1)',
    padding: '12px 16px',
    display: 'flex',
    gap: '10px',
    alignItems: 'flex-end',
    flexShrink: 0,
  };

  const textareaStyle: React.CSSProperties = {
    flex: 1,
    background: 'rgba(255, 255, 255, 0.04)',
    border: '1px solid rgba(0, 229, 255, 0.2)',
    borderRadius: '8px',
    padding: '9px 12px',
    color: '#e0e6ed',
    fontSize: '13.5px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
    resize: 'none',
    outline: 'none',
    lineHeight: '1.5',
    minHeight: '38px',
    maxHeight: '120px',
    overflowY: 'auto',
    opacity: isAgentRunning ? 0.5 : 1,
    transition: 'border-color 0.15s, opacity 0.2s',
  };

  const sendButtonStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '38px',
    height: '38px',
    borderRadius: '8px',
    border: 'none',
    background: isAgentRunning || !inputValue.trim()
      ? 'rgba(0, 229, 255, 0.1)'
      : 'rgba(0, 229, 255, 0.2)',
    color: isAgentRunning || !inputValue.trim() ? '#6b7b8d' : '#00E5FF',
    cursor: isAgentRunning || !inputValue.trim() ? 'not-allowed' : 'pointer',
    transition: 'background 0.15s, color 0.15s',
    flexShrink: 0,
    outline: 'none',
  };

  const emptyStateStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: '#6b7b8d',
    fontSize: '13px',
    gap: '8px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  return (
    <>
      <style>{`
        @keyframes agentPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        .chat-textarea:focus {
          border-color: rgba(0, 229, 255, 0.5) !important;
        }
        .chat-messages::-webkit-scrollbar {
          width: 4px;
        }
        .chat-messages::-webkit-scrollbar-track {
          background: transparent;
        }
        .chat-messages::-webkit-scrollbar-thumb {
          background: rgba(0,229,255,0.2);
          border-radius: 2px;
        }
      `}</style>

      <GlassPanel style={panelStyle}>
        <div style={headerStyle}>
          <span style={statusDotStyle} />
          <span style={headerTitleStyle}>Agent Chat</span>
        </div>

        <div className="chat-messages" style={messagesAreaStyle}>
          {messages.length === 0 ? (
            <div style={emptyStateStyle}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="rgba(0,229,255,0.3)" strokeWidth="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <span>Send a message to start</span>
            </div>
          ) : (
            messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))
          )}
          {isAgentRunning && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        <div style={inputAreaStyle}>
          <textarea
            ref={inputRef}
            className="chat-textarea"
            style={textareaStyle}
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isAgentRunning ? 'Agent is running...' : 'Message the agent... (Enter to send)'}
            disabled={isAgentRunning}
            rows={1}
          />
          <button
            style={sendButtonStyle}
            onClick={handleSend}
            disabled={isAgentRunning || !inputValue.trim()}
            title="Send message"
            aria-label="Send message"
          >
            <SendIcon />
          </button>
        </div>
      </GlassPanel>
    </>
  );
};

export default React.memo(ChatPanel);
