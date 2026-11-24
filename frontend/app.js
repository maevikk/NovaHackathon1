'use strict';
const $=sel=>document.querySelector(sel);
const clone=v=>JSON.parse(JSON.stringify(v));
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(n,d=0)=>n===null||n===undefined?'—':Number(n).toLocaleString('ru-RU',{maximumFractionDigits:d});
const isVenio=m=>m?.id==='venio-c'&&m?.status==='illustrative_normative_scenario';
const short=n=>{if(n===null||n===undefined)return '—';return n>=60?`${num(n/60,1)} мин`:`${num(n,0)} с`;};
const TABS=[['overview','▦','Обзор'],['map','↣','КПСЦ / AS-IS'],['floor','▤','Планировка'],['parameters','≡','Параметры'],['scenarios','◫','Сценарии'],['finance','₽','Экономика'],['sources','◎','Источники'],['method','◈','Методика']];
const state={model:null,initial:null,baseline:null,result:null,comparison:null,view:'overview',selected:'o8',baselineResult:null,loading:false,dirty:false,showStage:'current',running:false};
let toastTimer;
function toast(msg){const el=$('#toast');el.textContent=msg;el.classList.add('open');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('open'),4000);}
async function api(endpoint,body){
 const options={credentials:'same-origin'};
 if(body!==undefined){options.method='POST';options.headers={'Content-Type':'application/json'};options.body=JSON.stringify(body);}
 const response=await fetch('/api/v1/'+endpoint,options);let data;
 try{data=await response.json();}catch{throw new Error('Ошибка ответа сервера');}
 if(!response.ok)throw new Error(data.message||data.error||`HTTP ${response.status}`);
 return data;
}
function btn(label,action,cls='',attrs=''){return `<button type="button" class="btn ${cls}" data-action="${action}" ${attrs}>${label}</button>`;}
function label(status){return isVenio(state.model)?'Нормативы + гипотезы':status==='synthetic_demo'?'Синтетический пример':'Пользовательская модель · проверка источников';}
function statusBadge(){return `<span class="badge red">◉ ${label(state.model.status)}</span>`;}
function header(eyebrow,title,sub,actions=''){return `<div class="hero"><div><div class="eyebrow">${eyebrow}</div><h1>${esc(title)}</h1><p class="desc">${sub}</p></div><div class="hero-actions">${actions}</div></div>`;}
function disclaimer(){const synthetic=!isVenio(state.model);return `<div class="disclaimer"><span style="font-size:18px">⚠</span><div><strong>Граница достоверности</strong>${synthetic?'Это не верифицированная модель фабрики VENIO-C. Для пользовательского/синтетического процесса источник циклов, маршрутов и ресурсов необходимо проверять отдельно. Демонстрационные показатели не являются фактом производства.':'Рабочие нормативы базовой фабрики взяты из стандартов; это не фактические замеры смены. Связи подсборок требуют подтверждения экспертами. Результаты ниже — сценарный расчёт при явно заданных допущениях.'}</div></div>`;}
function panel(title,subtitle,content,right=''){return `<section class="card"><div class="section-row"><div><h2 class="card-title">${title}</h2><p class="card-sub">${subtitle}</p></div>${right}</div>${content}</section>`;}
function renderLogin(error=''){
 $('#app').innerHTML=`<div class="login-bg"><main class="login-card"><div class="brand-mark"><svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.4"><path d="M3 18l6-7 4 4 8-10M15 5h6v6"/></svg></div><div class="eyebrow">ЦИФРОВОЙ ДВОЙНИК · ПРОЦЕССЫ</div><h1>PROCESS LAB</h1><p class="desc">Учебная производственная аналитика: КПСЦ, нормативы, сценарии и расчёт возможных ограничений потока.</p><form id="login-form"><div class="field"><label for="password">Пароль демонстрационного пользователя</label><input id="password" name="password" type="password" required autocomplete="current-password" placeholder="Введите пароль"></div>${error?`<p style="color:#bf5460;font-size:12px">${esc(error)}</p>`:''}<button class="btn primary" type="submit">Войти в проект →</button></form><div class="login-tip"><b>Локальный демо-доступ:</b> пароль по умолчанию <code>demo2026</code>. Его можно изменить при запуске сервера через <code>PROCESSLAB_PASSWORD</code>. Это учебная авторизация, не промышленный контур безопасности.</div></main></div>`;
 $('#login-form').addEventListener('submit',async e=>{e.preventDefault();try{await api('login',{password:$('#password').value});await init();}catch(err){renderLogin(err.message);}});
}
async function init(){
 try{
 const auth=await api('session');if(!auth.authenticated){renderLogin();return;}
 if(!state.model){state.initial=await api('demo');state.model=clone(state.initial);state.baseline=clone(state.initial);}
 await run(true);if(!state.baselineResult)state.baselineResult=clone(state.result);render();
 }catch(err){$('#app').innerHTML=`<div class="loading-screen">Не удалось открыть проект: ${esc(err.message)}<p>Для запуска: <code>python -m backend.server</code></p></div>`;}
}
function shell(){
 return `<aside class="sidebar"><div class="brand"><div class="brand-mark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M3 18l6-7 4 4 8-10M15 5h6v6"/></svg></div><div class="brand-label"><b>PROCESS LAB</b><small>DIGITAL TWIN STUDIO</small></div></div><div class="nav-caption">Рабочая область</div><nav aria-label="Разделы приложения">${TABS.map(([id,icon,title])=>`<button class="nav-item ${state.view===id?'active':''}" data-view="${id}"><span class="miniicon">${icon}</span><span class="nav-text">${title}</span></button>`).join('')}</nav><div class="nav-end"><p>PROCESS LAB · Версия 4.1<br>МУ ФЦК №17-2023<br>Демо, не промышленная система</p><button data-action="logout">↪ Выйти</button></div></aside><div class="shell"><header class="topbar"><div class="breadcrumb">Проекты / <strong>${esc(TABS.find(a=>a[0]===state.view)?.[2]||'Обзор')}</strong></div><div class="topbar-actions"><span class="topbar-status"><i class="status-dot"></i>Демо · локально</span>${btn('↓ <span class="hide-mobile">Экспорт JSON</span>','export','small')}${btn('↑ <span class="hide-mobile">Импорт</span>','import','small')}${btn('▶ <span class="hide-mobile">Рассчитать</span>','run','small primary')}</div></header><main class="main">${renderPage()}<p class="footer-note">PROCESS LAB · Сценарная модель, не измеренный цифровой двойник предприятия. Данные не отправляются во внешние сервисы. 3D-тур не реализован в рамках MVP направления A.</p></main></div>`;
}
function render(){if(!state.model)return;$('#app').innerHTML=shell();}
function renderPage(){switch(state.view){case 'map':return mapView();case 'floor':return floorView();case 'parameters':return parameterView();case 'scenarios':return scenarioView();case 'finance':return financeView();case 'sources':return sourcesView();case 'method':return methodView();default:return overviewView();}}
function metric(title,value,hint,cls='',percent=0){return `<div class="card metric ${cls}"><div class="label">${title}</div><div class="number">${value}</div><div class="hint">${hint}</div><div class="mini-trend"><i style="width:${Math.max(1,Math.min(100,percent))}%"></i></div></div>`;}
function operationRows(result){
 if(!result)return `<div class="empty">Нужен расчёт</div>`;
 const max=Math.max(...result.operations.map(o=>o.cycle_s),1);
 return `<div class="bars">${result.operations.map(o=>`<div class="bar-row ${o.risk_above_takt?'hot':''}" title="${esc(o.name)}"><span class="title">${esc(o.name)}</span><span class="bar-track"><span style="width:${(o.cycle_s/max*100).toFixed(1)}%"></span></span><span class="value">${num(o.cycle_s)} с</span></div>`).join('')}</div>`;
}
function overviewView(){
 const m=state.model,s=m.settings,r=state.result,b=r?.potential_bottleneck,synthetic=!isVenio(m);
 const opCount=m.nodes.filter(n=>n.kind==='operation').length, qcCount=m.nodes.filter(n=>n.kind==='quality').length;
 const actions=`${btn('↣ Карта потока','goto-map','')}${btn('◫ Проверить гипотезу','goto-scenarios','primary')}`;
 const accepted=r?.accepted??null;
 const bottleneckNote=synthetic?`<b>Что означает ${esc(b?.name||'ограничение')}</b><p>В синтетическом примере самая медленная операция — ${esc(b?.name||'не определена')} (${num(b?.cycle_s)} с/изд). Измените её параметры и сравните сценарии. Эти значения демонстрационные, а не измеренные.</p>`:`<b>Почему важно проверить операцию № 8</b><p>По рабочему стандарту установка шести болтов длится <b>171 с</b>, а заданный такт — <b>120 с</b>. При одном исполнителе нормативная производительность этой операции ниже требуемого темпа. Это обоснованный риск ограничения, а не зафиксированный фактический простой.</p>`;
 const evidence=synthetic?`<div class="source-row"><div class="source-id">≈</div><div><b>Учебный набор исходных данных</b><p>Все операции, маршруты и времена созданы специально для проверки расширяемости.</p></div><span class="badge red">Синтетика</span></div><div class="source-row"><div class="source-id">?</div><div><b>Фактические измерения</b><p>Источники измерений для этого предприятия не предоставлены.</p></div><span class="badge red">Нет данных</span></div>`:`<div class="source-row"><div class="source-id">✓</div><div><b>Нормативы операций</b><p>Стандарты выполнения операций, стр. 33–50</p></div><span class="badge green">Источник</span></div><div class="source-row"><div class="source-id">?</div><div><b>Фактические замеры</b><p>CT, ожидания, НЗП и логистический маршрут не предоставлены</p></div><span class="badge red">Уточнить</span></div><div class="source-row"><div class="source-id">≈</div><div><b>Маршрут подсборок</b><p>Технологическая гипотеза по рабочим стандартам</p></div><span class="badge red">Гипотеза</span></div>`;
 return `${header('ПРОИЗВОДСТВЕННАЯ АНАЛИТИКА',synthetic?'Универсальный конструктор потока':'Управляйте потоком, а не предположениями',`<b>${esc(m.product||m.name)}</b>. Изменяйте параметры и связи, чтобы проверить возможные ограничения процесса.`,actions)}
 ${disclaimer()}<div class="tablo">${statusBadge()}<span class="badge grey">${opCount} операций + ${qcCount} ОТК</span><span class="badge grey">Смена ${num(s.shift_s/60)} мин</span><span class="badge grey">Такт ${num(s.takt_s)} секунд</span></div>
 <section class="grid metrics">${metric('Принято заказчиком',num(accepted)+' / '+num(s.target_units),'Прогноз при принятых допущениях','primary-metric',100*(accepted??0)/s.target_units)}${metric('Потенциальное узкое место',b?num(b.cycle_s)+' с':'—',b?esc(b.name):'Нужно рассчитать','warn',b?100*b.cycle_s/(s.takt_s*2):0)}${metric('Теоретический путь',short(r?.theoretical_critical_path_s),'Без ожиданий и логистики — не фактический ВПП','',r?.theoretical_critical_path_s?50:0)}${metric('Расчётная выработка',num(r?.throughput_units_hour,1)+' шт/ч','Не фактический выпуск производства','',r?.throughput_units_hour?Math.min(100,r.throughput_units_hour/30*100):0)}</section>
 <div class="note" style="margin:12px 0 16px"><b>Откуда «${num(accepted)} из ${num(s.target_units)}»?</b> Это расчёт симулятора, а не измеренный выпуск фабрики. За ${num(s.shift_s/60,1)} мин прошли ОТК <b>${num(r?.finished)} шт.</b>, по графику приёмки клиент получил <b>${num(accepted)} шт.</b>, а <b>${num(Math.max(0,(r?.finished??0)-(accepted??0)))} шт.</b> ещё ожидали следующего момента приёмки. Остальные запущенные комплекты на конец расчёта не завершили ОТК или выбыли в условном сценарии. По умолчанию брак равен 0% только как допущение. Для проверки измените параметры на вкладке «Параметры» и сравните сценарии — это не фактический отчёт о выпуске.</div>
 <div class="grid cols"><div>${panel('Баланс операций',synthetic?'Все времена синтетические, а не нормативные':'Секунды на единицу по рабочим стандартам; красным — выше такта',operationRows(r),btn('Все параметры','goto-parameters','small'))}<div class="callout"><div class="icon">!</div><div>${bottleneckNote}</div></div></div><div>${panel('Как устроен расчёт','От источников до управленческого решения',`<ol class="list-clean">${['Изучить нормативы и фактические замеры','Зафиксировать материальный и информационный потоки','Заполнить недостающие параметры','Найти потенциальное ограничение','Сравнить AS-IS и TO-BE как сценарии'].map((x,i)=>`<li><span class="pill-step">${i+1}</span>${x}</li>`).join('')}</ol>`)}<div style="height:16px"></div>${panel('Статус данных','Не скрываем неизвестные показатели',evidence)}</div></div>`;
}
function graphGeometry(model,layoutOverride=null){
 const by=Object.fromEntries(model.nodes.map(n=>[n.id,n]));const incoming={};const outgoing={};model.nodes.forEach(n=>{incoming[n.id]=[];outgoing[n.id]=[];});
 model.edges.forEach(e=>{if(by[e.from]&&by[e.to]){incoming[e.to].push(e.from);outgoing[e.from].push(e.to);}});
 const indegree=Object.fromEntries(model.nodes.map(n=>[n.id,incoming[n.id].length]));let ready=model.nodes.filter(n=>!indegree[n.id]).map(n=>n.id),layers={},order=[];
 let attempts=0;
 while(ready.length&&attempts++<200){const n=ready.shift();order.push(n);layers[n]=Math.max(0,...incoming[n].map(x=>(layers[x]||0)+1));for(const to of outgoing[n]){indegree[to]--;if(indegree[to]===0)ready.push(to);}}
 model.nodes.forEach(n=>{if(layers[n.id]===undefined)layers[n.id]=0;});
 const groups={};model.nodes.forEach(n=>{const k=layers[n.id];(groups[k]||(groups[k]=[])).push(n);});
 const countMax=Math.max(...Object.values(groups).map(a=>a.length));const H=Math.max(560,countMax*125+105);const W=(Math.max(...Object.keys(groups).map(Number),1)+1)*208+130;
 const positions={};Object.keys(groups).sort((a,b)=>a-b).forEach(key=>{const group=groups[key];group.sort((a,b)=>a.id.localeCompare(b.id));group.forEach((node,i)=>{positions[node.id]={x:35+key*208,y:105+(H-160)*(i+.5)/group.length-40};});});
 // Keep spatial arrangement separate from technological dependencies.
 for(const [id,p] of Object.entries(layoutOverride||model.kpsc_layout||{})){
  if(positions[id]&&Number.isFinite(p.x)&&Number.isFinite(p.y))positions[id]={x:p.x,y:p.y};
 }
 const graphW=Math.max(W, ...Object.values(positions).map(p=>p.x+195));
 const graphH=Math.max(H, ...Object.values(positions).map(p=>p.y+120));
 return {by,positions,W:graphW,H:graphH,incoming};
}
function graphSvg(model=state.model){
 const g=graphGeometry(model,state.model.kpsc_layout||{}),{positions,by}=g;const s=model.settings;
 const svgLines=model.edges.map(e=>{let a=positions[e.from],b=positions[e.to];if(!a||!b)return '';
 const x=a.x+148,y=a.y+34,x2=b.x,y2=b.y+34;
 const supply=e.category==='supply';const assumed=e.verification==='requires_expert_confirmation';
 const bend=Math.max(50,(x2-x)/2);const d=`M${x},${y} C${x+bend},${y} ${x2-bend},${y2} ${x2},${y2}`;
 return `<path d="${d}" fill="none" stroke="${supply?'#a9b9cf':assumed?'#d6a65a':'#7584a5'}" stroke-width="${supply?'1.6':'2'}" marker-end="url(#arr)"><title>${esc(e.from+' → '+e.to+(assumed?' · требует подтверждения':''))}</title></path>`;
 }).join('');
 const maxH=g.H;
 const info=`<g><rect x="40" y="22" width="190" height="41" rx="8" fill="#edf8fc" stroke="#8cc0cf" stroke-dasharray="5 4"/><text x="135" y="47" text-anchor="middle" font-size="12" fill="#397c90" font-weight="700">План → задания</text><path d="M240,43 H${Math.min(g.W-80,1040)}" stroke="#61a4b8" stroke-width="1.5" stroke-dasharray="7 5" marker-end="url(#infoArr)"/><text x="${Math.min(g.W-250,600)}" y="32" font-size="10" fill="#679fac">Информационные сигналы / заявки логисту</text></g>`;
 const shapes=model.nodes.map(n=>{const p=positions[n.id];if(!p)return '';const typ=n.kind;
 const isStore=typ==='source',isCustomer=typ==='customer',isQC=typ==='quality';
 const rectFill=isQC?'#e5f8f0':isStore?'#f0f3f8':isCustomer?'#fff6e8':'#fff';const stroke=isQC?'#58ad89':isStore?'#8a9db8':isCustomer?'#d3ab6a':'#7e91b5';
 const display=n.name.replace(/^\d+\s*·\s*/,'');const words=display.split(' ');const lines=[];let line='';for(const w of words){if((line+' '+w).length>20){lines.push(line);line=w;}else line=(line+' '+w).trim();}if(line)lines.push(line);
 const safeLines=lines.slice(0,3);const cycle=n.cycle_s?`CTн: ${num(n.cycle_s)} с`:(isStore?'Снабжение':'Приёмка');
 return `<g data-node="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(n.name)}. Перетащите блок, чтобы изменить место на схеме, или используйте стрелки клавиатуры"><rect x="${p.x}" y="${p.y}" width="148" height="70" rx="9" fill="${rectFill}" stroke="${stroke}" stroke-width="${state.selected===n.id?3:1.6}"/><text x="${p.x+11}" y="${p.y+13}" fill="#8191a9" font-size="9" font-weight="800">${esc(n.id.toUpperCase())}</text>${safeLines.map((l,i)=>`<text x="${p.x+11}" y="${p.y+28+i*13}" font-size="10.4" fill="#263855" font-weight="600">${esc(l)}</text>`).join('')}<rect x="${p.x+4}" y="${p.y+74}" width="140" height="20" rx="5" fill="${n.cycle_s>s.takt_s?'#fff2e5':'#f0f4fa'}"/><text x="${p.x+74}" text-anchor="middle" y="${p.y+88}" fill="${n.cycle_s>s.takt_s?'#bf7545':'#72839d'}" font-size="10" font-weight="700">${esc(cycle)}</text></g>`;
 }).join('');
 return `<svg width="${g.W}" height="${maxH+30}" viewBox="0 0 ${g.W} ${maxH+30}" aria-label="Карта потока"><defs><marker id="arr" markerWidth="6" markerHeight="6" refX="5.5" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="#8493ae" stroke-width="1.3"/></marker><marker id="infoArr" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0L7 3L0 6" fill="none" stroke="#61a4b8" stroke-width="1.4"/></marker></defs>${info}${svgLines}${shapes}<text x="35" y="${maxH+16}" font-size="11" fill="#8b9bb0">${model.status==='synthetic_demo'?'Время: синтетика':'Время: нормативное'}. Оранжевые маршруты — гипотезы. НЗП/ожидания на карте не измерены.</text></svg>`;
}
function nodeInspector(model=state.model,readonly=false){
 const n=model.nodes.find(n=>n.id===state.selected)||model.nodes.find(x=>x.kind==='operation');if(!n)return '';
 const isOp=n.kind==='operation'||n.kind==='quality';
 return `${panel('Паспорт узла','Нажмите на операцию в карте для просмотра данных',`<div class="eyebrow">${esc(n.id)} · ${esc(n.kind)}</div><h2 style="margin-bottom:13px">${esc(n.name)}</h2>${isOp?`<div class="data-card"><h3>${num(n.cycle_s)} сек / единица</h3><p>${esc(n.evidence||'Источник не указан')}</p></div>${readonly?`<div class="note">Исходный базис только для просмотра. Для изменения времени, ресурсов и маршрутов перейдите в TO-BE.</div>`:`<hr class="divider"><div class="mini-form"><div class="field"><label>Время цикла, секунд</label><input type="number" min="1" step="1" data-node-field="cycle_s" data-node-id="${esc(n.id)}" value="${n.cycle_s}"><small>Изменение создаёт сценарий, не меняет первоисточник.</small></div><div class="field"><label>Число исполнителей</label><input type="number" min="1" max="16" step="1" data-node-field="workers" data-node-id="${esc(n.id)}" value="${n.workers}"></div></div>`}`:`<div class="note">Тип: ${esc(n.kind)}. Нормативное время здесь не задаётся.</div>`}<hr class="divider"><h3>Статус доказательств</h3><p class="desc">${n.cycle_basis==='work_standard_not_observed'?'Норматив из рабочего стандарта, факт хронометража не предоставлен.':'Операция или узел учебной модели.'}</p><div style="margin-top:18px">${readonly?btn('Перейти к TO-BE','goto-target','small soft'):btn('Изменить параметры','goto-parameters','small soft')}</div>`)}`;
}
function mapView(){
 const stage=state.showStage;
 const synthetic=!isVenio(state.model);
 const current=stage==='current',shown=current?state.baseline:state.model;
 const selector=`<select class="search-field" style="width:190px" id="stage-select"><option value="current" ${stage==='current'?'selected':''}>AS-IS · текущая</option><option value="ideal" ${stage==='ideal'?'selected':''}>IDEAL · идеальная</option><option value="target" ${stage==='target'?'selected':''}>TO-BE · целевая</option></select>`;
 if(stage==='ideal')return `${header('МУ-17-2023 · ИДЕАЛЬНЫЙ ПОТОК','Идеальное состояние ещё не рассчитано','Методика требует прогнозов, исходной КПСЦ, выявления потерь и обоснованных целевых KPI.',btn('Вопросы и источники','goto-sources','primary'))}${disclaimer()}${panel('IDEAL · обязательное методическое разграничение','Это не та же карта, что исходная КПСЦ',`<div class="section-row">${selector}</div><div class="empty">Полноценная идеальная карта пока не может быть достоверно составлена: нет фактических CT, НЗП, транспортировок и измеренного ВПП. Она должна быть построена после обследования, а не заполнена придуманными «идеальными» цифрами.</div><p class="desc" style="margin-top:18px">Промежуточный результат: отдельный документ <b>analysis/03_ideal_target_and_kpsc.md</b> фиксирует критерии идеального состояния и перечень недостающих измерений.</p>`)}`;
 return `${header('МУ-17-2023 · КАРТИРОВАНИЕ','Карта потока создания ценности',state.model.status==='synthetic_demo'?'Изображён синтетический маршрут. Вы можете добавить собственные операции и связи; это не карта обследованного предприятия.':'Разделяем материальные объекты и управление информацией. Технологические связи требуют экспертного подтверждения.',(current?btn('Перейти к TO-BE','goto-target','primary'):btn('＋ Добавить операцию','add-operation','')+btn('↳ Добавить связь','add-edge','')+btn('⊖ Удалить связь','remove-edge','')+btn('▶ Симуляция','run','primary')))}${disclaimer()}<div class="card"><div class="section-row"><div><h2 class="card-title">КПСЦ · ${stage==='current'?'AS-IS · исходная модель (базис)':stage==='ideal'?'идеальное состояние (концепция)':'TO-BE · редактируемая гипотеза'}</h2><p class="card-sub">Предмет: ${esc(shown.product||shown.name)}</p></div><select class="search-field" style="width:190px" id="stage-select"><option value="current" ${stage==='current'?'selected':''}>AS-IS · текущая</option><option value="ideal" ${stage==='ideal'?'selected':''}>IDEAL · идеальная</option><option value="target" ${stage==='target'?'selected':''}>TO-BE · целевая</option></select></div>${stage!=='current'?`<div class="note" style="margin-bottom:13px"><b>Статус: гипотеза, а не подтверждённая карта.</b> В МУ-17 идеальная и целевая карты требуют отдельных решений, проверки реализуемости и расчётов. Здесь показан вариант графа с текущими сценарными параметрами; окончательное картирование — после замеров и экспертного согласования.</div>`:''}<div class="info-strip"><strong>Информационный поток (не производственные зависимости)</strong><div class="info-chips">${(shown.info_flow||[]).map(f=>`<span>${esc(f.message)}</span>`).join('')||'<span>Не задан</span>'}</div></div><div class="map-tools"><span>Перетаскивайте блоки мышью или пальцем в AS-IS и TO-BE. Меняются только координаты. Чтобы сохранить раскладку после перезагрузки, используйте «Экспорт JSON» и затем «Импорт».</span>${btn('↺ Авторасположение','reset-layout','small')}</div><div class="workspace" id="flow-space">${graphSvg(shown)}</div><div class="legend"><span><i></i>Поток материальных объектов</span><span><i class="hyp"></i>Материальная связь: гипотеза (оранжевая сплошная)</span><span><i class="info"></i>Информационный поток</span><span>CTн — нормативное время цикла</span></div><p class="card-sub">${current?'На AS-IS показан неизменный исходный базис. Перестановка блоков на экране не меняет его.':'TO-BE отображает текущее состояние редактируемой сценарной модели; изменения сравнивайте с AS-IS во вкладке «Сценарии». '}НЗП, фактические транспортировки, простои и ВПП не нанесены количественно: замеры не предоставлены. На защите нельзя выдавать этот предварительный AS-IS за результаты обследования.</p></div><div style="height:16px"></div>${nodeInspector(shown,current)}`;
}
function floorView(){
 if(!isVenio(state.model))return `${header('ПЛАНИРОВКА / ДРУГОЕ ПРЕДПРИЯТИЕ','План пока не загружен','Фабрика VENIO-C не используется для этого синтетического процесса.',btn('Смотреть КПСЦ','goto-map','primary'))}${disclaimer()}${panel('Планировка другого предприятия','Привязка координат к узлам — отдельный источник данных',`<div class="empty">В этой модели нет подтверждённой планировки. Для построения диаграммы спагетти загрузите схему помещений и реальные перемещения логиста. Нельзя автоматически переносить расположение столов фабрики регулятора газа на другое предприятие.</div>`)}`;
 const positions={o9:[17,15],qc:[62,9],o2:[17,27],o7:[62,27],o4:[17,40],o5:[62,42],o3:[17,54],o1:[62,55],o6:[17,67],o8:[62,68]};
 const model=state.model;
 const items=model.nodes.filter(x=>positions[x.id]).map(n=>{let [left,top]=positions[n.id];return `<button class="table ${n.kind==='quality'?'quality':''}" data-select-node="${esc(n.id)}" style="left:${left}%;top:${top}%" title="${esc(n.name)}">${esc(n.id==='qc'?'ОТК':n.id.toUpperCase())}</button>`;}).join('');
 return `${header('МУ-17 · ПЛАНИРОВКА','План размещения рабочих мест','Вид сверху по схеме фабрики процессов. Это опорная схема для будущей диаграммы спагетти — не измеренная траектория логиста.',btn('Смотреть КПСЦ','goto-map','primary'))}${disclaimer()}<div class="card"><div class="section-row"><div><h2 class="card-title">Фабрика процессов · учебная площадка</h2><p class="card-sub">По файлу «6. Планировка Фабрики процессов» · 6,15 × 18,40 м</p></div><span class="badge grey">Масштаб схематичный</span></div><div class="floor-wrap"><div class="floor-plan"><div style="position:absolute;top:13px;left:0;right:0;text-align:center;font-size:11px;color:#7c89a3">6,15 м</div>${items}<div style="position:absolute;bottom:11px;left:0;right:0;text-align:center;font-size:11px;color:#9daabf">18,40 м · учебный зал</div></div><div class="floor-side"><h2>Что подтверждает план</h2><ul class="list-clean"><li>Размещение пронумерованных рабочих столов, контролёра и заказчика в учебном помещении.</li><li>Размеры стола: <b>100 × 70 см, высота 82 см</b>.</li><li>В первом раунде комплектующие между местами перемещает логист на тележке и в таре.</li><li>Маршрут логиста и длины конкретных перемещений в схеме <b>не указаны</b>.</li></ul><div class="note" style="margin-top:24px"><b>Диаграмма спагетти:</b> будет корректной только после фиксации реального маршрута и числа перемещений. Простые линии между столами не являются замерами и не используются в расчёте расстояний.</div><hr class="divider"><p class="card-sub">Если откроете другую модель, эта иллюстрация относится только к фабрике VENIO-C. Для иных предприятий следует загрузить их собственный план.</p></div></div></div>`;
}
function field(name,key,value,info,step='1',max=''){return `<div class="field"><label for="setting-${key}">${name}</label><input id="setting-${key}" type="number" step="${step}" min="0" ${max?`max="${max}"`:''} data-setting="${key}" value="${value===null?'':value}" placeholder="Нет данных" class="${value===null?'missing':''}"><small>${info}</small></div>`;}
function parameterView(){
 const s=state.model.settings;
 const cols=state.model.nodes.filter(n=>n.kind==='operation'||n.kind==='quality');
 return `${header('ДАННЫЕ / ПАРАМЕТРЫ','Конфигурация производственной модели',!isVenio(state.model)?'В этом примере все циклы и связи условные. Вносите параметры своего производственного процесса.':'Нормативы импортированы из инструкций фабрики. Любое редактирование здесь относится к вашему сценарию, а не к первоисточнику.',btn('↻ Вернуть исходные','reset','')+btn('▶ Пересчитать','run','primary'))}${disclaimer()}<div class="settings-grid"><section class="card fields-card"><h2>Производственная программа</h2><p class="card-sub">Целевые значения первого раунда</p><div class="form-grid">${field('Длительность смены, сек','shift_s',s.shift_s,'Продолжительность текущей модели в секундах')}${field('Заказ, изделий','target_units',s.target_units,'Целевой спрос текущей модели')}${field('Запущено комплектов','release_units',s.release_units,'Сценарное количество запусков')}<div class="field"><label>Такт, сек/изд</label><input type="number" readonly value="${s.takt_s}" aria-label="Такт вычисляется автоматически"><small>ФДВ / заказ. Пересчитывается автоматически при изменении смены или плана.</small></div></div></section><section class="card fields-card"><h2>Межоперационная логистика</h2><p class="card-sub">Нет замеров скорости и продолжительности рейсов</p><div class="form-grid">${field('Размер транспортной партии','transport_batch',s.transport_batch,'Сценарный размер партии перевозки')}${field('Количество логистов','logists',s.logists,'Количество доступных исполнителей логистики')}${field('Время одной поездки, сек','travel_s',s.travel_s,'0 = не учитываем неизвестное время; не наблюдение') }<div class="field"><label for="transport-policy">Правило партии</label><select id="transport-policy" data-settings-select="transport_policy"><option value="exact" ${s.transport_policy==='exact'?'selected':''}>Строго по ${s.transport_batch}</option><option value="max" ${s.transport_policy==='max'?'selected':''}>Не более ${s.transport_batch}</option></select><small>Для фабрики в первом раунде — строго по 2; другие правила являются гипотезами.</small></div></div></section></div><div style="height:16px"></div>${panel(!isVenio(state.model)?'Операции пользовательского/синтетического процесса':'Нормативы по рабочим местам',!isVenio(state.model)?'Условные времена для учебного процесса':'Времена рассчитаны как сумма шагов рабочего стандарта на одну единицу',`<div class="scroll-table"><table class="data-table"><thead><tr><th>Участок</th><th>Время, сек</th><th>Исполнители</th><th>CTн / такт</th><th>Источник</th></tr></thead><tbody>${cols.map(n=>`<tr><td><b>${esc(n.name)}</b></td><td><input style="max-width:93px" class="search-field" type="number" step="1" min="1" data-node-field="cycle_s" data-node-id="${esc(n.id)}" value="${n.cycle_s}"></td><td><input class="search-field" style="max-width:82px" type="number" step="1" min="1" max="16" data-node-field="workers" data-node-id="${esc(n.id)}" value="${n.workers}"></td><td>${(n.cycle_s/(s.takt_s*n.workers)).toFixed(2)} ${n.cycle_s>s.takt_s*n.workers?'<span class="badge red">Риск</span>':''}</td><td><span class="tiny muted">${esc(n.evidence||'Синтетика')}</span></td></tr>`).join('')}</tbody></table></div>`,btn('Проверить изменения','run','small primary'))}`;
}
function compareCell(name,a,b,unit='',higherGood=true){
 const diff=a===null||b===null?null:b-a;
 const good=diff===null?null:(higherGood?diff>=0:diff<=0);
 return `<tr><td><b>${name}</b></td><td>${num(a,1)}${unit}</td><td>${num(b,1)}${unit}</td><td>${diff===null?'—':`<span class="delta ${good?'':'bad'}">${diff>0?'+':''}${num(diff,1)}${unit}</span>`}</td></tr>`;
}
function scenarioView(){
 const c=state.comparison,r=state.result,b=c?.baseline||state.baselineResult,s=c?.scenario||r;
 return `${header('ЧТО ЕСЛИ? / SCENARIO LAB','Проверка гипотез TO-BE','Изменяйте длительности операций и параметры процесса, затем сравнивайте прогноз с исходной моделью. Эффект не подтверждён фактом внедрения.',btn(!isVenio(state.model)?'Гипотеза: ускорить узкое место':'Гипотеза: ускорить ОП-8','preset-bottleneck','soft')+btn('▶ Сравнить','compare','primary'))}${disclaimer()}<div class="grid half"><div class="card"><div class="section-row"><h2 class="card-title">AS-IS · исходные параметры</h2><span class="badge grey">Фиксированный базис</span></div><p class="card-sub">Расчёт на неизменённой исходной модели</p><div class="metric"><div class="label">Принято в сценарии</div><div class="number">${num(b?.accepted)} шт.</div></div></div><div class="card"><div class="section-row"><h2 class="card-title">TO-BE · проверяемая гипотеза</h2><span class="badge green">Редактируемый сценарий</span></div><p class="card-sub">Параметры из вкладки «Параметры»</p><div class="metric"><div class="label">Принято в сценарии</div><div class="number">${num(s?.accepted)} шт.</div></div></div></div><div style="height:16px"></div>${panel('Сравнение результатов','Разницы относятся только к выбранной расчётной модели',c?`<div class="scroll-table"><table class="data-table"><thead><tr><th>Показатель</th><th>AS-IS</th><th>TO-BE</th><th>Изменение</th></tr></thead><tbody>${compareCell('Принятые изделия',b.accepted,s.accepted,' шт',true)}${compareCell('Выработка',b.throughput_units_hour,s.throughput_units_hour,' шт/ч',true)}${compareCell('Расчётная длительность пути',b.theoretical_critical_path_s,s.theoretical_critical_path_s,' с',false)}${compareCell('Не приняты к концу смены',b.not_accepted,s.not_accepted,' шт',false)}${compareCell('Время изделия в модели',b.avg_flow_s,s.avg_flow_s,' с',false)}</tbody></table></div>`:`<div class="empty">Нажмите «Сравнить», чтобы получить результат сценария.</div>`)}<div style="height:16px"></div><div class="grid half">${panel('Гипотеза H-01','Балансировка критической операции',`<p class="desc">${!isVenio(state.model)?'Для другого процесса гипотеза меняет длительность самой медленной операции на 20%. Этот параметр не подтверждает реальное улучшение.':'Сократить нормативное время на установку болтов с <b>171 до 120 секунд</b>. Это только целевой параметр для проверки; необходимо обосновать организационными мерами и фактическими замерами.'}</p>`,btn('Применить','preset-bottleneck','small soft'))}${panel('Настройки сравнения','Условия должны быть сопоставимы',`<p class="desc">Смена, спрос, начальные условия и правила моделирования должны быть одинаковы. Для корректной интерпретации меняйте один фактор за раз.</p>`,btn('Сбросить сценарий','reset','small'))}</div>`;
}
function financeView(){const s=state.model.settings,r=state.result,items=[['Выручка с изделия, ₽','unit_sale_price','Не предоставлена'],['Материалы на один запуск, ₽','unit_material_cost','Не предоставлена'],['Труд в смену, ₽','labor_cost_shift','Не предоставлена'],['Логистика в смену, ₽','logistic_cost_shift','Не предоставлена'],['Прочие расходы в смену, ₽','overhead_cost_shift','Не предоставлены']];
 return `${header('СТОИМОСТЬ / ПРИБЫЛЬ','Экономика без выдуманных чисел','Отсутствующие финансовые ставки нельзя автоматически заменять нулём. Расчёт откроется только после ввода всех исходных значений.',btn('▶ Рассчитать','run','primary'))}${disclaimer()}<div class="grid cols"><section class="card fields-card"><h2>Ввод финансовых параметров</h2><p class="card-sub">Поля необязательны. Источники и даты утверждения ставок нужно приложить отдельно.</p><div class="form-grid" style="margin-top:19px">${items.map(([name,key,info])=>field(name,key,s[key],info,'0.01')).join('')}</div></section>${panel('Предварительный результат','Расчёт на сценарно введённых ставках',r?.financial.status==='calculated'?`<div class="metric"><div class="label">Модельная прибыль</div><div class="number">${num(r.financial.profit,2)} ₽</div></div><table class="data-table"><tbody>${[['Выручка',r.financial.revenue],['Материалы',r.financial.materials],['Труд',r.financial.labor],['Логистика',r.financial.logistics],['Прочие',r.financial.overhead]].map(([k,v])=>`<tr><td>${k}</td><td>${num(v,2)} ₽</td></tr>`).join('')}</tbody></table>`:`<div class="empty">Недостаточно подтверждённых финансовых данных для расчёта прибыли. Пока это корректный результат: <b>«нет данных»</b>, а не 0 ₽.</div>`)}</div>`;
}
const SOURCES=[
 ['ТЗ_хакатон_предв(3).docx','Цель, функциональность, ограничения, сценарный анализ, прототип','ТЗ организаторов'],
 ['МУ_Составление_карт_потоков_и_процессов_1.pdf','МУ-17-2023: текущая / идеальная / целевая КПСЦ, символы, показатели','Методика ФЦК'],
 ['0. Общее описание Фабрики процессов(3).pdf','20 минут, 10 изделий, 120 секунд такт, 9 операторов, логист, ОТК','Правила фабрики'],
 ['1. Комплектация рабочих мест(2).pdf','Наборы деталей и оснащение операторов 1–10','Детали рабочих мест'],
 ['2. Детали в разбивке по рабочим местам(2).pdf','Карточки комплектации на один раунд для 1–9 рабочих мест','Логистика'],
 ['3. Стандарты выполнения операций(3).pdf','Состав действий и нормативные времена, стр. 33–50; логист, стр. 51–53','Основа CTн'],
 ['4. Заполнение блоков инфоцентра (дашборда)(2).pdf','Качество, исполнение, запасы, затраты и безопасность','Метрики / формы'],
 ['6. Планировка Фабрики процессов(3).pdf','Расположение столов и габариты учебного зала','Планировка'],
 ['Приложение №3. Шаблон КПСЦ2.xlsx','Официальные шаблон КПСЦ, обозначения и показатели','Шаблон ФЦК'],
 ['Карта потока детализ. пример.xlsx','Пример текущей и целевой схемы, не факт по фабрике','Образец ФЦК']];
function sourcesView(){
 const synthetic=!isVenio(state.model);
 const verified=synthetic?`<ul class="list-clean"><li>В текущей модели нет подтверждённых производственных наблюдений.</li><li>Учебные операции «Раскрой» и «Покрытие» введены специально для проверки универсальности.</li><li>Для демонстрационного примера VENIO-C используйте переключатель «Базовый VENIO-C».</li></ul>`:`<ul class="list-clean"><li>Девять сборочных мест и отдельный ОТК.</li><li>Циклы по рабочим стандартам: 83, 66, 13, 61, 35, 39, 102, 171, 82, 22 секунд (ОТК).</li><li>Цель первого раунда — 10 изделий за 20 минут, такт 120 секунд.</li><li>Партия перевозки между рабочими столами в первом раунде — 2 изделия.</li></ul>`;
 return `${header('ПРОИСХОЖДЕНИЕ / EVIDENCE','Источники и допущения','Каждое значение, маршрут и бизнес-вывод должны иметь источник. Расчётные предположения отделены от нормативов и реальных наблюдений.',btn('Базовый VENIO-C','original','')+btn('Синтетический процесс','generic','primary'))}${disclaimer()}${panel('Реестр материалов','Источники базовой фабрики VENIO-C; не являются источниками синтетического примера',SOURCES.map((x,i)=>`<div class="source-row"><div class="source-id">${String(i+1).padStart(2,'0')}</div><div><b>${esc(x[0])}</b><p>${esc(x[1])}</p></div><span class="badge grey">${esc(x[2])}</span></div>`).join(''))}<div style="height:16px"></div><div class="grid half">${panel('Что подтверждено',synthetic?'Для синтетического примера нет фактических источников':'Нормативные данные и правила VENIO-C',verified)}${panel('Каких данных не хватает','Нужно согласовать с экспертами',`<ul class="list-clean"><li>Фактический хронометраж: не менее двух замеров на оператора.</li><li>Подтверждение маршрутов и соединения подсборок.</li><li>Реальная траектория логиста, длительность и число перевозок.</li><li>НЗП на входе/выходе, простой, переналадка, брак и доработка.</li><li>Денежные ставки для экономического эффекта.</li></ul>`)}</div>`;
}
function methodView(){return `${header('МУ-17-2023 / LEAN','Методическая основа модели','От анализа потока до решений: не подменяем наблюдения, различаем виды времени и сопоставляем состояния по одной методике.',btn('Источники','goto-sources','primary'))}${panel('Этапы составления КПСЦ','Последовательность по МУ-17-2023, таблица 1, стр. 6',`<div class="grid half">${['Выбрать продукт, цели и границы','Составить текущую КПСЦ и измерить параметры','Построить идеальную КПСЦ с доказательствами','Сопоставить текущую и идеальную карты','Построить целевую КПСЦ и рассчитать KPI','Разработать мероприятия по устранению причин'].map((x,i)=>`<div class="data-card"><h3><span class="pill-step">${i+1}</span>${x}</h3><p>${['Подтверждён: учебный продукт','Предварительно: нужна верификация','Пока концептуальный ориентир','Нужны фактические KPI','Сценарные гипотезы, не результат','Требуются решения и обоснования'][i]}</p></div>`).join('')}</div>`)}<div style="height:16px"></div>${panel('Единый глоссарий','Терминология и области применимости вычислений',`<div class="scroll-table"><table class="data-table"><thead><tr><th>Термин</th><th>Определение</th><th>Состояние данных</th></tr></thead><tbody>${[
 ['CTн · нормативное время','Сумма секунд шагов стандартной операции на изделие',state.model.status==='synthetic_demo'?'В синтетическом примере отсутствует':'Есть, но это не хронометраж'],
 ['CTф · фактический цикл','Реально измеренный повторяющийся рабочий цикл','Нет замеров'],
 ['Такт','Фонд доступного времени / спрос, сек/шт',!isVenio(state.model)?'Задан параметром сценария':'120 с по условиям раунда'],
 ['ВПП','Время критического пути с ожиданием и транспортировкой','Без замеров не определено'],
 ['НЗП','Незавершённые изделия/подсборки в процессе','Нужны записи начала/конца'],
 ['Узкое место','Ресурс, ограничивающий весь поток',!isVenio(state.model)?'Сценарный расчёт':'Потенциальное по CTн: №8'],
 ['Пропускная способность','Принятое количество / длительность моделирования','Вычисляется в сценарии'],
 ['AS-IS / IDEAL / TO-BE','Текущее / идеальное / реализуемое целевое состояния','Нужны подтверждения'],
 ].map(([a,b,c])=>`<tr><td><b>${a}</b></td><td>${b}</td><td><span class="table-status">${c}</span></td></tr>`).join('')}</tbody></table></div>`)}<div class="note" style="margin-top:16px"><b>Граница модели:</b> это ориентированный граф операций с объединением подсборок, расчетом очередей при партии и сценарием ресурсов. Это не полная производственная DES-модель: не проверены маршруты, не воспроизводятся возвраты брака, реальный логистический маршрут, МТО и финансовые потери. Их нельзя скрывать.</div>`;}
async function run(quiet=false){try{state.running=true;state.result=await api('simulate',state.model);state.dirty=false;if(!quiet)toast('Сценарий рассчитан. Проверьте предупреждения к результату.');}catch(err){if(!quiet)toast('Ошибка модели: '+err.message);throw err;}finally{state.running=false;}}
async function applyModelChange(mutator,message){
 const proposed=clone(state.model);mutator(proposed);
 await api('validate',proposed);
 const result=await api('simulate',proposed);
 state.model=proposed;state.result=result;state.comparison=null;state.dirty=false;state.showStage='target';
 render();toast(message+' · сервер пересчитал модель');
}
function redrawMapOnly(){
 const space=$('#flow-space');if(!space)return;
 // Only redraw the SVG, keeping scroll position, sidebar and inspector intact.
 space.innerHTML=graphSvg(state.showStage==='current'?state.baseline:state.model);
}
let drag=null,skipClickUntil=0,skipClickNode=null;
// A pointer must be captured by the STABLE workspace. The SVG itself is
// recreated while dragging, and capturing it causes intermittent lost drags.
document.addEventListener('pointerdown',event=>{
 const group=event.target.closest?.('#flow-space svg [data-node]');
 if(!group||state.showStage==='ideal'||(event.pointerType==='mouse'&&event.button!==0))return;
 const space=$('#flow-space'),svg=group.closest('svg');
 const id=group.dataset.node,shown=state.showStage==='current'?state.baseline:state.model;
 const coords=graphGeometry(shown,state.model.kpsc_layout||{}).positions[id];
 const rect=svg.getBoundingClientRect();
 if(!coords||!rect.width||!rect.height)return;
 drag={id,initialX:coords.x,initialY:coords.y,startX:event.clientX,startY:event.clientY,
       scaleX:svg.viewBox.baseVal.width/rect.width,scaleY:svg.viewBox.baseVal.height/rect.height,
       moved:false,pointerId:event.pointerId,space};
 try{space.setPointerCapture(event.pointerId);}catch(_){/* fallback: document listeners */}
});
document.addEventListener('pointermove',event=>{
 if(!drag||event.pointerId!==drag.pointerId)return;
 const dx=(event.clientX-drag.startX)*drag.scaleX;
 const dy=(event.clientY-drag.startY)*drag.scaleY;
 if(!drag.moved&&Math.hypot(dx,dy)<5)return;
 if(!drag.moved){drag.moved=true;state.selected=drag.id;drag.space.classList.add('is-dragging');}
 // These are presentation coordinates ONLY; never change nodes or edges.
 const p={x:Math.round(Math.max(15,Math.min(9500,drag.initialX+dx))),
          y:Math.round(Math.max(72,Math.min(9500,drag.initialY+dy)))};
 (state.model.kpsc_layout||(state.model.kpsc_layout={}))[drag.id]=p;
 redrawMapOnly();event.preventDefault();
},{passive:false});
function finishDrag(event,cancel=false){
 if(!drag||event.pointerId!==drag.pointerId)return;
 const d=drag;drag=null;
 d.space.classList.remove('is-dragging');
 try{if(d.space.hasPointerCapture(d.pointerId))d.space.releasePointerCapture(d.pointerId);}catch(_){/* capture may be lost */}
 if(cancel)return;
 if(d.moved){
  skipClickUntil=Date.now()+350;skipClickNode=d.id;
  toast('Блок перемещён только на схеме. Экспортируйте JSON для сохранения после перезапуска.');
 }else{state.selected=d.id;render();}
}
document.addEventListener('pointerup',event=>finishDrag(event));
document.addEventListener('pointercancel',event=>finishDrag(event,true));
async function compareScenario(){try{state.comparison=await api('compare',{baseline:state.baseline,scenario:state.model});state.result=state.comparison.scenario;state.dirty=false;toast('Базовый и целевой сценарии пересчитаны.');render();}catch(e){toast(e.message);}}
function exportFile(name,obj){const blob=new Blob([JSON.stringify(obj,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);let a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),500);}
function showModal(title,body,controls){const popup=document.createElement('div');popup.id='dialog';popup.style.cssText='position:fixed;inset:0;background:#111b34aa;z-index:20;display:grid;place-items:center;padding:20px';popup.innerHTML=`<div class="card" style="max-width:510px;width:100%;box-shadow:0 30px 80px #10193850"><h2>${title}</h2><div>${body}</div><div style="display:flex;gap:9px;justify-content:flex-end;margin-top:24px">${btn('Закрыть','close-dialog')}${controls||''}</div></div>`;document.body.appendChild(popup);}
function addOperationDialog(){const options=state.model.edges.map((e,i)=>({...e,idx:i})).filter(e=>!state.model.nodes.some(n=>n.id===e.from&&n.kind==='quality')&&!state.model.nodes.some(n=>n.id===e.to&&n.kind==='customer')).map(e=>`<option value="${e.idx}">${esc(e.from)} → ${esc(e.to)}</option>`).join('');showModal('Добавить операцию в маршрут',`<p class="desc">Новый узел вставится между существующими узлами. Значения новой операции считаются синтетическими, пока не указаны источник и замеры.</p><div class="field" style="margin-top:16px"><label>Название операции</label><input id="new-name" maxlength="120" placeholder="Например, упаковка"></div><div class="field" style="margin-top:12px"><label>Время цикла, секунд</label><input id="new-cycle" type="number" min="1" step="1" value="60"></div><div class="field" style="margin-top:12px"><label>Вставить между</label><select id="new-parent">${options}</select></div>`,btn('Создать узел','confirm-add','primary'));}
function addEdgeDialog(){let options=state.model.nodes.filter(n=>n.kind!=='customer').map(n=>`<option value="${esc(n.id)}">${esc(n.id+' · '+n.name)}</option>`).join('');let dest=state.model.nodes.filter(n=>n.kind!=='source').map(n=>`<option value="${esc(n.id)}">${esc(n.id+' · '+n.name)}</option>`).join('');showModal('Добавить материальную связь',`<p class="desc">Выбирайте связь только при наличии подтверждения. Для сборки нескольких подсборок входы выполняются по принципу AND-объединения.</p><div class="field" style="margin-top:15px"><label>Откуда</label><select id="edge-from">${options}</select></div><div class="field" style="margin-top:12px"><label>Куда</label><select id="edge-to">${dest}</select></div>`,btn('Добавить связь','confirm-edge','primary'));}
function removeEdgeDialog(){
 const rows=state.model.edges.filter(e=>e.from!==state.model.nodes.find(n=>n.kind==='quality')?.id);
 const options=rows.map(e=>`<option value="${esc(e.from+'|'+e.to)}">${esc(e.from+' → '+e.to+' · '+(e.category==='supply'?'снабжение':'связь'))}</option>`).join('');
 showModal('Удалить материальную связь',`<p class="desc">Удаление меняет технологические зависимости, а не оформление карты. Сервер не позволит разорвать обязательный путь от склада до заказчика.</p><div class="field" style="margin-top:16px"><label>Выберите связь</label><select id="edge-remove">${options}</select></div>`,btn('Проверить и удалить','confirm-remove-edge','danger'));
}
async function loadWhich(endpoint){try{const data=await api(endpoint);state.model=clone(data);state.baseline=clone(data);state.baselineResult=null;state.comparison=null;state.selected=data.nodes.find(n=>n.kind==='operation')?.id;await run(true);state.baselineResult=clone(state.result);render();toast('Модель открыта: '+data.name);}catch(e){toast(e.message);}}
document.addEventListener('click',async e=>{
 const view=e.target.closest('[data-view]');if(view){state.view=view.dataset.view;render();return;}
 const sel=e.target.closest('[data-node]');if(sel){if(Date.now()<skipClickUntil&&sel.dataset.node===skipClickNode)return;state.selected=sel.dataset.node;render();return;}
 const floor=e.target.closest('[data-select-node]');if(floor){state.selected=floor.dataset.selectNode;state.view='map';render();return;}
 const action=e.target.closest('[data-action]')?.dataset.action;if(!action)return;
 try{switch(action){
  case 'run':await run();render();break;
  case 'compare':await compareScenario();break;
  case 'goto-map':state.view='map';render();break;
  case 'goto-target':state.view='map';state.showStage='target';render();break;
  case 'goto-scenarios':state.view='scenarios';render();break;
  case 'goto-parameters':state.view='parameters';render();break;
  case 'goto-sources':state.view='sources';render();break;
  case 'generic':await loadWhich('generic');break;
  case 'original':await loadWhich('demo');break;
  case 'export':exportFile((state.model.id||'process')+'_model.json',state.model);break;
  case 'import':$('#import-file').click();break;
  case 'logout':await api('logout',{});state.model=null;renderLogin();break;
  case 'reset':state.model=clone(state.baseline);state.comparison=null;await run();render();break;
  case 'preset-bottleneck':{const node=(isVenio(state.model)?state.model.nodes.find(n=>n.id==='o8'):null)||state.model.nodes.filter(n=>n.kind==='operation').sort((a,b)=>b.cycle_s-a.cycle_s)[0];if(node){const id=node.id;await applyModelChange(m=>{const n=m.nodes.find(n=>n.id===id);n.cycle_s=!isVenio(m)?Math.max(1,Math.round(n.cycle_s*0.8)):120;n.cycle_basis='target_hypothesis_not_fact';},'Гипотеза применена');state.selected=id;await compareScenario();}break;}
  case 'add-operation':addOperationDialog();break;
  case 'add-edge':addEdgeDialog();break;
  case 'remove-edge':removeEdgeDialog();break;
  case 'reset-layout':delete state.model.kpsc_layout;redrawMapOnly();toast('Автоматическое расположение восстановлено; расчёты не менялись');break;
  case 'close-dialog':$('#dialog')?.remove();break;
  case 'confirm-remove-edge':{
   const [from,to]=($('#edge-remove')?.value||'').split('|');
   await applyModelChange(m=>{m.edges=m.edges.filter(edge=>!(edge.from===from&&edge.to===to));},'Материальная связь удалена');
   $('#dialog')?.remove();break;
  }
  case 'confirm-add':{
   const name=$('#new-name')?.value.trim();const cycle=Number($('#new-cycle')?.value);const idx=Number($('#new-parent')?.value);
   if(!name||!(cycle>0&&cycle<=7200))throw new Error('Укажите название и цикл от 1 до 7200 секунд');
   const old=state.model.edges[idx];if(!old)throw new Error('Неверная связь');
   let j=1;while(state.model.nodes.some(n=>n.id==='custom'+j))j++;
   const id='custom'+j;
   await applyModelChange(m=>{
    m.nodes.push({id,kind:'operation',name,cycle_s:cycle,workers:1,defect_pct:0,evidence:'Введено вручную, проверить',cycle_basis:'hypothesis'});
    m.edges.splice(idx,1,{from:old.from,to:id,category:'assembly',verification:'requires_expert_confirmation'},{from:id,to:old.to,category:'assembly',verification:'requires_expert_confirmation'});
   },'Операция создана как гипотеза');
   $('#dialog')?.remove();state.selected=id;render();break;
  }
  case 'confirm-edge':{
   const from=$('#edge-from').value,to=$('#edge-to').value;
   const existed=state.model.edges.some(edge=>edge.from===from&&edge.to===to);
   if(existed)throw new Error('Связь уже существует');
   await applyModelChange(m=>{m.edges.push({from,to,category:'assembly',verification:'requires_expert_confirmation'});},'Связь создана как гипотеза');$('#dialog')?.remove();break;
  }
 }}catch(err){toast(err.message);}
});
document.addEventListener('change',async e=>{
 const t=e.target;
 if(t.id==='stage-select'){state.showStage=t.value;render();return;}
 if(t.dataset.setting){
  const key=t.dataset.setting,raw=t.value.trim(),v=raw===''?null:Number(raw);
  if(v!==null&&!Number.isFinite(v)){toast('Некорректное значение');render();return;}
  try{await applyModelChange(m=>{m.settings[key]=v;if(key==='shift_s'||key==='target_units')m.settings.takt_s=m.settings.shift_s/m.settings.target_units;},'Параметр обновлён');}
  catch(err){toast('Не сохранено: '+err.message);render();}
  return;
 }
 if(t.dataset.settingsSelect){
  try{await applyModelChange(m=>{m.settings[t.dataset.settingsSelect]=t.value;},'Правило перевозки обновлено');}
  catch(err){toast('Не сохранено: '+err.message);render();}
  return;
 }
 if(t.dataset.nodeField){
  const id=t.dataset.nodeId,key=t.dataset.nodeField,v=Number(t.value);
  if(t.value.trim()===''||!Number.isFinite(v)||v<=0||(key==='workers'&&!Number.isInteger(v))){toast('Введите допустимое положительное значение');render();return;}
  try{await applyModelChange(m=>{const node=m.nodes.find(x=>x.id===id);if(!node)throw Error('Узел не найден');node[key]=v;if(node.cycle_basis==='work_standard_not_observed')node.cycle_basis='changed_as_scenario';},'Параметр операции сохранён');}
  catch(err){toast('Не сохранено: '+err.message);render();}
  return;
 }
 if(t.id==='import-file'){
  const file=t.files[0];if(!file)return;if(file.size>1024*1024){toast('Максимальный размер: 1 МБ');return;}
  try{const model=JSON.parse(await file.text());await api('validate',model);state.model=model;state.baseline=clone(model);state.selected=model.nodes.find(n=>n.kind==='operation')?.id;state.comparison=null;state.baselineResult=null;await run(true);state.baselineResult=clone(state.result);render();toast('Модель импортирована и проверена');}catch(err){toast('Ошибка импорта: '+err.message);}finally{t.value='';}
 }
});
window.addEventListener('keydown',e=>{
 if(e.key==='Escape'){$('#dialog')?.remove();return;}
 const group=e.target.closest?.('#flow-space svg [data-node]');
 if(!group||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
 e.preventDefault();const id=group.dataset.node;
 const pos=graphGeometry(state.showStage==='current'?state.baseline:state.model,state.model.kpsc_layout||{}).positions[id];if(!pos)return;
 const step=e.shiftKey?30:12;
 const dx=e.key==='ArrowRight'?step:e.key==='ArrowLeft'?-step:0;
 const dy=e.key==='ArrowDown'?step:e.key==='ArrowUp'?-step:0;
 (state.model.kpsc_layout||(state.model.kpsc_layout={}))[id]={x:Math.max(15,pos.x+dx),y:Math.max(72,pos.y+dy)};
 state.selected=id;redrawMapOnly();[...document.querySelectorAll('#flow-space [data-node]')].find(n=>n.dataset.node===id)?.focus();
});
(async()=>{try{const auth=await api('session');if(!auth.authenticated){renderLogin();return;}await init();}catch(e){renderLogin('Сервер недоступен: '+e.message);}})();
