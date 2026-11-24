from pathlib import Path
from csv import DictReader
import unittest,json
from xml.etree import ElementTree as ET
ROOT=Path(__file__).parents[1]
class SourceTests(unittest.TestCase):
 def test_normative_sum_csv(self):
  with (ROOT/'analysis/data/source_reconciliation.csv').open('r',encoding='utf8') as fp:
   rows=list(DictReader(fp))
  self.assertEqual(len(rows),10)
  for row in rows:
   self.assertEqual(sum(map(int,row['шаги_секунды'].split('+'))),int(row['сумма_нормы_секунды']))
   self.assertEqual(row['статус_источника'],'норматив рабочего стандарта')
   self.assertEqual(row['статус_факта'],'не измерено')
   self.assertEqual(row['факт_цикл_секунды'],'')
 def test_stage1_store_matches_engine(self):
  import sqlite3,sys
  sys.path.insert(0,str(ROOT))
  from analysis.build_stage1_store import build_database
  path=ROOT/'data'/'venio_stage1.sqlite'
  build_database(path)
  connection=sqlite3.connect(path)
  query='select id, accepted, theoretical_critical_path_s, bottleneck_cycle_s, finance_status from scenario_result'
  rows={row[0]:row[1:] for row in connection.execute(query)}
  self.assertEqual(rows['baseline'],(1,587.0,171.0,'insufficient_data'))
  self.assertEqual(rows['scenario'][0],2)
  self.assertEqual(rows['scenario'][2],120.0)
  self.assertEqual(connection.execute('select count(*) from node').fetchone()[0],12)
 def test_bpmn_xml_valid(self):
  root=ET.parse(ROOT/'analysis/diagrams/as_is.bpmn').getroot()
  self.assertEqual(root.tag.split('}')[-1],'definitions')
  self.assertEqual(len(root.findall('.//{*}sequenceFlow')),17)
 def test_svg_editable(self):
  ET.parse(ROOT/'analysis/diagrams/as_is_kpsc.svg')
  ET.parse(ROOT/'analysis/diagrams/to_be_hypothesis.svg')
  ET.parse(ROOT/'analysis/diagrams/kpsc_current.svg')
  ET.parse(ROOT/'analysis/diagrams/kpsc_ideal.svg')
  ET.parse(ROOT/'analysis/diagrams/kpsc_target.svg')
 def test_schema_both_datasets(self):
  s=json.loads((ROOT/'data/schema.json').read_text('utf8'))
  self.assertEqual(s['properties']['schema_version']['const'],4)
  for f in ['venio_factory.json','generic_example.json']:
   m=json.loads((ROOT/'data'/f).read_text('utf8'))
   self.assertEqual(m['schema_version'],4)
if __name__=='__main__':unittest.main()
