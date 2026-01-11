import { useState, useEffect, useRef } from "preact/hooks";

interface Message {
  role: "user" | "bot";
  content: string;
}

interface Conversation {
  conversation_id: string;
  title: string;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConv, setCurrentConv] = useState<string | null>(null);
  const [token, setToken] = useState(localStorage.getItem("token") || "");

  const endRef = useRef<HTMLDivElement>(null);
  const scrollDown = () => endRef.current?.scrollIntoView({ behavior: "smooth" });

  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`,
  };

  // ===============================
  // Helper para crear mensajes con tipado seguro
  // ===============================
  const createMessage = (role: "user" | "bot", content: string): Message => ({ role, content });

  // ===============================
  // Cargar conversaciones
  // ===============================
  const loadConversations = async () => {
    if (!token) return;
    const res = await fetch("http://localhost:8000/conversations", { headers });
    if (res.ok) {
      const data = await res.json();
      setConversations(data);
    }
  };

  // ===============================
  // Seleccionar conversación
  // ===============================
  const selectConversation = async (conv_id: string) => {
    setCurrentConv(conv_id);
    const res = await fetch(`http://localhost:8000/conversations/${conv_id}/messages`, { headers });
    if (res.ok) {
      const msgs = await res.json();
      setMessages(msgs);
      scrollDown();
    }
  };

  // ===============================
  // Eliminar conversación
  // ===============================
  const deleteConversation = async (conv_id: string) => {
    await fetch(`http://localhost:8000/conversations/${conv_id}`, { method: "DELETE", headers });
    if (currentConv === conv_id) setMessages([]);
    setCurrentConv(null);
    loadConversations();
  };

  // ===============================
  // Enviar mensaje
  // ===============================
  async function sendMessage() {
    if (!input.trim() || !currentConv || !token) return;

    const userMsg = createMessage("user", input);
    setMessages((prev) => [...prev, userMsg]);
    const messageToSend = input;
    setInput("");
    scrollDown();

    // Crear bloque de bot y obtener su índice
    setMessages((prev) => {
      const botMsg = createMessage("bot", "Generando...");
      const newMessages = [...prev, botMsg];
      const botIndex = newMessages.length - 1;
      streamBotResponse(botIndex, messageToSend, currentConv);
      return newMessages;
    });
  }

  // ===============================
  // Streaming respuesta bot
  // ===============================
  async function streamBotResponse(botIndex: number, userInput: string, convId: string) {
    try {
      const res = await fetch("http://localhost:8000/chat_with_history/stream", {
        method: "POST",
        headers,
        body: JSON.stringify({ message: userInput, conversation_id: convId }),
      });

      if (!res.body) throw new Error("No hay body en la respuesta");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let accumulatedText = "";

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value);
          accumulatedText += chunk;
          setMessages((m) => {
            const newMessages = [...m];
            newMessages[botIndex] = createMessage("bot", accumulatedText);
            return newMessages;
          });
          scrollDown();
        }
      }
    } catch (err) {
      setMessages((m) => [...m, createMessage("bot", "❌ Error al conectar con el backend")]);
      scrollDown();
    }
  }

  // ===============================
  // Crear nueva conversación
  // ===============================
  const createNewConversation = async () => {
    const res = await fetch("http://localhost:8000/conversations", {
      method: "POST",
      headers,
      body: JSON.stringify({}),
    });
    if (res.ok) {
      const data = await res.json();
      loadConversations();
      selectConversation(data.conversation_id);
    }
  };

  useEffect(() => { if (token) loadConversations(); }, [token]);

  // ===============================
  // RENDER
  // ===============================
  return (
    <div class="flex h-screen bg-gray-900 text-white">
      {/* Sidebar */}
      <div class="w-64 bg-gray-800 p-4 flex flex-col">
        <h2 class="text-xl font-bold mb-4">Conversaciones</h2>
        <div class="flex-1 overflow-y-auto space-y-2">
          {conversations.map((conv) => (
            <div key={conv.conversation_id} class="flex justify-between items-center bg-gray-700 px-2 py-1 rounded hover:bg-gray-600">
              <button class="text-left flex-1 text-sm" onClick={() => selectConversation(conv.conversation_id)}>
                {conv.title}
              </button>
              <button class="ml-2 text-gray-400 hover:text-red-500 font-bold" onClick={() => deleteConversation(conv.conversation_id)}>X</button>
            </div>
          ))}
        </div>
        <button class="mt-4 px-4 py-2 bg-green-600 rounded" onClick={createNewConversation}>
          Nueva conversación
        </button>
      </div>

      {/* Chat area */}
      <div class="flex-1 flex flex-col">
        <div class="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((m, i) => (
            <div key={i} class={`max-w-lg px-4 py-2 rounded-xl ${m.role === "user" ? "bg-blue-600 self-end" : "bg-gray-700 self-start whitespace-pre-wrap"}`}>
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
    </div>
  );
}
