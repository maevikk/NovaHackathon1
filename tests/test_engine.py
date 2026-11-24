from __future__ import annotations
import unittest, json, copy
from pathlib import Path
from backend.engine import simulate, compare
from backend.model import validate, ModelError
D=Path(__file__).parents[1]/'data'
MODEL=json.loads((D/'venio_factory.json').read_text('utf8'))
GENERIC=json.loads((D/'generic_example.json').read_text('utf8'))

class EngineTests(unittest.TestCase):
 def test_sources_and_norms(self):
  g=validate(MODEL)
  cycles={n['id']:n['cycle_s'] for n in g['nodes'].values() if n['kind'] in {'operation','quality'}}
  self.assertEqual(cycles,{'o1':83,'o2':66,'o3':13,'o4':61,'o5':35,'o6':39,'o7':102,'o8':171,'o9':82,'qc':22})
  self.assertEqual(len([n for n in g['nodes'].values() if n['kind']=='operation']),9)
  self.assertEqual(len([n for n in g['nodes'].values() if n['kind']=='quality']),1)
 def test_logist_supplies_nine_workplaces(self):
  supplied={e['to'] for e in MODEL['edges'] if e['from']=='wh'}
  self.assertEqual(supplied,{f'o{x}' for x in range(1,10)})
 def test_case_one_takt_bottleneck(self):
  r=simulate(MODEL)
  self.assertEqual(r['potential_bottleneck']['id'],'o8')
  self.assertEqual(r['potential_bottleneck']['cycle_s'],171)
  self.assertEqual(r['potential_bottleneck']['takt_s'],120)
  self.assertEqual(r['theoretical_critical_path_s'],587)
  self.assertLessEqual(r['accepted'],MODEL['settings']['target_units'])
  self.assertTrue(r['operations'][7]['risk_above_takt']) if r['operations'][7]['id']=='o8' else self.assertTrue(next(x for x in r['operations'] if x['id']=='o8')['risk_above_takt'])
 def test_reproducible(self):
  self.assertEqual(simulate(MODEL),simulate(copy.deepcopy(MODEL)))
 def test_info_not_material(self):
  changed=copy.deepcopy(MODEL)
  changed['info_flow']=[{'from':'qc','to':'wh','message':'Пример сигнала'}]
  self.assertEqual(simulate(MODEL),simulate(changed))
 def test_actual_wip_not_claimed(self):
  r=simulate(MODEL)
  self.assertNotIn('measured_wip_units',r)
  self.assertIsNone(r['transport']['measured_route_distance_m'])
 def test_finance_missing_is_null(self):
  r=simulate(MODEL)
  self.assertEqual(r['financial']['status'],'insufficient_data')
  self.assertIsNone(r['financial']['profit'])
 def test_finance_filled_works(self):
  m=copy.deepcopy(MODEL)
  m['settings'].update({'unit_material_cost':1,'unit_sale_price':10,'labor_cost_shift':2,'logistic_cost_shift':1,'overhead_cost_shift':1})
  r=simulate(m)
  self.assertEqual(r['financial']['profit'],r['accepted']*10-10-2-1-1)
 def test_scenario_comparison(self):
  c=copy.deepcopy(MODEL);next(x for x in c['nodes'] if x['id']=='o8')['cycle_s']=120
  output=compare(MODEL,c)
  self.assertEqual(output['baseline']['potential_bottleneck']['cycle_s'],171)
  self.assertEqual(output['scenario']['potential_bottleneck']['cycle_s'],120)
  self.assertEqual(output['delta']['accepted']['difference'],output['scenario']['accepted']-output['baseline']['accepted'])
 def test_extensible_to_generic_example(self):
  g=simulate(GENERIC)
  self.assertEqual(len(g['operations']),3)
  self.assertTrue(g['accepted']>=0)
 def test_transport_policy_can_change(self):
  m=copy.deepcopy(MODEL);m['settings']['transport_policy']='max'
  self.assertNotEqual(simulate(MODEL)['transport']['trips_simulated'],simulate(m)['transport']['trips_simulated'])
 def test_reject_cycle(self):
  m=copy.deepcopy(MODEL);m['edges'].append({'from':'o9','to':'o3'})
  with self.assertRaisesRegex(ModelError,'цикл'):validate(m)
 def test_bad_inputs(self):
  for field,bad in [('cycle_s',0),('cycle_s',float('nan')),('workers',1.5),('defect_pct',-1)]:
   m=copy.deepcopy(MODEL);next(n for n in m['nodes'] if n['id']=='o8')[field]=bad
   with self.subTest(field=field,bad=bad),self.assertRaises(ModelError):validate(m)
 def test_duplicate_edges(self):
  m=copy.deepcopy(MODEL);m['edges'].append(copy.deepcopy(m['edges'][0]))
  with self.assertRaises(ModelError):validate(m)
 def test_missing_source_to_destination(self):
  m=copy.deepcopy(MODEL);m['edges']=[e for e in m['edges'] if not(e['from']=='o8' and e['to']=='o9')]
  with self.assertRaises(ModelError):validate(m)
 def test_extremely_large_graph_blocked(self):
  m=copy.deepcopy(MODEL);m['nodes']*=8
  with self.assertRaises(ModelError):validate(m)

if __name__=='__main__':unittest.main()
