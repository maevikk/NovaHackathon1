"""Validation, provenance guardrails and graph utilities for PROCESS LAB v4."""
from __future__ import annotations
from collections import defaultdict, deque
import math

class ModelError(ValueError):
    pass

ALLOWED_KINDS = {'source', 'operation', 'quality', 'customer'}
MAX_NODES = 80
MAX_EDGES = 260

def nonnegative(value, name, *, max_value=1e7, allow_none=False):
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= max_value:
        raise ModelError(f'{name}: ожидается конечное число от 0 до {max_value}')
    return value

def positive_int(value, name, maximum=10000):
    nonnegative(value, name, max_value=maximum)
    if not isinstance(value, int) or value <= 0:
        raise ModelError(f'{name}: ожидается положительное целое число')
    return value

def validate(model):
    if not isinstance(model, dict):
        raise ModelError('Модель должна быть JSON-объектом')
    nodes, edges, settings = model.get('nodes'), model.get('edges'), model.get('settings')
    if not isinstance(nodes, list) or not 3 <= len(nodes) <= MAX_NODES:
        raise ModelError(f'nodes: требуется от 3 до {MAX_NODES} узлов')
    if not isinstance(edges, list) or not 1 <= len(edges) <= MAX_EDGES:
        raise ModelError(f'edges: требуется от 1 до {MAX_EDGES} связей')
    if not isinstance(settings, dict):
        raise ModelError('settings: требуется объект')
    by_id, incoming, outgoing, types = {}, defaultdict(list), defaultdict(list), defaultdict(list)
    for n in nodes:
        if not isinstance(n, dict):
            raise ModelError('Каждый узел должен быть объектом')
        nid, kind = n.get('id'), n.get('kind')
        if not isinstance(nid, str) or not 1 <= len(nid) <= 60 or not nid.replace('_', '').replace('-', '').isalnum() or nid in by_id:
            raise ModelError('ID узла пустой, повторяется или содержит недопустимые символы')
        if kind not in ALLOWED_KINDS:
            raise ModelError(f'{nid}: неизвестный тип {kind}')
        if not isinstance(n.get('name'), str) or not 1 <= len(n['name']) <= 160:
            raise ModelError(f'{nid}: требуется название')
        if kind in {'operation', 'quality'}:
            nonnegative(n.get('cycle_s'), f'{nid}.cycle_s', max_value=7200)
            if n['cycle_s'] <= 0: raise ModelError(f'{nid}.cycle_s должно быть > 0')
            positive_int(n.get('workers'), f'{nid}.workers', 16)
            nonnegative(n.get('defect_pct', 0), f'{nid}.defect_pct', max_value=100)
        for axis in ('x','y'):
            if axis in n: nonnegative(n[axis], f'{nid}.{axis}', max_value=10000)
        by_id[nid], types[kind] = n, types[kind] + [nid]
    if len(types['source']) != 1 or len(types['customer']) != 1 or len(types['quality']) != 1 or not types['operation']:
        raise ModelError('Требуются один склад-источник, один ОТК, один заказчик и минимум одна операция')
    # Visual positions are saved independently of the production graph.
    # Dragging a block must never silently modify an operation or material edge.
    layout=model.get('kpsc_layout',{})
    if not isinstance(layout,dict):raise ModelError('kpsc_layout должен быть объектом')
    for node_id,coords in layout.items():
        if node_id not in by_id:raise ModelError('kpsc_layout: неизвестный узел '+str(node_id))
        if not isinstance(coords,dict):raise ModelError('kpsc_layout: ожидается объект координат')
        for axis in ('x','y'):
            nonnegative(coords.get(axis),f'kpsc_layout.{node_id}.{axis}',max_value=10000)
    edge_ids = set()
    for edge in edges:
        if not isinstance(edge, dict): raise ModelError('Связь должна быть объектом')
        a, b = edge.get('from'), edge.get('to')
        if a not in by_id or b not in by_id or a == b:
            raise ModelError(f'Некорректная связь {a} → {b}')
        if (a,b) in edge_ids: raise ModelError(f'Повторяющаяся связь {a} → {b}')
        if by_id[a]['kind']=='customer' or by_id[b]['kind']=='source' or (by_id[a]['kind']=='quality' and by_id[b]['kind']!='customer') or (by_id[b]['kind']=='customer' and by_id[a]['kind']!='quality'):
            raise ModelError(f'Запрещённая связь {a} → {b}')
        edge_ids.add((a,b)); incoming[b].append(a); outgoing[a].append(b)
    indegree={n:len(incoming[n]) for n in by_id}
    ready=deque(n for n in by_id if indegree[n]==0)
    order=[]
    while ready:
        nid=ready.popleft(); order.append(nid)
        for other in outgoing[nid]:
            indegree[other]-=1
            if indegree[other]==0: ready.append(other)
    if len(order)!=len(by_id): raise ModelError('Обнаружен цикл. Для возврата на доработку нужна отдельная модель')
    source, customer, qc=types['source'][0], types['customer'][0], types['quality'][0]
    def reachable(start, adj):
        seen=set(); stack=[start]
        while stack:
            n=stack.pop()
            if n in seen:continue
            seen.add(n);stack.extend(adj[n])
        return seen
    from_source=reachable(source,outgoing); to_customer=reachable(customer,incoming)
    if not all(n in from_source and n in to_customer for n in by_id):
        raise ModelError('Все узлы должны лежать на пути от склада к заказчику')
    if outgoing[qc] != [customer]: raise ModelError('ОТК должна предшествовать заказчику')
    for k,limit in [('shift_s',86400),('target_units',10000),('release_units',10000),('transport_batch',100),('logists',12)]:
        positive_int(settings.get(k),f'settings.{k}',limit)
    nonnegative(settings.get('takt_s'), 'settings.takt_s', max_value=86400)
    if settings['takt_s']<=0:raise ModelError('settings.takt_s должно быть больше 0')
    if abs(settings['shift_s']/settings['target_units']-settings['takt_s'])>0.00001:
        raise ModelError('Такт должен соответствовать ФДВ/спросу: shift_s / target_units')
    if settings['release_units']<settings['target_units']:
        raise ModelError('Количество запусков не меньше плана заказчика')
    if settings.get('transport_policy') not in {'max', 'exact'}:
        raise ModelError('transport_policy: max или exact')
    nonnegative(settings.get('travel_s',0),'settings.travel_s',max_value=3600)
    for field in ['unit_material_cost','unit_sale_price','labor_cost_shift','logistic_cost_shift','overhead_cost_shift']:
        nonnegative(settings.get(field),f'settings.{field}',allow_none=True,max_value=1e10)
    return {'nodes':by_id, 'edges':edges, 'incoming':incoming, 'outgoing':outgoing,
            'order':order,'source':source,'customer':customer,'qc':qc,'settings':settings}
