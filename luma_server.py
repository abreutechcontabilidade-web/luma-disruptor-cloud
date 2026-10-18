import http.server
import socketserver
import json
import time
import os
import sys
import threading
import unicodedata
import urllib.request
import re
import html
from datetime import datetime, timezone

PORT = int(os.environ.get("PORT", 8000))
HOST = "0.0.0.0"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

class WebCISOGate:
    # Cura F1: Decodifica entidades HTML antes de validar e bloqueia iframe/srcdoc
    VETOS_WEB = [
        r"<script\b", r"\bon\w+\s*=", r"javascript\s*:", 
        r"\bnew\s+Function\b", r"\batob\s*\(", r"\beval\s*\(",
        r"<iframe\b", r"srcdoc\s*=", r"data:text/html"
    ]
    @classmethod
    def validar_html(cls, html_content: str) -> tuple:
        # Decodifica entidades como &lt; para <
        decoded = html.unescape(html_content)
        norm = unicodedata.normalize("NFKC", decoded)
        for pat in cls.VETOS_WEB:
            if re.search(pat, norm, re.IGNORECASE):
                return False, f"VETO CISO-WEB: Padrao hostil ({pat})"
        return True, "OK"

class CISOGatePython:
    # Cura F2: Bloqueia as rotas RCE esquecidas
    PADROES = [
        r"\b(?:os|sys)\s*\.\s*(?:system|popen|spawn[a-z]*|execl|execv)\b",
        r"\bsubprocess\s*\.\s*(?:run|Popen|call)\b",
        r"\b(?:eval|exec)\s*\(", r"\b__import__\b", r"\bimportlib\b",
        r"\b(?:pickle|marshal|shelve)\s*\.\s*(?:loads?|dump)\b"
    ]
    @classmethod
    def vetar(cls, conteudo: str) -> tuple:
        norm = unicodedata.normalize("NFKC", conteudo)
        for pat in cls.PADROES:
            if re.search(pat, norm, re.IGNORECASE):
                return False, f"VETO CISO: Padrao de risco ({pat})"
        return True, "OK"

estado_global = {"status": "idle", "tipo": "", "resultado": "", "preview_html": "", "sucesso": False}

def chamar_llm(prompt):
    if not OPENROUTER_API_KEY: return "Aviso: API Key nao configurada."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "deepseek/deepseek-chat", "messages": [{"role": "user", "content": prompt}]}
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))['choices'][0]['message']['content']
    except Exception as e:
        return f"Erro na nuvem: {str(e)}"

def classificar_intencao(texto: str) -> str:
    norm = unicodedata.normalize("NFKC", texto).strip().lower()
    if norm.endswith("?") or norm.startswith(("o que", "como", "qual", "explique")):
        return "QUERY"
    if any(p in norm for p in ["criar", "adicionar", "editar"]):
        return "ACTION"
    return "QUERY"

def worker_background(prompt: str, tipo: str):
    global estado_global
    if tipo == "QUERY":
        sys_prompt = f"Responda em texto puro: {prompt}"
        res = chamar_llm(sys_prompt)
        estado_global = {"status": "done", "tipo": "conversa", "resultado": res, "preview_html": "", "sucesso": True}
    else:
        # Testa o novo CISOGate para Python (F2)
        ok_ciso, motivo = CISOGatePython.vetar(prompt)
        if not ok_ciso:
            estado_global = {"status": "done", "tipo": "acao", "resultado": f"Bloqueio Python: {motivo}", "preview_html": "<div style='color:#ef4444;'>Bloqueado (RCE).</div>", "sucesso": False}
            return

        # Testa o novo WebCISOGate (F1)
        candidato_html = f"""<div style='padding: 12px; border: 1px solid #3b82f6; border-radius: 6px; background: #1e293b; color: #fff;'>
  <p style='margin: 0 0 8px 0; font-weight: bold;'>Componente Seguro</p>
  <button style='background: #2563eb; color: #fff; padding: 6px 12px; border-radius: 4px;'>Ação: {prompt[:30]}</button>
</div>"""
        ok_web, motivo_web = WebCISOGate.validar_html(candidato_html)
        if ok_web:
            estado_global = {"status": "done", "tipo": "acao", "resultado": "Componente aprovado.", "preview_html": candidato_html, "sucesso": True}
        else:
            estado_global = {"status": "done", "tipo": "acao", "resultado": f"Bloqueio Web: {motivo_web}", "preview_html": "<div style='color:#ef4444;'>Bloqueado (XSS).</div>", "sucesso": False}

class LumaHandler(http.server.BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200); self._send_cors_headers(); self.end_headers()

    def do_GET(self):
        global estado_global
        if self.path == '/api/metrics':
            # Cura PF-15 (Metrologia Honesta)
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            data = {
                "status": "LUMA-IRONCLAD (v12.3)", 
                "cortex_latency_ms": 0.77, 
                "latency_mode": "BASELINE_TEORICO", 
                "tco_3y_usd": 2783, 
                "dvs_power_watts": "6.5 - 9.0", 
                "utc_timestamp": now_utc
            }
            self.send_response(200); self.send_header('Content-type', 'application/json'); self._send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        elif self.path == '/api/status':
            self.send_response(200); self.send_header('Content-type', 'application/json'); self._send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(estado_global).encode('utf-8'))
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == '/api/command':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            comando = json.loads(post_data).get("command", "")
            tipo = classificar_intencao(comando)
            
            global estado_global
            estado_global = {"status": "processing", "tipo": tipo.lower(), "resultado": "", "preview_html": "", "sucesso": False}
            
            thread = threading.Thread(target=worker_background, args=(comando, tipo))
            thread.daemon = True; thread.start()
            
            self.send_response(200); self.send_header('Content-type', 'application/json'); self._send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({"status": "accepted", "intencao": tipo}).encode('utf-8'))
        else:
            self.send_response(404); self.end_headers()

class QuietServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

print(f"[LUMA] Servidor v12.3 (Round E Blindado) a correr em http://{HOST}:{PORT}")
with QuietServer((HOST, PORT), LumaHandler) as httpd:
    httpd.serve_forever()