"""Deterministic event simulation of DAG assembly, AND-joins and batch transport.

EXPLICIT SIMPLIFICATIONS:
- Planned standard work times are not measured current-state cycle times.
- All necessary component kits are available at t=0 in demo; initial WIP=0.
- Per-edge one token represents one kit/subassembly per final product.
- Routing and defect values are hypotheses, not verified observations.
- Transport time defaults to zero because actual time was not provided.
- AND joins consume one input per predecessor; do not model scrap/rework loops.
"""
from __future__ import annotations
from collections import deque
from itertools import count
import heapq
import random
from .model import validate


def simulate(model):
    g=validate(model); nodes=g['nodes']; s=g['settings']; horizon=s['shift_s'];
    source=g['source']; customer=g['customer']; qc=g['qc']
    pending={ (e['from'],e['to']):deque() for e in g['edges']}
    delivered={edge:deque() for edge in pending}
    for dst in g['outgoing'][source]:
        key=(source,dst)
        for order_id in range(s['release_units']): pending[key].append({'birth':0.0, 'lot':order_id})
    busy={n:0 for n in nodes}; processed={n:0 for n in nodes}; started={n:0 for n in nodes};
    op_busy_s={n:0.0 for n in nodes}; max_queues={n:0 for n in nodes}; waited={n:0.0 for n in nodes};
    events=[]; counter=count(); time=0.; accepted=0; finished=0; accepted_times=[]; finished_times=[]
    deliveries=0; transported=0; active_logists=0; trip_seconds=0.; ready_customer=deque();
    events_seen=0
    completed_scrap=0
    rand=random.Random(int(s.get('seed',2026)))
    op_ids=[n for n in g['order'] if nodes[n]['kind'] in ('operation','quality')]
    last_queue_counts={n:0 for n in op_ids}

    def push(t, event, **kw): heapq.heappush(events,(round(t,7),next(counter),event,kw))

    def update_queue(n):
        if n not in last_queue_counts:return
        q=sum(len(delivered[(a,n)]) for a in g['incoming'][n])
        max_queues[n]=max(max_queues[n],q)
        last_queue_counts[n]=q

    def plan_transport():
        nonlocal active_logists, deliveries, transported, trip_seconds
        # Only edges with sufficient quantity can depart in exact-batch mode.
        # Production transfers and warehouse provisioning are handled uniformly.
        batch=s['transport_batch']; exact=s['transport_policy']=='exact'
        while active_logists<s['logists']:
            options=[]
            for key,queue in pending.items():
                if key[1]==customer: continue  # client pickup, not logistic movement
                if queue and (not exact or len(queue)>=batch):
                    options.append((queue[0]['birth'],key[0],key[1],key))
            if not options:break
            options.sort();key=options[0][-1]
            take=min(batch,len(pending[key])); payload=[pending[key].popleft() for _ in range(take)]
            active_logists+=1;deliveries+=1;transported+=take
            dt=s.get('travel_s',0)
            trip_seconds+=min(dt,max(0,horizon-time))
            push(time+max(0,dt),'arrival', edge=key,tokens=payload)

    def start_operations(n):
        if n not in op_ids:return
        needed=[(parent,n) for parent in g['incoming'][n]]
        if not needed: return
        node=nodes[n]
        # AND-join: assemble components for the SAME final product ID. A plain
        # FIFO pop from each inbound edge could mix two products after a defect.
        while busy[n]<node['workers'] and all(delivered[e] for e in needed) and started[n]<s['release_units']:
            common=set(token['lot'] for token in delivered[needed[0]])
            for edge in needed[1:]:
                common.intersection_update(token['lot'] for token in delivered[edge])
            if not common:
                break
            lot=min(common)
            inputs=[]
            for edge in needed:
                match=next(token for token in delivered[edge] if token['lot']==lot)
                delivered[edge].remove(match)
                inputs.append(match)
            birth=min(x['birth'] for x in inputs)
            waited[n]+=sum(time-x.get('delivered_at',time) for x in inputs)/len(inputs)
            busy[n]+=1;started[n]+=1; update_queue(n)
            cycle=node['cycle_s']; op_busy_s[n]+=min(cycle,max(0,horizon-time))
            push(time+cycle,'complete',node=n,birth=birth,lot=lot)

    # Customer pickup at takt intervals, including at end of shift.
    tick=s['takt_s']
    while tick<=horizon+1e-7:
        push(tick,'pickup');tick+=s['takt_s']
    plan_transport()
    while events:
        t,_,etype,p=heapq.heappop(events)
        if t>horizon+1e-7:break
        time=t;events_seen+=1
        if events_seen>300000:raise ValueError('Превышен лимит событий')
        if etype=='arrival':
            active_logists-=1
            key=p['edge']
            for token in p['tokens']:
                token['delivered_at']=time
                delivered[key].append(token)
            update_queue(key[1]);start_operations(key[1]);plan_transport()
        elif etype=='complete':
            nid=p['node'];busy[nid]-=1;processed[nid]+=1
            if rand.random()*100 < nodes[nid].get('defect_pct',0):
                completed_scrap+=1
            elif nid==qc:
                finished+=1;finished_times.append(time)
                ready_customer.append({'birth':p['birth'],'done':time,'lot':p['lot']})
            else:
                for target in g['outgoing'][nid]:
                    pending[(nid,target)].append({'birth':p['birth'],'lot':p['lot']})
            start_operations(nid);plan_transport()
        elif etype=='pickup':
            if ready_customer and accepted<s['target_units']:
                token=ready_customer.popleft();accepted+=1
                accepted_times.append({'t':time,'flow_s':time-token['birth'],'lot':token['lot']})
    throughput=accepted/(horizon/3600)
    bottleneck=max((n for n in op_ids if n!=qc),key=lambda n:nodes[n]['cycle_s']/nodes[n]['workers'])
    by_operation=[]
    for n in op_ids:
        row=nodes[n]
        by_operation.append({
            'id':n,'name':row['name'],'cycle_s':row['cycle_s'],'workers':row['workers'],
            'started':started[n], 'completed':processed[n],
            'capacity_units_hour':round(3600*row['workers']/row['cycle_s'],2),
            'utilization_pct':round(100*op_busy_s[n]/(horizon*row['workers']),1),
            'queue_max_tokens':max_queues[n],
            'risk_above_takt':row['cycle_s']/row['workers']>s['takt_s'],
            'source':row.get('evidence','unknown'),
        })
    max_path={}; predecessor={}
    for n in g['order']:
        inputs=g['incoming'][n]
        prev=max(inputs,key=lambda x:max_path.get(x,0),default=None)
        max_path[n]=max_path.get(prev,0)+(nodes[n].get('cycle_s',0) if nodes[n]['kind'] in {'operation','quality'} else 0)
        predecessor[n]=prev
    critical=[];n=customer
    while n is not None:
        if n not in (source,customer):critical.append(n)
        n=predecessor[n]
    critical.reverse()
    price=s.get('unit_sale_price');raw=s.get('unit_material_cost');labor=s.get('labor_cost_shift');
    logistics=s.get('logistic_cost_shift');overhead=s.get('overhead_cost_shift')
    finance={
        'status':'calculated' if all(x is not None for x in (price,raw,labor,logistics,overhead)) else 'insufficient_data',
        'revenue':round(accepted*price,2) if price is not None else None,
        'materials':round(s['release_units']*raw,2) if raw is not None else None,
        'labor':labor,'logistics':logistics,'overhead':overhead,'profit':None,
    }
    if finance['status']=='calculated':
        finance['profit']=round(finance['revenue']-finance['materials']-labor-logistics-overhead,2)
    venio = model.get('id')=='venio-c' and model.get('status')=='illustrative_normative_scenario'
    synthetic = not venio
    return {
        'status':'ok','simulation_type':'deterministic_educational_scenario',
        'shift_s':horizon,'target':s['target_units'],'released':s['release_units'],
        'accepted':accepted,'finished':finished,'scrap_simulated':completed_scrap,
        'not_accepted':s['release_units']-accepted,
        'throughput_units_hour':round(throughput,2),
        'avg_flow_s':round(sum(x['flow_s'] for x in accepted_times)/accepted,1) if accepted else None,
        'first_accepted_s':accepted_times[0]['t'] if accepted else None,
        'accepted_lot_ids':[row['lot'] for row in accepted_times],
        'theoretical_critical_path_s':round(max_path[customer],1),
        'critical_path_nodes':critical,
        'potential_bottleneck':{'id':bottleneck,'name':nodes[bottleneck]['name'],
                                'cycle_s':nodes[bottleneck]['cycle_s'],'takt_s':s['takt_s']},
        'operations':by_operation,
        'transport':{'trips_simulated':deliveries,'tokens_moved':transported,
                     'seconds_busy_assumed':round(trip_seconds,1), 'assumed_trip_time_s':s.get('travel_s',0),
                     'measured_route_distance_m':None},
        'financial':finance,
        'timeline':accepted_times,
        'warnings':[
            'Происхождение времён пользовательской/синтетической модели не подтверждено организаторами.' if synthetic else 'Операционные времена — нормативные суммы рабочих стандартов, НЕ фактический хронометраж.',
            'Маршруты пользовательской/синтетической модели требуют отдельного подтверждения.' if synthetic else 'Технологические связи между операциями восстановлены по текстам стандартов и требуют подтверждения экспертами.',
            'Начальные подсборки и НЗП в сценарии не заданы; комплектующие условно доступны в момент запуска.',
            'Нулевое время транспортировки и 0% дефектов — технические допущения, НЕ наблюдения на фабрике.'
              if not any(n.get('defect_pct') for n in nodes.values()) and s.get('travel_s')==0 else
              'Параметры транспортировки и брака относятся к сценарию, а не к подтверждённым замерам.',
            'Результат имитации НЕ равен фактическому ВПП согласно МУ-17-2023: для ВПП нужны наблюдения ожиданий и перевозок.'
        ],
        'data_status':'synthetic_only' if synthetic else 'normative_plus_hypothetical_graph',
    }


def compare(baseline,scenario):
    a=simulate(baseline);b=simulate(scenario)
    keys=['accepted','throughput_units_hour','avg_flow_s','not_accepted','theoretical_critical_path_s']
    delta={}
    for key in keys:
        x,y=a[key],b[key]
        delta[key]={'before':x,'after':y,'difference':round(y-x,2) if x is not None and y is not None else None}
    return {'baseline':a,'scenario':b,'delta':delta,
            'caveat':'Изменения — сценарный результат модели, не подтверждённый эффект внедрения.'}
