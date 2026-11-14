"""Saathi AI backend.  Run:  python server.py   then open http://localhost:8000

  /api/ask     RAG: MCP search_faq (+ optional NotebookLM MCP bridge, + optional Claude)
  /api/tts     spoken answer in hi/kn/ta via edge-tts (neural voices, needs internet)
  /api/tickets HR tickets stored through the MCP server tools
  /api/health  capability report used by the page

Optional environment variables
  ANTHROPIC_API_KEY      let Claude rephrase the retrieved answer (grounded, same language)
  NOTEBOOKLM_MCP_CMD     command that starts a NotebookLM MCP server (stdio), e.g. "npx -y notebooklm-mcp@latest"
  NOTEBOOKLM_MCP_TOOL    tool name of that server to query (default: ask_question)
  NOTEBOOKLM_MCP_ARG     argument name for the question (default: question)
"""
import asyncio, json, os, shlex, subprocess, sys, threading, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))
VOICES = {"hi": "hi-IN-SwaraNeural", "kn": "kn-IN-SapnaNeural", "ta": "ta-IN-PallaviNeural", "en": "en-IN-NeerjaNeural"}


class MCPClient:
    """Minimal MCP stdio client (initialize / tools/list / tools/call)."""

    def __init__(self, cmd, cwd=None):
        self.cmd, self.cwd, self.p, self.n, self.lock, self.tools = cmd, cwd, None, 0, threading.Lock(), []

    def start(self):
        self.p = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  cwd=self.cwd, text=True, encoding="utf-8", bufsize=1, shell=isinstance(self.cmd, str))
        self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "saathi-web", "version": "1.0"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"); self.p.stdin.flush()
        self.tools = [t["name"] for t in self.rpc("tools/list", {}).get("tools", [])]

    def rpc(self, method, params):
        with self.lock:
            self.n += 1
            self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n"); self.p.stdin.flush()
            while True:
                line = self.p.stdout.readline()
                if not line: raise RuntimeError("MCP server closed")
                try: m = json.loads(line)
                except ValueError: continue
                if m.get("id") == self.n:
                    if "error" in m: raise RuntimeError(m["error"].get("message"))
                    return m["result"]

    def call(self, name, args):
        r = self.rpc("tools/call", {"name": name, "arguments": args})
        text = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        try: return json.loads(text)
        except ValueError: return text


saathi = MCPClient([sys.executable, os.path.join(HERE, "saathi_mcp.py")], HERE)
notebook = None


def init_mcp():
    global notebook
    saathi.start()
    cmd = os.environ.get("NOTEBOOKLM_MCP_CMD")
    if cmd:
        try:
            notebook = MCPClient(cmd); notebook.start()
            print("NotebookLM MCP connected, tools:", notebook.tools)
        except Exception as e:
            notebook = None; print("NotebookLM MCP not available:", e)


def ask_notebooklm(q):
    if not notebook: return None
    tool = os.environ.get("NOTEBOOKLM_MCP_TOOL", "ask_question")
    if tool not in notebook.tools: return None
    try:
        r = notebook.call(tool, {os.environ.get("NOTEBOOKLM_MCP_ARG", "question"): q})
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
    except Exception as e:
        print("NotebookLM error:", e); return None


def ask_claude(question, language, context):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key: return None
    lang = {"hi": "Hindi", "kn": "Kannada", "ta": "Tamil", "en": "English"}[language]
    body = {"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 600,
            "system": f"You are Saathi, an HR assistant for factory workers. Answer ONLY from the context, in simple {lang}, max 5 short sentences. If the context does not answer it, say HR should be contacted.",
            "messages": [{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", json.dumps(body).encode(),
                                 {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)["content"][0]["text"].strip()


def tts_available():
    try:
        import edge_tts  # noqa
        return True
    except ImportError:
        return False


def synth(text, language):
    import edge_tts
    async def go():
        out = bytearray()
        async for ch in edge_tts.Communicate(text, VOICES.get(language, VOICES["hi"]), rate="-15%").stream():
            if ch["type"] == "audio": out += ch["data"]
        return bytes(out)
    return asyncio.run(go())


def api_ask(d):
    q, lang = (d.get("question") or "").strip(), d.get("language", "hi")
    res = saathi.call("search_faq", {"query": (d.get("hint_question") or q), "language": lang})
    ms = res["matches"]
    if not res["understood"]:
        return {"understood": False, "answer": "", "retrieval_score": ms[0]["score"] if ms else 0}
    top = ms[0]
    answer, mode, llm_used, llm_err = top["answer"], "faq_grounded", False, None
    nb = ask_notebooklm(q)
    context = "\n\n".join(f"[{m['id']}] {m['answer_en'] or m['answer']}" for m in ms) + (f"\n\n[NotebookLM]\n{nb}" if nb else "")
    try:
        out = ask_claude(q, lang, context)
        if out: answer, mode, llm_used = out, "llm_grounded_rag", True
    except Exception as e:
        llm_err = str(e)
    sources = [{"name": top.get("source_name") or "Saathi FAQ"}] + ([{"name": "NotebookLM"}] if nb else [])
    r = {"understood": True, "answer": answer, "english_translation": top["answer_en"], "faq_id": top["id"],
         "topic": "esic" if "esic" in (top["question_en"] + top["category"]).lower() else "pf",
         "retrieval_score": top["score"], "answer_mode": mode, "llm_used": llm_used, "sources": sources,
         "notebooklm_used": bool(nb), "mcp_tools_used": ["saathi.search_faq"] + (["notebooklm." + os.environ.get("NOTEBOOKLM_MCP_TOOL", "ask_question")] if nb else []),
         "ticket_suggested": bool(top["human_escalation_recommended"] or top["authenticated_data_required"])}
    if llm_err: r["llm_error"] = llm_err
    return r


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes): body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f: return self.send(200, f.read(), "text/html; charset=utf-8")
        if p == "/api/health":
            return self.send(200, {"ok": True, "tts_configured": tts_available(), "llm_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
                                   "mcp": {"connected": bool(saathi.p and saathi.p.poll() is None), "tools": saathi.tools},
                                   "notebooklm": {"connected": bool(notebook), "tools": notebook.tools if notebook else []}})
        if p == "/api/tickets": return self.send(200, {"tickets": saathi.call("list_hr_tickets", {})})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            d = self.body()
            if p == "/api/ask": return self.send(200, api_ask(d))
            if p == "/api/tts": return self.send(200, synth(d.get("text", ""), d.get("language", "hi")), "audio/mpeg")
            if p == "/api/tickets": return self.send(200, {"ticket": saathi.call("create_hr_ticket", d), "delivery": "local_demo_only"})
        except Exception as e:
            return self.send(500, {"error": str(e)})
        self.send(404, {"error": "not found"})

    def do_PATCH(self):
        p = urlparse(self.path).path
        if p.startswith("/api/tickets/"):
            return self.send(200, {"ticket": saathi.call("update_hr_ticket", {"id": p.rsplit("/", 1)[1], "status": self.body().get("status")})})
        self.send(404, {"error": "not found"})


if __name__ == "__main__":
    init_mcp()
    print(f"Saathi AI running at http://localhost:{PORT}  (MCP tools: {saathi.tools}; TTS: {tts_available()})")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
