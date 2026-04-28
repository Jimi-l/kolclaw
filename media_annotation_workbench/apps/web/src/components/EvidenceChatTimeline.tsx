import type { EvidenceChatMessage } from "../lib/types";

interface EvidenceChatTimelineProps {
  messages: EvidenceChatMessage[];
}

export function EvidenceChatTimeline({ messages }: EvidenceChatTimelineProps) {
  if (messages.length === 0) {
    return <p className="muted-text">当前没有可展示的证据消息。</p>;
  }

  return (
    <div className="evidence-chat-panel">
      {messages.map((message) => {
        const isAgency = message.role === "agency";
        const rowClassName = `chat-message-row ${isAgency ? "chat-message-row-agency" : "chat-message-row-creator"}`;
        const bubbleClassName = `chat-bubble ${isAgency ? "chat-bubble-agency" : "chat-bubble-creator"} ${
          message.is_direct_evidence ? "chat-direct-evidence" : ""
        }`;
        const showRawToggle = Boolean(message.raw_text) && message.raw_text !== message.clean_text;

        return (
          <div className={rowClassName} key={message.message_id}>
            <article className={bubbleClassName}>
              <div className="chat-meta">
                <span className="chat-badge">{message.speaker_badge}</span>
                <strong>{message.speaker_name}</strong>
                <span className="chat-time">{message.formatted_time ?? "时间未知"}</span>
                {message.is_direct_evidence ? <span className="chat-evidence-flag">直接证据</span> : null}
              </div>
              <div className="chat-text">{message.clean_text || "（空消息）"}</div>
              {showRawToggle ? (
                <details className="chat-raw-toggle">
                  <summary>查看原文</summary>
                  <div className="chat-raw-text">{message.raw_text}</div>
                </details>
              ) : null}
            </article>
          </div>
        );
      })}
    </div>
  );
}
