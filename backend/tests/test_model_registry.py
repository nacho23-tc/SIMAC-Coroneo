from backend.tests.support import TEMP_ROOT
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.model_registry import activate, classify, models, save_candidate
from backend.svm_experiment import run
from backend.tests.test_yield_experiment import records, sample


class ModelRegistryTests(unittest.TestCase):
    def test_save_activate_predict_without_retraining_and_rollback(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root:
            report = run(records(), artifact_sink=lambda fitted, meta: save_candidate(root, fitted, meta))
            version = report['model_version']
            self.assertIsNone(models(root)['active_id'])
            self.assertEqual(classify(root, sample())['status'], 'pending')
            activate(root, version)
            new = sample(20)
            new.pop('metadata')
            with patch('backend.svm_experiment.run', side_effect=AssertionError('No debe reentrenar')):
                prediction = classify(root, new)
            self.assertEqual(prediction['status'], 'experimental')
            self.assertIn(prediction['label'], ['Alto','Bajo'])
            self.assertTrue(prediction['outside_training_range'])
            again = run(records(), kernel='linear', artifact_sink=lambda fitted, meta: save_candidate(root, fitted, meta))
            activate(root, again['model_version'])
            activate(root, version)
            self.assertEqual(models(root)['active_id'], version)
            path = Path(root)/'yield_models'/(version+'.joblib')
            path.write_bytes(path.read_bytes()+b'changed')
            self.assertEqual(classify(root, new)['status'], 'pending')

    def test_summary_fallback_and_real_weight(self):
        from backend import main
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as root, patch.object(main,'HISTORY_PATH',Path(root)/'samples.sqlite3'):
            data=sample();data['weight_inputs']={'mode':'auto'}
            summary=main.result_summary(data)
            self.assertEqual(summary['yield']['status'],'pending')
            self.assertEqual(summary['weight']['status'],'scenario')
            data['weight_inputs']={'mode':'lot','mass_g':'7','count':'25','lot':'L1','measured':True,
                'grain_signature':[[g[k] for k in ['grano','largo','ancho','area']] for g in data['result']['grains']]}
            self.assertEqual(main.result_summary(data)['weight']['status'],'measured')
