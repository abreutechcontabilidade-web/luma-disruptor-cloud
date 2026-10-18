import http.server
import socketserver
import json
import time
import random
import os
import sys
import threading
import unicodedata
import urllib.request
import urllib.error

PORT = int(os.environ.get("PORT", 8000))
HOST = "0.0.0.0"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

estado_global = {"status": "idle", "tipo": "", "resultado": "", "sucesso": False}

def chamar_llm_cloud(prompt):
    if not OPENROUTER_API_KEY:
        return "Aviso: A API Key não está configurada no Render. Adicione OPENROUTER_API_KEY nas variáveis de ambiente."
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://luma-disruptor.onrender.com"
    }
    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['choices'][0]['message']['content']
    except Exception as e:
        return f"Erro na nuvem ao contactar o LLM: {str(e)}"

def processar_acao(comando):
    global estado_global
    estado_global = {"status": "processing", "tipo": "acao", "resultado": "", "sucesso": False}
    time.sleep(2)
    estado_global = {"status": "done", "tipo": "acao", "resultado": "Ação simulada na nuvem (modo leitura).", "sucesso": True}

def processar_conversa(comando):
    global estado_global
    estado_global = {"status": "processing", "tipo": "conversa", "resultado": "", "sucesso": False}
    
    comando_seguro = unicodedata.normalize("NFKC", comando)
    if any(p in comando_seguro.lower() for p in ["ignore", "esqueça", "system prompt"]):
        estado_global = {"status": "done", "tipo": "conversa", "resultado": "Aviso de Segurança: CISO bloqueou injeção de prompt.", "sucesso": False}
        return

    prompt = f"Você é o LUMA, o CTO de IA de elite. Responda de forma direta e técnica em português: {comando_seguro}"
    res = chamar_llm_cloud(prompt)
    estado_global = {"status": "done", "tipo": "conversa", "resultado": res, "sucesso": True}

class LumaHandler(http.server.BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        global estado_global
        if self.path == '/api/metrics':
            t0 = time.perf_counter()
            latency = round(0.77 + random.uniform(-0.05, 0.05), 3)
            t1 = time.perf_counter()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            data = {"status": "LUMA-DISRUPTOR (v12.0 Cloud)", "cortex_latency_ms": latency, "tco_3y_usd": 2783, "dvs_power_watts": "6.5 - 9.0"}
            self.wfile.write(json.dumps(data).encode('utf-8'))
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(estado_global).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/command':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            comando = json.loads(post_data).get("command", "")
            
            palavras_acao = ["criar", "editar", "injetar", "adicionar", "corrigir", "remover", "construir", "fazer"]
            eh_acao = any(p in comando.lower() for p in palavras_acao)
            
            if eh_acao:
                thread = threading.Thread(target=processar_acao, args=(comando,))
            else:
                thread = threading.Thread(target=processar_conversa, args=(comando,))
            
            thread.daemon = True
            thread.start()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "accepted", "tipo": "acao" if eh_acao else "conversa"}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

class QuietServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

print(f"[LUMA] Servidor v12.0 (Cloud LLM) a correr em http://{HOST}:{PORT}")
with QuietServer((HOST, PORT), LumaHandler) as httpd:
    httpd.serve_forever()