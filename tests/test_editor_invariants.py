"""Regression tests for layout independence, provenance and AND-joins."""
import copy
import json
import unittest
from pathlib import Path
from backend.engine import simulate
from backend.model import validate, ModelError

DATA=Path(__file__).parents[1]/'data'
BASE=json.loads((DATA/'venio_factory.json').read_text('utf8'))


class EditorInvariantTests(unittest.TestCase):
    def test_drag_coordinates_do_not_change_a_single_simulation_result(self):
        moved=copy.deepcopy(BASE)
        moved['kpsc_layout']={'o1':{'x':300,'y':300},'o8':{'x':1200,'y':600}}
        validate(moved)
        self.assertEqual(simulate(BASE),simulate(moved))
        self.assertEqual(BASE['edges'],moved['edges'])

    def test_reject_unknown_map_node(self):
        m=copy.deepcopy(BASE)
        m['kpsc_layout']={'fake':{'x':300,'y':100}}
        with self.assertRaisesRegex(ModelError,'неизвестный узел'):
            validate(m)

    def test_reject_bad_map_coordinates(self):
        for bad in ('a',-2,float('nan'),float('inf'),10001):
            m=copy.deepcopy(BASE)
            m['kpsc_layout']={'o1':{'x':bad,'y':200}}
            with self.subTest(value=bad),self.assertRaises(ModelError):validate(m)

    def test_takt_is_derived_from_shift_and_demand(self):
        m=copy.deepcopy(BASE)
        m['settings']['shift_s']=1500
        with self.assertRaisesRegex(ModelError,'ФДВ/спросу'):validate(m)
        m['settings']['takt_s']=150
        validate(m)

    def test_joins_never_pair_different_product_ids_after_scrap(self):
        nodes=[
            {'id':'source','kind':'source','name':'Склад'},
            {'id':'a','kind':'operation','name':'A','cycle_s':2,'workers':1,'defect_pct':50},
            {'id':'b','kind':'operation','name':'B','cycle_s':3,'workers':1,'defect_pct':0},
            {'id':'join','kind':'operation','name':'Сборка','cycle_s':1,'workers':1,'defect_pct':0},
            {'id':'qc','kind':'quality','name':'ОТК','cycle_s':1,'workers':1,'defect_pct':0},
            {'id':'buyer','kind':'customer','name':'Клиент'},
        ]
        edges=[{'from':a,'to':b} for a,b in [('source','a'),('source','b'),('a','join'),('b','join'),('join','qc'),('qc','buyer')]]
        settings=dict(BASE['settings'])
        settings.update(shift_s=200,target_units=4,release_units=4,takt_s=50,transport_batch=1,seed=1)
        m=dict(id='independent-example',status='synthetic_demo',name='Тест',nodes=nodes,edges=edges,settings=settings)
        r=simulate(m)
        # For this reproducible random seed, A scraps lots 0 and 2.
        # The old engine could combine a remaining A lot with the wrong B lot.
        self.assertEqual(r['accepted_lot_ids'],[1,3])
        self.assertEqual(r['accepted'],2)
        self.assertEqual(r['scrap_simulated'],2)

    def test_no_financial_figure_when_inputs_missing(self):
        result=simulate(BASE)
        self.assertEqual(result['financial']['status'],'insufficient_data')
        self.assertIsNone(result['financial']['profit'])

if __name__=='__main__':unittest.main()
