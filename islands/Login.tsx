import { useState } from "preact/hooks";

export default function LoginIsland() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleSubmit(e: Event) {
    e.preventDefault();
    setError("");
    setSuccess("");

    try {
      const res = await fetch("http://localhost:8000/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, isRegister }),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Error desconocido");
        return;
      }

      if (!isRegister) {
        // Guardamos token
        localStorage.setItem("token", data.access_token);
        window.location.href = "/chat";
      } else {
        setSuccess("Usuario registrado correctamente. Ahora inicia sesión.");
        setIsRegister(false);
        setPassword("");
      }
    } catch (err) {
      setError("❌ Error de conexión al servidor");
    }
  }

  return (
    <div class="flex flex-col items-center justify-center h-screen bg-gray-900 text-white">
      <h1 class="text-3xl mb-6">{isRegister ? "Registrarse" : "Iniciar sesión"}</h1>

      <form class="flex flex-col gap-4 w-80" onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Correo"
          value={email}
          onInput={(e) => setEmail(e.currentTarget.value)}
          required
          class="px-4 py-2 rounded bg-gray-700 text-white"
        />
        <input
          type="password"
          placeholder="Contraseña"
          value={password}
          onInput={(e) => setPassword(e.currentTarget.value)}
          required
          class="px-4 py-2 rounded bg-gray-700 text-white"
        />

        <button type="submit" class="px-4 py-2 bg-green-600 rounded">
          {isRegister ? "Registrarse" : "Iniciar sesión"}
        </button>

        <button
          type="button"
          class="mt-2 text-blue-400 underline"
          onClick={() => {
            setIsRegister(!isRegister);
            setError("");
            setSuccess("");
          }}
        >
          {isRegister ? "Ya tengo cuenta" : "Crear cuenta nueva"}
        </button>

        {error && <p class="text-red-500">{error}</p>}
        {success && <p class="text-green-500">{success}</p>}
      </form>
    </div>
  );
}
