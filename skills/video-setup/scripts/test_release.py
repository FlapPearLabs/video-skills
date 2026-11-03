import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_release as release


class ReleaseBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.root=Path(__file__).resolve().parents[2]
        cls.result=release.build(cls.root,Path(cls.tmp.name)/'out','test-author')
        cls.skills=release.resolve(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_collection_contains_six_individual_uploads(self):
        with zipfile.ZipFile(self.result['runtime_bundle']) as z:
            self.assertIn('INSTALL.md',z.namelist())
            self.assertNotIn('SKILL.md',z.namelist())
            self.assertEqual(len([n for n in z.namelist() if n.endswith('.zip')]),6)
            manifest=json.loads(z.read('RELEASE.json'))
            self.assertEqual(manifest['workbuddy_import'],'not_tested')
        with zipfile.ZipFile(self.result['development_bundle']) as z:
            self.assertEqual(json.loads(z.read('RELEASE.json'))['format'],'development-source-six-skills')

    def test_each_upload_has_one_self_contained_skill(self):
        for name in release.NAMES:
            path=Path(self.result['runtime_bundle']).parent/'workbuddy'/(name+'-v0.1.1.zip')
            with zipfile.ZipFile(path) as z:
                self.assertIsNone(z.testzip())
                self.assertEqual({n.split('/')[0] for n in z.namelist()},{name})
                entries={n[len(name)+1:]:z.read(n) for n in z.namelist()}
                self.assertTrue(release.validate_entries(name,entries))
                metadata,body=release.parse(entries['SKILL.md'].decode())
                self.assertEqual(metadata['version'],'0.1.1')
                self.assertEqual(metadata['author'],'test-author')
                self.assertIn('@references/project-contract.md',body)
                self.assertNotIn('](references/',body)

    def test_runtime_omits_development_and_private_identifiers(self):
        for name,folder in self.skills.items():
            entries=release.runtime_entries(name,folder,'0.1.1','test-author')
            self.assertFalse(any('evaluation' in n or 'test_' in n or 'build_release' in n or n.startswith('agents/') for n in entries))
            self.assertFalse(any(b'feedbeeffeedbeeffeedbeeffeedbeef' in b for b in entries.values()))

    def test_source_frontmatter_remains_generic(self):
        for folder in self.skills.values():
            metadata,_=release.parse((folder/'SKILL.md').read_text())
            self.assertEqual(set(metadata),{'name','description'})

    def test_missing_workbuddy_field_rejected(self):
        entries=release.runtime_entries('video-grill',self.skills['video-grill'],'0.1.1','test-author')
        entries['SKILL.md']=entries['SKILL.md'].replace(b'author: test-author\n',b'')
        with self.assertRaisesRegex(ValueError,'author'):
            release.validate_entries('video-grill',entries)

    def test_missing_reference_rejected(self):
        entries=release.runtime_entries('video-grill',self.skills['video-grill'],'0.1.1','test-author')
        del entries['references/project-contract.md']
        with self.assertRaisesRegex(ValueError,'missing resource'):
            release.validate_entries('video-grill',entries)

    def test_shared_drift_rejected_and_sync_restores(self):
        with tempfile.TemporaryDirectory() as td:
            skills={}
            for name,folder in self.skills.items():
                dest=Path(td)/name
                shutil.copytree(folder,dest,ignore=shutil.ignore_patterns('__pycache__'))
                skills[name]=dest
            target=skills['video-grill']/'references/project-contract.md'
            target.write_text('drift')
            with self.assertRaisesRegex(ValueError,'shared file drift'):
                release.check_shared(skills)
            release.sync(skills)
            release.check_shared(skills)

    def test_exported_scripts_run_from_another_working_directory(self):
        for name,script in [('video-setup','project_files.py'),('video-implement','operation_guard.py')]:
            entries=release.runtime_entries(name,self.skills[name],'0.1.1','test-author')
            with tempfile.TemporaryDirectory() as td:
                base=Path(td)/name
                for rel,data in entries.items():
                    path=base/rel
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(data)
                result=subprocess.run([sys.executable,str(base/'scripts'/script),'--help'],cwd=td,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)

    def test_reused_output_directory_does_not_include_stale_archive(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            (out/'workbuddy').mkdir()
            stale=out/'workbuddy/video-setup-v0.1.0.zip'
            with zipfile.ZipFile(stale,'w') as z:
                z.writestr('marker.txt','not a current release')
            result=release.build(self.root,out,'test-author')
            with zipfile.ZipFile(result['runtime_bundle']) as z:
                self.assertNotIn('workbuddy/'+stale.name,z.namelist())
                self.assertEqual(len([n for n in z.namelist() if n.endswith('.zip')]),6)

    def test_private_project_id_hyphenated_form_rejected(self):
        entries=release.runtime_entries('video-grill',self.skills['video-grill'],'0.1.1','test-author')
        entries['references/project-contract.md']+=b'\nFEEDBEEF-FEED-BEEF-FEED-BEEFFEEDBEEF\n'
        with self.assertRaisesRegex(ValueError,'private smoke project'):
            release.validate_entries('video-grill',entries)


if __name__=='__main__':
    unittest.main(verbosity=2)
