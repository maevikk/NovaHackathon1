"""PROCESS LAB integration diagnostics.

Default check needs only Python standard library:
    python3 tests/browser_smoke.py

Optional full browser check (only if Playwright and Chromium are installed):
    python3 tests/browser_smoke.py --browser
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def serve():
    sock=socket.socket();sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1];sock.close()
    proc=subprocess.Popen([sys.executable,'-m','backend.server','--port',str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    for _ in range(60):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health',timeout=.3)
            return proc,f'http://127.0.0.1:{port}/'
        except Exception:
            time.sleep(.1)
    proc.terminate();raise AssertionError('server did not start')


def run_browser():
    # Import dynamically so VS Code does not report an unresolved optional package.
    import importlib
    try:
        sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError("Не установлен необязательный Playwright. Для полной браузерной проверки: python3 -m pip install playwright && python3 -m playwright install chromium") from exc
    proc,url=serve()
    try:
        with sync_playwright() as pw:
            try:
                # Default Playwright Chromium location works on macOS, Windows and Linux.
                browser=pw.chromium.launch(headless=True)
            except Exception as first_error:
                # Fallback for a Linux test container with system Chromium.
                if sys.platform.startswith('linux') and Path('/usr/bin/chromium').exists():
                    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
                else:
                    raise RuntimeError('Браузер Chromium для Playwright не найден. Выполни: python3 -m playwright install chromium') from first_error
            # Chromium here forbids navigation to HTTP by policy. Load the
            # project's exact HTML/CSS/JS inline, but forward its API calls to
            # the real local Python server through an instrumented bridge.
            import http.cookiejar,urllib.error
            html=(ROOT/'frontend/index.html').read_text('utf-8')
            css=(ROOT/'frontend/styles.css').read_text('utf-8')
            js=(ROOT/'frontend/app.js').read_text('utf-8')
            html=html.replace('<link rel="stylesheet" href="/styles.css">','<style>'+css+'</style>')
            html=html.replace('<script src="/app.js" defer></script>', '<script>window.fetch=async (endpoint,options={})=>{const result=await window.__realBackend(endpoint,options);return {ok:result.status>=200&&result.status<300,status:result.status,json:async()=>JSON.parse(result.body)};};</script><script>'+js+'</script>' )
            def install_page(page):
                jar=http.cookiejar.CookieJar()
                opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
                def request_backend(source,endpoint,options):
                    payload=options.get('body')
                    headers={'Content-Type':'application/json'} if payload is not None else {}
                    req=urllib.request.Request(url+endpoint.lstrip('/'),data=payload.encode('utf-8') if payload is not None else None,headers=headers)
                    try:response=opener.open(req,timeout=10)
                    except urllib.error.HTTPError as exc:response=exc
                    status=response.status
                    api_replies.append((options.get('method','GET'),endpoint.rsplit('/',1)[-1],status))
                    return {'status':status,'body':response.read().decode('utf-8')}
                page.expose_binding('__realBackend',request_backend)
                page.set_content(html,wait_until='load')
            page=browser.new_page(viewport={'width':1440,'height':900},accept_downloads=True)
            page.set_default_timeout(10000)
            errors=[];failed=[];api_replies=[]
            page.on('pageerror',lambda e: errors.append(str(e)))
            page.on('console',lambda e: failed.append(e.text) if e.type=='error' else None)
            install_page(page)
            page.locator('#password').fill('demo2026');page.locator('#login-form button[type=submit]').click()
            page.locator('.sidebar').wait_for(timeout=20000)
            assert 'PROCESS LAB' in page.locator('.sidebar').inner_text()
            page.locator('[data-view="map"]').click()
            page.locator('#flow-space svg').wait_for()
            page.screenshot(path=str(ROOT/'docs/previews/kpsc_verified.png'),full_page=True)
            assert page.locator('#flow-space [data-node]').count()==12
            assert page.locator('.map-tools').count()==1
            # Drag only a visual position; no simulation request is needed.
            page.locator('#flow-space').evaluate('(e)=>e.scrollLeft=0')
            g=page.locator('#flow-space [data-node="o1"]')
            rect=g.bounding_box()
            assert rect, 'drag target not visible'
            src=(rect['x']+rect['width']/2,rect['y']+rect['height']/2)
            before=page.evaluate('JSON.stringify(state.model.edges)')
            page.mouse.move(*src);page.mouse.down();page.mouse.move(src[0]+70,src[1]+35,steps=8);page.mouse.up()
            layout=page.evaluate('state.model.kpsc_layout?.o1')
            assert layout and layout['x']>0, f'Drag did not save: {layout}'
            assert before==page.evaluate('JSON.stringify(state.model.edges)'),'drag changed graph topology'
            with page.expect_download(timeout=5000) as dl:
                page.locator('[data-action="export"]').click()
            downloaded=json.loads(Path(dl.value.path()).read_text('utf-8'))
            assert downloaded['kpsc_layout']['o1']==layout,'export lost drag positions'
            page.locator('[data-action="reset-layout"]').click()
            assert page.evaluate('state.model.kpsc_layout===undefined')
            # AS-IS is a read-only baseline; editing lives in the TO-BE scenario.
            page.locator('[data-action="goto-target"]').first.click()
            # Regression: v4.1 accidentally blocked dragging whenever AS-IS was not selected.
            target_group=page.locator('#flow-space [data-node="o8"]')
            target_group.scroll_into_view_if_needed()
            target_box=target_group.bounding_box()
            assert target_box, 'TO-BE node not rendered'
            tx,ty=target_box['x']+target_box['width']/2,target_box['y']+target_box['height']/2
            before_edges=page.evaluate('JSON.stringify(state.model.edges)')
            page.mouse.move(tx,ty);page.mouse.down();page.mouse.move(tx+54,ty+25,steps=8);page.mouse.up()
            moved_pos=page.evaluate('state.model.kpsc_layout?.o8')
            assert moved_pos and moved_pos['x']>0, 'TO-BE drag was blocked'
            assert before_edges==page.evaluate('JSON.stringify(state.model.edges)'), 'TO-BE drag modified topology'
            # Keyboard positioning on both stages must also work.
            page.locator('#flow-space [data-node="o8"]').focus()
            page.keyboard.press('ArrowRight')
            assert page.evaluate('state.model.kpsc_layout?.o8?.x')==moved_pos['x']+12
            with page.expect_download(timeout=5000) as dl:
                page.locator('[data-action="export"]').click()
            downloaded=json.loads(Path(dl.value.path()).read_text('utf-8'))
            assert downloaded['kpsc_layout']['o8']['x']==moved_pos['x']+12
            page.locator('#flow-space [data-node="o8"]').click()
            inp=page.locator('[data-node-field="cycle_s"][data-node-id="o8"]')
            inp.fill('125');inp.press('Tab')
            page.wait_for_function("state.model.nodes.find(n=>n.id==='o8').cycle_s===125 && state.result.potential_bottleneck.cycle_s===125",timeout=10000)
            assert ('POST','simulate',200) in api_replies
            assert ('POST','validate',200) in api_replies
            # The original AS-IS card remains unchanged after modifying TO-BE.
            page.locator('#stage-select').select_option('current')
            assert page.evaluate("state.baseline.nodes.find(n=>n.id==='o8').cycle_s")==171
            assert '171 с' in page.locator('#flow-space [data-node="o8"]').text_content()
            page.locator('#stage-select').select_option('target')
            assert '125 с' in page.locator('#flow-space [data-node="o8"]').text_content()
            # Reject invalid model through server; UI must not keep it.
            page.locator('[data-node-field="workers"][data-node-id="o8"]').fill('0')
            page.locator('[data-node-field="workers"][data-node-id="o8"]').press('Tab')
            assert page.evaluate("state.model.nodes.find(n=>n.id==='o8').workers") == 1
            page.locator('[data-view="scenarios"]').click()
            page.locator('[data-action="compare"]').click()
            page.wait_for_function('state.comparison!==null',timeout=10000)
            assert ('POST','compare',200) in api_replies
            # Capture base-factory metrics before swapping datasets.
            page.locator('[data-view="overview"]').click()
            page.screenshot(path=str(ROOT/'docs/previews/dashboard_factory_verified.png'),full_page=True)
            # Other model: no factory-specific labels should leak into generic dashboard.
            page.locator('[data-view="sources"]').click();page.locator('[data-action="generic"]').click()
            page.wait_for_function("state.model.status==='synthetic_demo'",timeout=10000)
            page.locator('[data-view="floor"]').click()
            assert 'пока не загружен' in page.locator('main').inner_text().lower()
            # ensure no 500/server crashes, and desktop visually valid
            page.locator('[data-view="overview"]').click()
            page.screenshot(path=str(ROOT/'docs/previews/dashboard_verified.png'),full_page=True)
            mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
            mobile.set_default_timeout(10000)
            mobile.on('pageerror',lambda e: errors.append('mobile:'+str(e)))
            install_page(mobile)
            mobile.locator('#password').fill('demo2026'); mobile.locator('#login-form button[type=submit]').click()
            mobile.locator('.sidebar').wait_for(timeout=20000)
            mobile.locator('[data-view="map"]').click()
            assert mobile.locator('#flow-space svg').count()==1
            # Touch regression on a narrow viewport (pointer capture survives SVG redraw).
            touch_node=mobile.locator('#flow-space [data-node="o1"]')
            touch_node.scroll_into_view_if_needed()
            bb=touch_node.bounding_box()
            assert bb, 'Touch node not visible'
            x,y=bb['x']+bb['width']/2,bb['y']+bb['height']/2
            cdp=mobile.context.new_cdp_session(mobile)
            cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y,'id':1}]})
            for i in range(1,7):
                cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+8*i,'y':y+3*i,'id':1}]})
            cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
            mobile.wait_for_function('Boolean(state.model.kpsc_layout?.o1)',timeout=3000)
            mobile.screenshot(path=str(ROOT/'docs/previews/map_mobile_verified.png'),full_page=True)
            assert not errors,errors
            assert not failed,failed
            assert not any(status>=500 for _,_,status in api_replies),api_replies
            print(json.dumps({'browser':'Chromium','result':'PASS','desktop_drag':True,'to_be_drag':True,'keyboard_layout':True,'backend_roundtrip':True,'compare':True,'generic':True,'mobile_touch_drag':True,'mobile':True,'api_calls':api_replies,'errors':errors},ensure_ascii=False,indent=2))
            mobile.close();browser.close()
    finally:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill()

def run_api_smoke():
    """Check that HTML, JS and CSS are served and share a working backend API.

    This is an HTTP integration smoke test, NOT a test of drag-and-drop.
    No Playwright, third-party packages, or system browser are required.
    """
    import http.cookiejar
    import urllib.error

    proc, base_url = serve()
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

    def get(path):
        with client.open(base_url + path.lstrip('/'), timeout=8) as response:
            return response.read().decode('utf-8'), response.status

    def request(path, body):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            base_url + 'api/v1/' + path,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with client.open(req, timeout=8) as response:
            return json.load(response), response.status

    try:
        html, status = get('/')
        assert status == 200 and '/app.js' in html and '/styles.css' in html, 'HTML не подключает JS и CSS'
        js, status = get('/app.js')
        assert status == 200 and "async function api(" in js and "fetch('/api/v1/'" in js, 'JS не подключает API'
        css, status = get('/styles.css')
        assert status == 200 and len(css) > 500, 'CSS не загружается'
        unauth, status = get('api/v1/session')
        assert json.loads(unauth)['authenticated'] is False, 'Некорректный стартовый сеанс'
        login, status = request('login', {'password':'demo2026'})
        assert status == 200 and login['authenticated'], 'Не удалось войти'
        auth, status = get('api/v1/session')
        assert json.loads(auth)['authenticated'], 'Cookie сессии не работает'
        demo, status = get('api/v1/demo')
        model = json.loads(demo)
        assert status == 200 and len(model['nodes']) >= 10, 'Сервер не отдал модель'
        validated, status = request('validate', model)
        assert status == 200 and validated['valid'], 'Валидация не работает'
        simulated, status = request('simulate', model)
        assert status == 200 and isinstance(simulated['accepted'], int), 'Движок моделирования не ответил'
        comparison, status = request('compare', {'baseline':model,'scenario':model})
        assert status == 200 and isinstance(comparison, dict), 'Сравнение сценариев не работает'
        generic, status = get('api/v1/generic')
        assert status == 200 and isinstance(json.loads(generic)['nodes'], list), 'Пример другой фабрики недоступен'
        print('PASS: HTML + JS + CSS + login + session + модель + validate + simulate + compare + импорт другого процесса')
        print('Frontend ↔ backend: HTTP-интеграция работает. Проверку перетаскивания выполняй в браузере либо с --browser.')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='PROCESS LAB: проверка соединения frontend/backend')
    parser.add_argument('--browser', action='store_true', help='Дополнительная проверка интерфейса в Chromium через Playwright')
    options = parser.parse_args()
    try:
        if options.browser:
            run_browser()
        else:
            run_api_smoke()
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)

