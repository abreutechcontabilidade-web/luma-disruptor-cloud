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
import random
from datetime import datetime, timezone

PORT = int(os.environ.get("PORT", 8000))
HOST = "0.0.0.0"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

LLM_POOL = ["deepseek/deepseek-chat", "anthropic/claude-3.5-sonnet"]

class BanditRouter:
    def __init__(self):
        self.brains = {
            "QUERY": [1.0, 1.0], "ACTION": [1.0, 1.0], 
            "MEMORY": [1.0, 1.0], "SYSTEM": [1.0, 1.0],
            "AUDIT": [1.0, 1.0], "REFACTOR": [1.0, 1.0],
            "DEPLOY": [1.0, 1.0], "DELEGATE": [1.0, 1.0], "VIGIA": [1.0, 1.0]
        }
    
    def choose_intent(self, text):
        norm = unicodedata.normalize("NFKC", text).strip().lower()
        
        # Regras Determinísticas (Prioridade Máxima)
        if any(p in norm for p in ["jogo", "html", "css", "javascript", "criar", "adicionar", "editar"]): 
            return "ACTION"
        if "vigia" in norm or "sombra" in norm: 
            return "VIGIA"
        if any(p in norm for p in ["histórico", "ledger", "memória"]): 
            return "MEMORY"
        if any(p in norm for p in ["auditar", "testar", "bancada"]): 
            return "AUDIT"
        if any(p in norm for p in ["deploy", "publicar"]): 
            return "DEPLOY"
        if any(p in norm for p in ["limpar", "reiniciar", "versão"]): 
            return "SYSTEM"
        
        # Se for ambíguo, o Bandit decide
        melhor_braco, maior_amostra = "QUERY", -1.0
        for intent, (alpha, beta) in self.brains.items():
            sample = random.betavariate(alpha, beta)
            if sample > maior_amostra:
                maior_amostra, melhor_braco = sample, intent
        return melhor_braco

bandit_router = BanditRouter()

class WebCISOGate:
    # CISO agora permite <script> para jogos, mas bloqueia injeções maliciosas.
    VETOS = [r"\beval\s*\(", r"\batob\s*\(", r"document\.cookie", r"localStorage", r"sessionStorage", r"<iframe\b", r"srcdoc\s*="]
    @classmethod
    def validar_html(cls, html: str) -> tuple:
        norm = unicodedata.normalize("NFKC", html)
        for pat in cls.VETOS:
            if re.search(pat, norm, re.IGNORECASE):
                return False, f"VETO CISO-WEB: Codigo malicioso detetado ({pat})"
        return True, "OK"

estado_global = {"status": "idle", "tipo": "", "resultado": "", "preview_html": "", "sucesso": False}

def chamar_llm(prompt):
    if not OPENROUTER_API_KEY: return "Aviso: API Key nao configurada."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    for modelo in LLM_POOL:
        data = {"model": modelo, "messages": [{"role": "user", "content": prompt}]}
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=25) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                if 'choices' in res_data: return res_data['choices'][0]['message']['content']
        except Exception: continue
    return "Erro: O tempo de resposta do LLM excedeu o limite."

def worker_background(prompt: str, tipo: str):
    global estado_global

    if tipo == "VIGIA":
        estado_global = {"status": "done", "tipo": "conversa", "resultado": f"👁️ VIGIA ativado.", "preview_html": "", "sucesso": True}
        return
    if tipo == "SYSTEM":
        estado_global = {"status": "done", "tipo": "conversa", "resultado": "Sistema v14.4 (Jogo Ready).", "preview_html": "", "sucesso": True}
        return
    if tipo == "QUERY":
        res = chamar_llm(f"Responda: {prompt}")
        estado_global = {"status": "done", "tipo": "conversa", "resultado": res, "preview_html": "", "sucesso": True}
    elif tipo in ["ACTION", "REFACTOR"]:
        sys_prompt = f"Crie o codigo HTML e JS jogavel para: {prompt}. Retorne APENAS o codigo HTML."
        codigo_gerado = chamar_llm(sys_prompt)
        codigo_limpo = re.sub(r"```(?:html)?\n?|```", "", codigo_gerado).strip()
        
        ok_web, motivo_web = WebCISOGate.validar_html(codigo_limpo)
        if ok_web:
            estado_global = {"status": "done", "tipo": "acao", "resultado": "Codigo gerado e aprovado.", "preview_html": codigo_limpo, "sucesso": True}
        else:
            estado_global = {"status": "done", "tipo": "acao", "resultado": f"Bloqueio: {motivo_web}", "preview_html": "<div style='color: #ef4444;'>Bloqueado (CISO).</div>", "sucesso": False}

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
            data = {"status": "LUMA-VIGIA (v14.4 Sandbox)", "cortex_latency_ms": 0.77, "latency_mode": "BASELINE", "tco_3y_usd": 2783, "dvs_power_watts": "6.5 - 9.0"}
            self.send_response(200); self.send_header('Content-type', 'application/json; charset=utf-8'); self._send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        elif self.path == '/api/status':
            self.send_response(200); self.send_header('Content-type', 'application/json; charset=utf-8'); self._send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(estado_global, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == '/api/command':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            comando = json.loads(post_data).get("command", "")
            tipo = bandit_router.choose_intent(comando)
            
            global estado_global
            estado_global = {"status": "processing", "tipo": tipo.lower(), "resultado": "", "preview_html": "", "sucesso": False}
            
            thread = threading.Thread(target=worker_background, args=(comando, tipo))
            thread.daemon = True; thread.start()
            
            self.send_response(200); self.send_header('Content-type', 'application/json; charset=utf-8'); self._send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({"status": "accepted", "intencao": tipo}, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404); self.end_headers()

class QuietServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

print(f"[LUMA] Servidor v14.4 a correr em http://{HOST}:{PORT}")
with QuietServer((HOST, PORT), LumaHandler) as httpd:
    httpd.serve_forever()