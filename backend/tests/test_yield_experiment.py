import unittest
from backend.yield_experiment import IMAGE, META, TARGET, inventory, prepare
from backend.svm_experiment import run, FORBIDDEN


def sample(i=0):
    return {"result": {"sample": f"F{i}", "unit": "mm", "grains": [{"unidad": "mm", "grano": j+1, **{v: 1+i*.1+j*.001 for v in IMAGE.values()}} for j in range(25)]},
            "review": {"reviewed": True}, "parameters": {"photoType": "grains"},
            "metadata": {"key": "nombre_imagen", "identifier": f"F{i}.jpg", "rows": [{"nombre_imagen": f"F{i}.jpg", TARGET: i+1, **{c: i+2 for c in META}}]}}


def records():
    return [(str(i), sample(i)) for i in range(12)]


class YieldTests(unittest.TestCase):
    def test_target_never_predictor(self):
        row = prepare(sample())
        self.assertTrue(row["training_ready"])
        self.assertTrue(all(v not in row["features"] for v in FORBIDDEN))
        self.assertEqual(len(row["features"]), 21)

    def test_uncalibrated_unreviewed_duplicate(self):
        data = sample(); data["result"]["unit"] = "px"; data["review"]["reviewed"] = False
        self.assertFalse(prepare(data)["ready"])
        self.assertTrue(all(not r["ready"] for r in inventory([("a", sample()), ("b", sample())], "imagen")))

    def test_missing_target_predict_only_and_class_ignored(self):
        data = sample(); data["metadata"]["rows"][0]["Class"] = "incorrecta"
        self.assertTrue(prepare(data)["training_ready"])
        del data["metadata"]["rows"][0][TARGET]
        self.assertTrue(prepare(data)["ready"])
        self.assertFalse(prepare(data)["training_ready"])

    def test_nonfinite_metadata_block(self):
        data = sample(); data["metadata"]["rows"][0][META[0]] = "NaN"
        self.assertFalse(prepare(data)["ready"])

    def test_insufficient_data_and_quality_controls(self):
        self.assertEqual(run([("a", sample())])["status"], "blocked")
        report = run(records(), min_grains=26)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(all(not r["ready"] for r in report["samples"]))
        self.assertFalse(run(records(), excluded=["F0"])["samples"][0]["ready"])

    def test_split_and_threshold_do_not_see_test_yields(self):
        data = records(); report = run(data)
        self.assertEqual(report["status"], "completed")
        self.assertFalse(set(report["train_ids"]) & set(report["test_ids"]))
        self.assertEqual(report["test_metrics"]["total"], 4)
        for identifier, payload in data:
            if identifier in report["test_ids"]:
                payload["metadata"]["rows"][0][TARGET] = 10000
        changed = run(data)
        self.assertEqual(report["threshold"], changed["threshold"])
        self.assertEqual(report["parameters"], changed["parameters"])
        self.assertEqual([r["predicted"] for r in report["test"]], [r["predicted"] for r in changed["test"]])

    def test_all_kernels_and_nested_selection(self):
        report = run(records(), kernel="auto", nested=True)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(len(report["comparison"]), 5)
        self.assertIsNotNone(report["nested"])
        self.assertEqual(report["validation_metrics"]["total"], 2*report["pair_count"])
        self.assertNotIn("prob_alto", report["test"][0])

    def test_invalid_configuration(self):
        for args in [{"c": float("nan")}, {"kernel": "bad"}, {"threshold": -1}, {"gamma": "bad"}]:
            with self.assertRaises(ValueError): run(records(), **args)
