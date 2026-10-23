from backend.tests.support import TEMP_ROOT
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from backend import main
from backend.yield_experiment import family


class LocalRecordsTests(unittest.TestCase):
    def test_register_preserves_rows_and_normalizes_yield(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder, patch.object(main,'METADATA_PATH',Path(folder)/'metadata.json'):
            first=main.register_local_metadata({'nombre_nuevo':'Coroneo_01','Yield':'1500','unidad_rendimiento':'kg/ha','Weight_50K':'15','localidad':'Coroneo'})
            self.assertEqual(first['rows'][0]['Yield'],'1.5')
            main.register_local_metadata({'nombre_nuevo':'Coroneo_02'})
            self.assertEqual(len(json.loads(main.METADATA_PATH.read_text())['rows']),2)
            with self.assertRaises(HTTPException):main.register_local_metadata({'nombre_nuevo':'Coroneo_01'})
            with self.assertRaises(HTTPException):main.register_local_metadata({'nombre_nuevo':'Bad','Weight_50K':'nan'})

    def test_saved_metadata_reference_not_measured_photo_weight(self):
        from backend.tests.test_yield_experiment import sample
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder, patch.object(main,'METADATA_PATH',Path(folder)/'metadata.json'),patch.object(main,'HISTORY_PATH',Path(folder)/'samples.sqlite3'):
            main.register_local_metadata({'nombre_nuevo':'Grano_01.jpg','Weight_50K':'15'})
            payload=sample();payload['result']['sample']='Grano1';payload.pop('metadata');payload['weight_inputs']={'mode':'auto'}
            summary=main.result_summary(payload)
            self.assertEqual(summary['weight']['total_g'],7.5)
            self.assertEqual(summary['weight']['status'],'estimated')
            self.assertEqual(family('Grano_01.jpg'),family('Grano1'))
