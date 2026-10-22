import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class InstallTests(unittest.TestCase):
    def test_installs_only_plugin_into_explicit_home_and_refuses_overwrite(self):
        spec = importlib.util.spec_from_file_location('install_plugin', ROOT / 'scripts/install_plugin.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as temp:
            home = Path(temp)
            result = module.install(home)
            self.assertEqual(result, home / 'plugins/slack-board')
            self.assertTrue((result / '__init__.py').is_file())
            self.assertTrue((result / 'controller.py').is_file())
            from ruamel.yaml import YAML
            manifest = YAML(typ='safe').load((result / 'plugin.yaml').read_text())
            self.assertEqual(manifest['name'], 'slack-board')
            self.assertEqual(manifest['requires_hermes'], '>=0.22.4,<0.23')
            self.assertEqual(sorted(p.name for p in home.iterdir()), ['plugins'])
            with self.assertRaises(FileExistsError):
                module.install(home)
