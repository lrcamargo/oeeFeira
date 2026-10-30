from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError,URLError
import sqlite3,json,datetime,os,ipaddress,re,base64
BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'wise_oee.sqlite3')
def connect():
 c=sqlite3.connect(DB); c.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, stamp TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL)'); c.commit();return c
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=BASE,**k)
 def output(self,code,data):
  b=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  url=urlsplit(self.path);q=parse_qs(url.query)
  if url.path=='/api/wise':
   return self.output(405,{'error':'Atualize a página: a leitura agora utiliza POST.'})
  if url.path=='/api/events':
   with connect() as c: rows=c.execute('SELECT id,stamp,kind,detail FROM events ORDER BY id DESC LIMIT 2000').fetchall()
   return self.output(200,{'events':[dict(zip(['id','stamp','kind','detail'],r)) for r in rows]})
  return super().do_GET()
 def do_POST(self):
  if self.path=='/api/wise':
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<=0 or n>2048:raise ValueError('Requisição inválida')
    val=json.loads(self.rfile.read(n))
    host=str(val.get('ip','')).strip()
    ip=ipaddress.ip_address(host)
    if ip.version!=4 or not ip.is_private:raise ValueError('Digite somente o IPv4 local, por exemplo: 192.168.1.100')
    port=int(val.get('port',80))
    if not 1<=port<=65535:raise ValueError('Porta HTTP inválida')
    username=str(val.get('username',''))
    password=str(val.get('password',''))
    headers={'Accept':'application/json','User-Agent':'WISE-OEE/2.0'}
    if username:
     token=base64.b64encode((username+':'+password).encode('utf-8')).decode('ascii')
     headers['Authorization']='Basic '+token
    target=f'http://{ip}:{port}/di_value/slot_0'
    req=Request(target,headers=headers,method='GET')
    # Evita o uso involuntário de proxies HTTP configurados no Windows.
    opener=build_opener(ProxyHandler({}))
    try:
     with opener.open(req,timeout=5) as resp:
      body=resp.read(100000).decode('utf-8-sig',errors='replace')
    except HTTPError as e:
     preview=e.read(300).decode('utf-8',errors='replace').strip()
     hint={400:'O equipamento rejeitou o pedido. Verifique usuário/senha, API REST habilitada e porta HTTP.',401:'Autenticação exigida ou usuário/senha incorretos.',403:'Acesso negado pelo WISE.',404:'Endpoint REST não encontrado neste firmware.'}.get(e.code,'Resposta HTTP recusada pelo equipamento.')
     return self.output(502,{'error':f'WISE respondeu HTTP {e.code}. {hint}'+(f' Detalhe: {preview[:160]}' if preview else '')})
    try: data=json.loads(body)
    except ValueError:return self.output(502,{'error':'O WISE respondeu, mas não enviou JSON. Pode ser uma página de login. Início: '+body[:130]})
    if not isinstance(data,dict) or not isinstance(data.get('DIVal'),list):
     return self.output(502,{'error':'Resposta recebida sem DIVal: '+str(data)[:180]})
    return self.output(200,data)
   except Exception as e:return self.output(502,{'error':type(e).__name__+': '+str(e)})
  if self.path!='/api/events':return self.output(404,{'error':'Rota não encontrada'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<=0 or n>100000:raise ValueError('Tamanho inválido')
   val=json.loads(self.rfile.read(n));kind=str(val.get('kind',''))[:40];detail=str(val.get('detail',''))[:500]
   if not re.fullmatch(r'[a-z_]+',kind):raise ValueError('Tipo inválido')
   stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
   with connect() as c:c.execute('INSERT INTO events (stamp,kind,detail) VALUES (?,?,?)',(stamp,kind,detail))
   return self.output(200,{'ok':True,'stamp':stamp})
  except Exception as e:return self.output(400,{'error':str(e)})
if __name__=='__main__':
 connect().close();print('Abra http://localhost:8765 no navegador');ThreadingHTTPServer(('0.0.0.0',8765),Handler).serve_forever()
