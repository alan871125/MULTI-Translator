from pathlib import Path
from core.text_unit import TextUnit
from core.engines.ck3 import Extractor

import pandas as pd

class TestCK3Extractor:
    folder_path = Path("test/.data/ck3/")
    output_folder = Path("test/.output/ck3/")
    units: list[TextUnit] = []
    
    @classmethod
    def test_extract_mod(cls):
        extractor = Extractor()
        cls.units = extractor.extract_dir(cls.folder_path)
        
    def test_apply_mod(self):
        # Modify translations for testing
        df = pd.DataFrame(self.units)
        df['translation'] = '(Translated) ' + df['original']
        extractor = Extractor()
        extractor.apply_translations(
            self.folder_path, df, save_path=self.output_folder, target_lang="spanish")

        units = extractor.extract_dir(self.output_folder, source_lang='spanish', target_lang='spanish')
        df_out = pd.DataFrame(units)
        # Verify that translations were applied correctly
        assert sum(df_out['original']!=df['translation']) == 0, "Not all translations were applied correctly."

if __name__ == "__main__":
    test = TestCK3Extractor()
    test.test_extract_mod()
    test.test_apply_mod()