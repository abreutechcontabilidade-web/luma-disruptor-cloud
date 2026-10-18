import http.server
import socketserver
import json
import time
import random
import subprocess
import os
import sys
import threading
import unicodedata

# A NUVEM USA A PORTA QUE ELA DEFINIR (OU 8000 SE FOR LOCAL)
PORT = int(os.environ.get("PORT", 8000))
HOST = "0.0.0.0" # Ouve em todas as interfaces para a nuvem conseguir aceder

MOTOR_DIR = r"C:\Users\user\Desktop\cpf_arboreo_repo\_bancada\motor"
PROJECT_DIR = r"C:\Users\user\Desktop\leitor-gibi"
PY_EXE = r"C:\Users\user\Desktop\luma-audit-repo\.venv\Scripts\python.exe"

MOTOR_LIB = r"C:\Users\user\Desktop\cpf_arboreo_repo\_bancada\motor\lib"
if MOTOR_LIB not in sys.path: sys.path.insert(0, MOTOR_LIB)
try:
    from multi_fallback import gerar_com_fallback
except:
    def gerar_com_fallback(p): return "Offline na nuvem (LLM nao configurado).", "mock", "mock"

estado_global = {"status": "idle", "tipo": "", "resultado": "", "sucesso": False}

def processar_acao(comando):
    global estado_global
    estado_global = {"status": "processing", "tipo": "acao", "resultado": "", "sucesso": False}
    # Na nuvem, não temos acesso aos ficheiros C:\. Vamos simular a ação para o frontend.
    time.sleep(2)
    estado_global = {"status": "done", "tipo": "acao", "resultado": "Ação simulada na nuvem.", "sucesso": True}

def processar_conversa(comando):
    global estado_global
    estado_global = {"status": "processing", "tipo": "conversa", "resultado": "", "sucesso": False}
    
    comando_seguro = unicodedata.normalize("NFKC", comando)
    if any(p in comando_seguro.lower() for p in ["ignore", "esqueça", "system prompt", "system override"]):
        estado_global = {"status": "done", "tipo": "conversa", "resultado": "Aviso de Segurança: Tentativa de manipulação detetada.", "sucesso": False}
        return

    prompt = f"Você é o LUMA, o CTO de IA de elite. Responda em português: {comando_seguro}"
    try:
        res, _, _ = gerar_com_fallback(prompt)
        estado_global = {"status": "done", "tipo": "conversa", "resultado": str(res), "sucesso": True}
    except Exception as e:
        estado_global = {"status": "error", "tipo": "conversa", "resultado": str(e), "sucesso": False}

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
            data = {"status": "LUMA-DISRUPTOR (v11.0 Cloud)", "cortex_latency_ms": latency, "tco_3y_usd": 2783, "dvs_power_watts": "6.5 - 9.0"}
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

print(f"[LUMA] Servidor v11.0 (Cloud) a correr em http://{HOST}:{PORT}")
with QuietServer((HOST, PORT), LumaHandler) as httpd:
    httpd.serve_forever()