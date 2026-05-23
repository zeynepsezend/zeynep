import { useState, useCallback } from 'react';
import type { Message } from '../components/ChatPanel/MessageBubble';
import type { NodeStatus } from '../components/ProcessPanel/ToolStatusCard';
import type { AgentEvent, AgentResponse } from '../utils/wsProtocol';

export interface UseAgentStateReturn {
  messages: Message[];
  nodeStatuses: Record<string, NodeStatus>;
  isAgentRunning: boolean;
  addUserMessage: (content: string) => void;
  handleAgentEvent: (event: AgentEvent) => void;
  handleAgentResponse: (response: AgentResponse) => void;
}

let messageCounter = 0;

export function useAgentState(): UseAgentStateReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [nodeStatuses, setNodeStatuses] = useState<Record<string, NodeStatus>>({});
  const [isAgentRunning, setIsAgentRunning] = useState(false);

  const addUserMessage = useCallback((content: string) => {
    const msg: Message = {
      id: `user-${++messageCounter}-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, msg]);
    setIsAgentRunning(true);
  }, []);

  const handleAgentEvent = useCallback((event: AgentEvent) => {
    const statusMap: Record<string, NodeStatus> = {
      started: 'running',
      completed: 'completed',
      error: 'error',
    };

    setNodeStatuses(prev => ({
      ...prev,
      [event.node]: statusMap[event.status] ?? 'pending',
    }));

    // If any node starts, agent is running
    if (event.status === 'started') {
      setIsAgentRunning(true);
    }
  }, []);

  const handleAgentResponse = useCallback((response: AgentResponse) => {
    const msg: Message = {
      id: `agent-${++messageCounter}-${Date.now()}`,
      role: 'agent',
      content: response.content,
      timestamp: Date.now(),
      toolCalls: response.tool_calls,
    };
    setMessages(prev => [...prev, msg]);
    setIsAgentRunning(false);
  }, []);

  return {
    messages,
    nodeStatuses,
    isAgentRunning,
    addUserMessage,
    handleAgentEvent,
    handleAgentResponse,
  };
}
