import pandas as pd
from pathlib import Path
from core.text_unit import TextUnit
from plugins.rimworld.extractor import RimWorldExtractor, parse_xml_to_dict


class TestRimWorldExtractor:
    folder_path = Path("test/.data/rimworld/Languages/English")
    output_folder = Path("test/.output/rimworld/")
    units: list[TextUnit] = []
    @classmethod
    def test_extract_mod(cls):
        extractor = RimWorldExtractor()
        cls.units = extractor.extract_file(cls.folder_path)
        
    def test_apply_mod(self):
        # Modify translations for testing
        df = pd.DataFrame(self.units)
        df['translation'] = '(Translated) ' + df['original']
        extractor = RimWorldExtractor()
        extractor.apply_translations(self.folder_path, df, save_path=self.output_folder)

        units = extractor.extract_file(self.output_folder/"Languages/English")
        df_out = pd.DataFrame(units)
        # Verify that translations were applied correctly
        assert sum(df_out['original']!=df['translation']) == 0, "Not all translations were applied correctly."
        # remove the output file after test
        
if __name__ == "__main__":
    test = TestRimWorldExtractor()
    test.test_extract_mod()
    test.test_apply_mod()