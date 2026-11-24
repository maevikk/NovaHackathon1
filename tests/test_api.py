from __future__ import annotations
import json, subprocess, sys, socket, time, http.cookiejar, unittest, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).parents[1]
class ApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  sock=socket.socket();sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1];sock.close()
  cls.proc=subprocess.Popen([sys.executable,'-m','backend.server','--port',str(cls.port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cls.url=f'http://127.0.0.1:{cls.port}/api/v1/'
  cls.jar=http.cookiejar.CookieJar();cls.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cls.jar))
  for i in range(30):
   try:urllib.request.urlopen(cls.url+'health',timeout=.5);break
   except Exception:time.sleep(.1)
  else:raise AssertionError('Server did not start')
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate();cls.proc.wait(timeout=5)
 def request_json(self,route,body=None):
  url=self.url+route
  headers={'Content-Type':'application/json'} if body is not None else {}
  req=urllib.request.Request(url,json.dumps(body).encode('utf8') if body is not None else None,headers=headers)
  with self.client.open(req,timeout=3) as r:return r.status,json.load(r)
 def test_access_control_and_workflow(self):
  # This test runs with initial no-cookie and then login, model, result.
  with self.assertRaises(urllib.error.HTTPError) as cm:self.request_json('demo')
  self.assertEqual(cm.exception.code,401)
  with self.assertRaises(urllib.error.HTTPError) as cm:self.request_json('login',{'password':'invalid'})
  self.assertEqual(cm.exception.code,401)
  _,response=self.request_json('login',{'password':'demo2026'})
  self.assertTrue(response['authenticated'])
  _,model=self.request_json('demo')
  _,valid=self.request_json('validate',model)
  self.assertTrue(valid['valid'])
  _,result=self.request_json('simulate',model)
  self.assertEqual(result['potential_bottleneck']['id'],'o8')
  m2=json.loads(json.dumps(model));next(n for n in m2['nodes'] if n['id']=='o8')['cycle_s']=120
  _,comparison=self.request_json('compare',{'baseline':model,'scenario':m2})
  self.assertIn('delta',comparison)
  bad=json.loads(json.dumps(model));bad['nodes'][1]['cycle_s']=-5
  with self.assertRaises(urllib.error.HTTPError) as cm:self.request_json('simulate',bad)
  self.assertEqual(cm.exception.code,422)
  self.request_json('logout',{})
  with self.assertRaises(urllib.error.HTTPError) as cm:self.request_json('generic')
  self.assertEqual(cm.exception.code,401)
if __name__=='__main__':unittest.main()
