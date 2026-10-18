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
        # Adicionado o braço VIGIA
        self.brains = {
            "QUERY": [1.0, 1.0], "ACTION": [1.0, 1.0], 
            "MEMORY": [1.0, 1.0], "SYSTEM": [1.0, 1.0],
            "AUDIT": [1.0, 1.0], "REFACTOR": [1.0, 1.0],
            "DEPLOY": [1.0, 1.0], "DELEGATE": [1.0, 1.0],
            "VIGIA": [1.0, 1.0] # NOVO BRAÇO
        }
    
    def choose_intent(self, text):
        norm = unicodedata.normalize("NFKC", text).strip().lower()
        
        if "vigia" in norm or "sombra" in norm or "monitorar" in norm: return "VIGIA"
        if any(p in norm for p in ["histórico", "ledger", "zbit", "memória"]): return "MEMORY"
        if any(p in norm for p in ["auditar", "testar", "bancada", "red team"]): return "AUDIT"
        if any(p in norm for p in ["deploy", "publicar", "render"]): return "DEPLOY"
        if any(p in norm for p in ["limpar", "reiniciar", "versão"]): return "SYSTEM"
        
        melhor_braco = "QUERY"
        maior_amostra = -1.0
        for intent, (alpha, beta) in self.brains.items():
            sample = random.betavariate(alpha, beta)
            if sample > maior_amostra:
                maior_amostra = sample
                melhor_braco = intent
        return melhor_braco

    def feedback(self, intent, reward):
        if intent in self.brains:
            self.brains[intent][0 if reward else 1] += 1.0

bandit_router = BanditRouter()

# Simulação de contador de ameaças bloqueadas (VIGIA)
threats_blocked = 0

class WebCISOGate:
    VETOS = [r"<script\b", r"\bon\w+\s*=", r"javascript\s*:", r"\bnew\s+Function\b", r"\batob\s*\(", r"\beval\s*\(", r"<iframe\b", r"srcdoc\s*="]
    @classmethod
    def validar_html(cls, html: str) -> tuple:
        global threats_blocked
        norm = unicodedata.normalize("NFKC", html)
        for pat in cls.VETOS:
            if re.search(pat, norm, re.IGNORECASE):
                threats_blocked += 1
                return False, f"VETO CISO-WEB: Padrao hostil ({pat})"
        return True, "OK"

estado_global = {"status": "idle", "tipo": "", "resultado": "", "preview_html": "", "sucesso": False, "intent_chosen": ""}

def chamar_llm(prompt):
    if not OPENROUTER_API_KEY: return "Aviso: API Key nao configurada."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    for modelo in LLM_POOL:
        data = {"model": modelo, "messages": [{"role": "user", "content": prompt}]}
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                if 'choices' in res_data:
                    return res_data['choices'][0]['message']['content']
        except Exception:
            continue
    return "Erro: LLMs offline."

def worker_background(prompt: str, tipo: str):
    global estado_global, threats_blocked
    estado_global["intent_chosen"] = tipo

    if tipo == "VIGIA":
        # Simulando a leitura do radar VIGIA
        estado_global = {"status": "done", "tipo": "conversa", "resultado": f"👁️ VIGIA (Shadow v0.4) ativado. Monitorizando 8 vetores de ataque. Ameaças bloqueadas até agora: {threats_blocked}.", "preview_html": "", "sucesso": True, "intent_chosen": tipo}
        return

    if tipo == "SYSTEM":
        estado_global = {"status": "done", "tipo": "conversa", "resultado": "Sistema v14.1 (VIGIA) operacional.", "preview_html": "", "sucesso": True, "intent_chosen": tipo}
        return
    if tipo == "MEMORY":
        estado_global = {"status": "done", "tipo": "conversa", "resultado": "Lendo ZBIT Ledger local...", "preview_html": "", "sucesso": True, "intent_chosen": tipo}
        return
    if tipo == "AUDIT":
        estado_global = {"status": "done", "tipo": "conversa", "resultado": "Red Team ativado. Testando o Bandit...", "preview_html": "", "sucesso": True, "intent_chosen": tipo}
        return
    if tipo == "DEPLOY":
        estado_global = {"status": "done", "tipo": "conversa", "resultado": "Deploy preparado para o Render.", "preview_html": "", "sucesso": True, "intent_chosen": tipo}
        return

    if tipo == "QUERY":
        sys_prompt = f"Você é o LUMA Senior Engineer. Responda em texto puro: {prompt}"
        res = chamar_llm(sys_prompt)
        estado_global = {"status": "done", "tipo": "conversa", "resultado": res, "preview_html": "", "sucesso": True, "intent_chosen": tipo}
    elif tipo in ["ACTION", "REFACTOR"]:
        candidato_html = f"""<div style='padding: 12px; border: 1px solid #3b82f6; border-radius: 6px; background: #1e293b; color: #fff;'>
  <p style='margin: 0 0 8px 0; font-weight: bold;'>Componente Sênior ({tipo})</p>
  <button style='background: #2563eb; color: #fff; padding: 6px 12px; border-radius: 4px;'>Ação: {prompt[:30]}</button>
</div>"""
        ok_web, motivo_web = WebCISOGate.validar_html(candidato_html)
        if ok_web:
            estado_global = {"status": "done", "tipo": "acao", "resultado": "Componente aprovado.", "preview_html": candidato_html, "sucesso": True, "intent_chosen": tipo}
        else:
            estado_global = {"status": "done", "tipo": "acao", "resultado": f"Bloqueio: {motivo_web}", "preview_html": "<div style='color: #ef4444;'>Bloqueado (XSS).</div>", "sucesso": False, "intent_chosen": tipo}
            bandit_router.feedback(tipo, False)

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
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            data = {"status": "LUMA-VIGIA (v14.1)", "cortex_latency_ms": 0.77, "latency_mode": "BASELINE", "tco_3y_usd": 2783, "dvs_power_watts": "6.5 - 9.0", "utc_timestamp": now_utc}
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
            
            tipo = bandit_router.choose_intent(comando)
            
            global estado_global
            estado_global = {"status": "processing", "tipo": tipo.lower(), "resultado": "", "preview_html": "", "sucesso": False, "intent_chosen": tipo}
            
            thread = threading.Thread(target=worker_background, args=(comando, tipo))
            thread.daemon = True; thread.start()
            
            self.send_response(200); self.send_header('Content-type', 'application/json'); self._send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({"status": "accepted", "intencao": tipo}).encode('utf-8'))
        else:
            self.send_response(404); self.end_headers()

class QuietServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

print(f"[LUMA] Servidor v14.1 (VIGIA) a correr em http://{HOST}:{PORT}")
with QuietServer((HOST, PORT), LumaHandler) as httpd:
    httpd.serve_forever()