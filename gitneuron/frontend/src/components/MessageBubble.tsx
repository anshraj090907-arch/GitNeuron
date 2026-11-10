import ReactMarkdown from "react-markdown";
import type { ChatMessage } from "../lib/types";
import ReasoningTrace from "./ReasoningTrace";
import SourcesPanel from "./SourcesPanel";
import ExportMenu from "./ExportMenu";
import MermaidBlock from "./MermaidBlock";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`message message--${message.role}`}>
      <div className="message__role">{isUser ? "You" : "GitNeuron"}</div>

      {!isUser && message.reasoning && message.reasoning.length > 0 && (
        <ReasoningTrace steps={message.reasoning} live={!!message.streaming} />
      )}

      <div className="message__body">
        <ReactMarkdown
          components={{
            // react-markdown wraps fenced code in <pre>; we take over that
            // wrapping ourselves so a ```mermaid block can render as a
            // diagram instead of being forced into a <pre>.
            pre({ children }) {
              return <>{children}</>;
            },
            code(props) {
              const { className, children, ...rest } = props as any;
              const match = /language-(\w+)/.exec(className || "");
              const text = String(children).replace(/\n$/, "");

              if (match?.[1] === "mermaid") {
                return <MermaidBlock code={text} />;
              }
              if (match) {
                return (
                  <pre>
                    <code className={className} {...rest}>
                      {text}
                    </code>
                  </pre>
                );
              }
              return (
                <code className={className} {...rest}>
                  {text}
                </code>
              );
            },
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>

      {!isUser && !message.streaming && message.sources && <SourcesPanel sources={message.sources} />}

      {!isUser && !message.streaming && message.content && (
        <div className="message__footer">
          {message.modelUsed && message.modelUsed !== "none" && (
            <span className="message__model">{message.modelUsed}</span>
          )}
          <ExportMenu title="GitNeuron answer" content={message.content} sources={message.sources ?? []} />
        </div>
      )}
    </div>
  );
}
