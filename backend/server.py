"""Local-only demo HTTP server with simple password-based session.

DO NOT expose to the internet. The local sign-in is a hackathon demonstration,
not enterprise security or an attestation of FZ-152 compliance.
"""
from __future__ import annotations
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
import json, os, secrets, time, hmac, hashlib, mimetypes
from .engine import simulate, compare
from .model import validate, ModelError

ROOT=Path(__file__).resolve().parent.parent
FRONT=ROOT/'frontend'; DATA=ROOT/'data'
PASSWORD=os.environ.get('PROCESSLAB_PASSWORD','demo2026')
SESSIONS={}
LOGIN_ATTEMPTS={}
MAX_BYTES=1024*1024
FILES={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/styles.css':'styles.css'}
DIAGRAMS={'/diagrams/as_is_kpsc.svg':'as_is_kpsc.svg','/diagrams/to_be_hypothesis.svg':'to_be_hypothesis.svg'}

class Handler(BaseHTTPRequestHandler):
    server_version='ProcessLab/4.1'
    def log_message(self,format,*args):
        print('[%s] %s'%(self.log_date_time_string(),format%args))
    def response(self,status,payload):
        raw=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers();self.wfile.write(raw)
    def cookie(self):
        for chunk in self.headers.get('Cookie','').split(';'):
            if chunk.strip().startswith('processlab_session='):
                return chunk.strip().split('=',1)[1]
        return None
    def authorized(self):
        key=self.cookie()
        if not key:return False
        valid=SESSIONS.get(key)
        if valid is None or valid<time.monotonic():
            SESSIONS.pop(key,None);return False
        return True
    def parse_json(self):
        typ=self.headers.get('Content-Type','').split(';')[0].strip()
        if typ!='application/json':raise ModelError('Требуется Content-Type: application/json')
        try: length=int(self.headers.get('Content-Length','-1'))
        except ValueError:raise ModelError('Некорректная длина запроса')
        if not 0<length<=MAX_BYTES:raise ModelError('Размер JSON должен быть от 1 байта до 1 МБ')
        try: return json.loads(self.rfile.read(length))
        except (UnicodeDecodeError,json.JSONDecodeError):raise ModelError('Некорректный JSON')
    def do_GET(self):
        route=urlsplit(self.path).path
        if route=='/api/v1/health':return self.response(200,{'status':'ok','version':'4.1','scope':'local_demo'})
        if route=='/api/v1/session':return self.response(200,{'authenticated':self.authorized(), 'mode':'local_demo'})
        if route=='/api/v1/demo':
            if not self.authorized():return self.response(401,{'error':'unauthorized'})
            return self.response(200,json.loads((DATA/'venio_factory.json').read_text('utf-8')))
        if route=='/api/v1/generic':
            if not self.authorized():return self.response(401,{'error':'unauthorized'})
            return self.response(200,json.loads((DATA/'generic_example.json').read_text('utf-8')))
        if route in DIAGRAMS:
            raw=(ROOT/'diagrams'/DIAGRAMS[route]).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type','image/svg+xml; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw);return
        name=FILES.get(route)
        if not name:return self.response(404,{'error':'not_found'})
        raw=(FRONT/name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type',{'index.html':'text/html; charset=utf-8','app.js':'application/javascript; charset=utf-8','styles.css':'text/css; charset=utf-8'}[name])
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        route=urlsplit(self.path).path
        if route=='/api/v1/login':
            try:body=self.parse_json()
            except ModelError as exc:return self.response(400,{'error':'invalid_input','message':str(exc)})
            ip=self.client_address[0];now=time.monotonic()
            attempts=[x for x in LOGIN_ATTEMPTS.get(ip,[]) if now-x<60]
            if len(attempts)>=8:return self.response(429,{'error':'too_many_attempts','message':'Повторите позже'})
            if not isinstance(body,dict) or not isinstance(body.get('password'),str) or not hmac.compare_digest(body['password'],PASSWORD):
                attempts.append(now);LOGIN_ATTEMPTS[ip]=attempts
                return self.response(401,{'error':'wrong_password','message':'Неверный пароль'})
            token=secrets.token_urlsafe(32);SESSIONS[token]=now+3600
            LOGIN_ATTEMPTS.pop(ip,None)
            raw=b'{"authenticated":true}'
            self.send_response(200)
            self.send_header('Set-Cookie',f'processlab_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600')
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw)
            return
        if not self.authorized():return self.response(401,{'error':'unauthorized','message':'Сначала войдите'})
        if route=='/api/v1/logout':
            SESSIONS.pop(self.cookie(),None)
            raw=b'{"authenticated":false}'
            self.send_response(200)
            self.send_header('Set-Cookie','processlab_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw);return
        if route not in ('/api/v1/validate','/api/v1/simulate','/api/v1/compare'):
            return self.response(404,{'error':'not_found'})
        try:
            body=self.parse_json()
            if route=='/api/v1/compare':
                result=compare(body['baseline'],body['scenario'])
            elif route=='/api/v1/validate':
                g=validate(body);result={'valid':True,'nodes':len(g['nodes']),'edges':len(g['edges'])}
            else:result=simulate(body)
            self.response(200,result)
        except (ModelError,KeyError,TypeError,ValueError) as e:
            self.response(422,{'error':'invalid_model','message':str(e)})
        except Exception as e:
            self.log_error('Failure: %s',e)
            self.response(500,{'error':'internal_error','message':'Внутренняя ошибка симулятора'})

def main():
    import argparse
    p=argparse.ArgumentParser(description='PROCESS LAB — локальный сервер')
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8765)
    a=p.parse_args()
    if a.host not in ('127.0.0.1','localhost','::1'):
        p.error('Публичный хост запрещён: демонстрационная авторизация не предназначена для интернета')
    print('PROCESS LAB 4.1: http://%s:%d/'%(a.host,a.port))
    print('Пароль по умолчанию: demo2026 (переопределить PROCESSLAB_PASSWORD)')
    server=ThreadingHTTPServer((a.host,a.port),Handler)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
