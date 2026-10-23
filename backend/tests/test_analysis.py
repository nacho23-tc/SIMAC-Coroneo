import unittest
from PIL import Image, ImageDraw
from backend.analysis import analyze


class AnalysisTests(unittest.TestCase):
    def run_analysis(self, image, **overrides):
        args = dict(method="classical", roi=(0, 0, 1, 1), diameter=None, min_area=30,
                    max_side=400, scale_pixels=None, scale_mm=None, sample="Prueba")
        args.update(overrides)
        return analyze(image, **args)

    def sample(self):
        image = Image.new("RGB", (800, 400), "black")
        draw = ImageDraw.Draw(image)
        draw.ellipse((100, 100, 200, 250), fill="#e2c975")
        draw.ellipse((400, 100, 500, 250), fill="#e2c975")
        return image

    def test_count_and_scale(self):
        px = self.run_analysis(self.sample())
        mm = self.run_analysis(self.sample(), scale_pixels=100, scale_mm=10)
        self.assertEqual(px["count"], 2)
        self.assertEqual(mm["unit"], "mm")
        self.assertAlmostEqual(px["mean_length"] / 10, mm["mean_length"], places=2)
        self.assertAlmostEqual(px["mean_area"] / 100, mm["mean_area"], places=2)

    def test_blank_is_not_a_seed(self):
        result = self.run_analysis(Image.new("RGB", (300, 300), "white"))
        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["mean_length"])

    def test_crop_and_formula_escape(self):
        result = self.run_analysis(self.sample(), roi=(0, 0, .4, 1), sample="=1+1")
        self.assertEqual(result["count"], 1)
        self.assertIn("'=1+1", result["csv"])


if __name__ == "__main__":
    unittest.main()
