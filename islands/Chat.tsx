
import { useState, useRef } from "preact/hooks";

export default function Chat() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const scrollDown = () => endRef.current?.scrollIntoView({ behavior: "smooth" });

  async function sendMessage() {
    if (!input.trim()) return;

    // Agregamos mensaje del usuario
    const userMsg = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    scrollDown();

    // Agregamos mensaje vacío del bot y obtenemos índice
    setMessages((prev) => {
      const newMessages = [...prev, { role: "bot", content: "" }];
      const botIndex = newMessages.length - 1;
      streamBotResponse(botIndex, input);
      return newMessages;
    });
  }

  async function streamBotResponse(botIndex: number, userInput: string) {
  try {
    // Insertamos mensaje temporal
    setMessages((m) => {
      const newMessages = [...m];
      newMessages[botIndex] = { role: "bot", content: "Generando..." };
      return newMessages;
    });
    scrollDown();

    const res = await fetch("http://localhost:8000/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userInput }),
    });

    const reader = res.body?.getReader();
    const decoder = new TextDecoder();
    let done = false;

    // Empezamos con contenido vacío para reemplazar "Generando..."
    let accumulatedText = "";

    while (!done && reader) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      const chunk = decoder.decode(value);
      const text = chunk.replace(/^data: /, "");

      if (text) {
        accumulatedText += text;
        setMessages((m) => {
          const newMessages = [...m];
          newMessages[botIndex] = { role: "bot", content: accumulatedText };
          return newMessages;
        });
        scrollDown();
      }
    }
  } catch (err) {
    setMessages((m) => [
      ...m,
      { role: "bot", content: "❌ Error al conectar con el backend" },
    ]);
    scrollDown();
  }
}


  return (
    <div class="flex flex-col h-screen bg-gray-900 text-white">
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m, i) => (
          <div
            key={i}
            class={`max-w-lg px-4 py-2 rounded-xl ${
              m.role === "user" ? "bg-blue-600 self-end" : "bg-gray-700 self-start whitespace-pre-wrap"
            }`}
          >
            {m.content}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div class="flex p-4 bg-gray-800 gap-2">
        <input
          class="flex-1 px-4 py-2 bg-gray-700 rounded text-white"
          placeholder="Escribe un mensaje..."
          value={input}
          onInput={(e) => setInput(e.currentTarget.value)}
          onKeyDown={(e) => { if (e.key === "Enter") sendMessage(); }}
        />
        <button class="px-4 py-2 bg-green-600 rounded" onClick={sendMessage}>
          Enviar
        </button>
      </div>
    </div>
  );
}
