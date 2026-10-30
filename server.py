from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError,URLError
import sqlite3,json,datetime,os,ipaddress,re
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
   host=q.get('ip',[''])[0].strip();port=q.get('port',['80'])[0]
   try:
    ip=ipaddress.ip_address(host)
    if not ip.is_private:raise ValueError('Use um IP de rede privada')
    port=int(port)
    if port<1 or port>65535:raise ValueError('Porta inválida')
    req=Request(f'http://{ip}:{port}/di_value/slot_0',headers={'Accept':'application/json'})
    with urlopen(req,timeout=3) as resp:data=json.loads(resp.read(100000).decode('utf-8'))
    if not isinstance(data.get('DIVal'),list):raise ValueError('Resposta do WISE sem DIVal')
    return self.output(200,data)
   except Exception as e:return self.output(502,{'error':str(e)})
  if url.path=='/api/events':
   with connect() as c: rows=c.execute('SELECT id,stamp,kind,detail FROM events ORDER BY id DESC LIMIT 2000').fetchall()
   return self.output(200,{'events':[dict(zip(['id','stamp','kind','detail'],r)) for r in rows]})
  return super().do_GET()
 def do_POST(self):
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
