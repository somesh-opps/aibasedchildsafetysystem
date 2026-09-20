import sys

with open("dashboard/client/src/App.tsx", "r") as f:
    content = f.read()

# Patch API function to include auth token
old_api_func = """async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase}${path}`, { headers: { "Content-Type": "application/json", ...(init?.headers || {}) }, ...init });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.error?.message || `Request failed (${res.status})`);
  const body = await res.json();
  return body.data ?? body;
}"""

new_api_func = """async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem("child_safety_token");
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init?.headers as any || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${apiBase}${path}`, { headers, ...init });
  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      sessionStorage.removeItem("child_safety_session");
      sessionStorage.removeItem("child_safety_token");
      window.dispatchEvent(new Event("unauthorized"));
    }
    throw new Error((await res.json().catch(() => null))?.detail || `Request failed (${res.status})`);
  }
  const body = await res.json();
  return body.data ?? body;
}"""

content = content.replace(old_api_func, new_api_func)

# Fix Login success handler to save token
old_login = """try { await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }); onSuccess(); }"""
new_login = """try { const res: any = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }); sessionStorage.setItem("child_safety_token", res.token); onSuccess(); }"""
content = content.replace(old_login, new_login)

# Add event listener for unauthorized
old_app_effect = """  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);"""
new_app_effect = """  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);
  useEffect(() => {
    const handleAuth = () => setAuthenticated(false);
    window.addEventListener("unauthorized", handleAuth);
    return () => window.removeEventListener("unauthorized", handleAuth);
  }, []);"""
content = content.replace(old_app_effect, new_app_effect)

with open("dashboard/client/src/App.tsx", "w") as f:
    f.write(content)
