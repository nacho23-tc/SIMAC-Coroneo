import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from backend import agriculture as ag, main
from backend.tests.support import TEMP_ROOT


class AgricultureTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.path=Path(self.folder.name)/'samples.sqlite3'
        self.material={'code':'M1','name':'Maíz rojo','municipality':'Coroneo, Guanajuato','locality':'Acatlán'}
        self.plot={'code':'P1','material_code':'M1','season':'2026','site':'Acatlán','sown_date':'2026-05-01','area_m2':100}
    def tearDown(self):self.folder.cleanup()
    def seed(self,db):
        ag.write(db,'materials',self.material);ag.write(db,'plots',self.plot)
    def test_yield_moisture_and_flowering_units(self):
        with ag.database(self.path) as db:
            self.seed(db)
            obs=ag.write(db,'observations',{'code':'O1','plot_code':'P1','observed_date':'2026-10-01','anthesis_date':'2026-07-01','harvest_kg':50,'harvest_area_m2':100,'moisture_pct':20,'reference_moisture_pct':14})
            d=ag.derived(db,obs)
            self.assertAlmostEqual(d['yield_t_ha'],50*10/100*80/86,places=5)
            self.assertEqual(d['days_to_anthesis'],61)
            plain=ag.derived(db,{k:v for k,v in obs.items() if k not in ('moisture_pct','reference_moisture_pct')})
            self.assertEqual(plain['yield_t_ha'],5)
    def test_invalid_measurements_and_links(self):
        with ag.database(self.path) as db:
            self.seed(db)
            base={'code':'O1','plot_code':'P1','observed_date':'2026-10-01'}
            for extra in [{'height_cm':'nan'},{'ears_count':1.5},{'height_cm':True},{'harvest_kg':3},{'harvest_kg':1,'harvest_area_m2':101},{'moisture_pct':100,'reference_moisture_pct':14},{'anthesis_date':'2027-01-01'},{'observed_date':'2026-04-01'},{'observed_date':'20261001'},{'plot_code':'missing'}]:
                with self.subTest(extra=extra),self.assertRaises(ValueError):ag.write(db,'observations',{**base,**extra})
    def test_updates_preserve_observation_consistency(self):
        with ag.database(self.path) as db:
            self.seed(db);ag.write(db,'observations',{'code':'O1','plot_code':'P1','observed_date':'2026-07-01','harvest_kg':2,'harvest_area_m2':90})
            with self.assertRaises(ValueError):ag.write(db,'plots',{**self.plot,'area_m2':50},True)
            with self.assertRaises(ValueError):ag.write(db,'plots',{**self.plot,'sown_date':'2026-08-01'},True)
    def test_import_failure_rolls_back_entire_file(self):
        text='code,name,municipality,locality\nM1,Maíz,Coroneo,Acatlán\nM2,Maíz,,Acatlán\n'
        with self.assertRaises(ValueError):
            with ag.database(self.path) as db:ag.import_csv(db,'materials',text.encode())
        with ag.database(self.path) as db:self.assertIsNone(ag.get(db,'materials','M1'))
    def test_csv_roundtrip_duplicate_and_formula_escape(self):
        with ag.database(self.path) as db:
            ag.write(db,'materials',{**self.material,'name':'=1+1'})
            out=ag.csv_text(db,'materials')
            self.assertIn("'=1+1",out)
            with self.assertRaises(FileExistsError):ag.write(db,'materials',self.material)
            ag.write(db,'materials',{**self.material,'name':'Cambio'},True)
            self.assertEqual(len(ag.overview(db)['records']['materials']),1)
            template=ag.csv_text(db,'materials',True)
            self.assertEqual(len(list(csv.reader(io.StringIO(template.lstrip('\ufeff'))))),1)
    def test_crosses_and_documented_families(self):
        with ag.database(self.path) as db:
            with self.assertRaises(ValueError):ag.write(db,'materials',{**self.material,'family_code':'F1'})
            ag.write(db,'families',{'code':'F1','name':'Familia 1','basis':'Registro del productor'})
            ag.write(db,'materials',{**self.material,'family_code':'F1'})
            ag.write(db,'materials',{**self.material,'code':'M2'})
            row={'code':'C1','mother_code':'M1','father_code':'M2','date':'2026-10-17','status':'planned'}
            ag.write(db,'crosses',row)
            with self.assertRaises(ValueError):ag.write(db,'crosses',{**row,'code':'C2','father_code':'M1'})
            self.assertEqual(ag.get(db,'crosses','C1')['status'],'planned')
    def test_readiness_counts_plots_not_only_rows(self):
        with ag.database(self.path) as db:
            self.seed(db)
            for i in range(2):ag.write(db,'observations',{'code':f'O{i}','plot_code':'P1','observed_date':'2026-07-01','height_cm':100+i})
            metric=next(r for r in ag.overview(db)['readiness'] if r['target']=='Altura medida')
            self.assertEqual((metric['records'],metric['plots'],metric['families']),(2,1,0))
    def test_routes_and_validation(self):
        with patch.object(main,'HISTORY_PATH',self.path):
            routes={route.name:route.endpoint for route in ag.router(lambda:self.path).routes}
            self.assertEqual(routes['records']()['records']['materials'],[])
            routes['create']('materials',self.material)
            with self.assertRaises(HTTPException) as caught:routes['create']('materials',self.material)
            self.assertEqual(caught.exception.status_code,409)
            with self.assertRaises(HTTPException) as caught:routes['update']('materials','M1',{**self.material,'code':'M2'})
            self.assertEqual(caught.exception.status_code,422)
            with self.assertRaises(HTTPException):routes['export']('unknown',False)
            self.assertIn('Maíz rojo',routes['export']('materials',False).body.decode())
            with self.assertRaises(HTTPException):routes['create']('materials',{**self.material,'code':'M2','sample_id':'missing'})
