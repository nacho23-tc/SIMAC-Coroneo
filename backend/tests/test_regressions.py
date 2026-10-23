from backend.tests.support import TEMP_ROOT
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from backend import main
from backend.model_registry import classify, models, write_json
from backend.tests.test_yield_experiment import sample
from backend.validation import validate_payload


class RegressionTests(unittest.TestCase):
    def test_bad_input_returns_validation_error(self):
        invalid=[{}, {'result':'bad'}, {'result':{'sample':'x','unit':'mm','grains':[None]}}]
        data=sample();data['result']['grains'][0]['area']=float('nan');invalid.append(data)
        data=sample();data['metadata']['key']=[];invalid.append(data)
        data=sample();data['review']['reviewed']='false';invalid.append(data)
        data=sample();data['result']['grains'][1]['grano']=1;invalid.append(data)
        for payload in invalid:
            with self.subTest(payload_type=str(type(payload))):
                with self.assertRaises(HTTPException) as caught:main.summarize_result(payload)
                self.assertEqual(caught.exception.status_code,422)
        self.assertIs(validate_payload(sample())['review']['reviewed'],True)

    def test_missing_or_broken_model_does_not_break_results(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder:
            root=Path(folder);directory=root/'yield_models';directory.mkdir()
            (directory/'active.json').write_text('{"id":"invalid"}',encoding='utf-8')
            (directory/'broken.json').write_text('not json',encoding='utf-8')
            self.assertEqual(classify(root,sample())['status'],'unavailable')
            listing=models(root)
            self.assertEqual(listing['models'],[])
            self.assertTrue(listing['warnings'])
            (directory/'active.json').write_text('bad json',encoding='utf-8')
            self.assertIsNone(models(root)['active_id'])

    def test_atomic_model_selection_writes(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder:
            path=Path(folder)/'active.json'
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda i:write_json(path,{'id':i}),range(20)))
            self.assertIn(json.loads(path.read_text())['id'],range(20))
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])

    def test_explicit_unmatched_metadata_does_not_use_another_catalog(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder,patch.object(main,'HISTORY_PATH',Path(folder)/'samples.sqlite3'),patch.object(main,'METADATA_PATH',Path(folder)/'metadata.json'):
            data=sample();data['metadata']=None;data['metadata_selection']='explicit';data['weight_inputs']={'mode':'auto'}
            main.METADATA_PATH.write_text(json.dumps({'columns':['nombre_nuevo','Weight_50K'],'rows':[{'nombre_nuevo':'F0','Weight_50K':100}]}),encoding='utf-8')
            self.assertEqual(main.result_summary(data)['weight']['status'],'scenario')


class CompressedSaveTests(unittest.TestCase):
    def test_large_compressed_save_preserves_results(self):
        import gzip, io
        from starlette.datastructures import UploadFile
        data=sample();data['padding']='x'*(41*1024*1024)
        raw=json.dumps(data).encode()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder, patch.object(main,'HISTORY_PATH',Path(folder)/'samples.sqlite3'), patch.object(main,'result_summary',return_value={'weight':{}}):
            saved=main.save_sample(UploadFile(filename='sample.jpg',file=io.BytesIO(b'photo')),UploadFile(filename='result.json.gz',file=io.BytesIO(gzip.compress(raw))),identifier='')
            with main.history_db() as db:
                stored=json.loads(db.execute('SELECT payload FROM samples WHERE id=?',(saved['id'],)).fetchone()[0])
            self.assertEqual(stored['result'],data['result'])
            self.assertEqual(len(stored['padding']),41*1024*1024)

    def test_corrupt_compressed_save_returns_validation_error(self):
        import io
        from starlette.datastructures import UploadFile
        with self.assertRaises(HTTPException) as error:
            main.save_sample(UploadFile(filename='x.jpg',file=io.BytesIO(b'x')),UploadFile(filename='x.gz',file=io.BytesIO(b'\x1f\x8bgarbage')),identifier='')
        self.assertEqual(error.exception.status_code,422)
