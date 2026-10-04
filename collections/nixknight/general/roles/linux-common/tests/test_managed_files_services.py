"""Offline generic-entry regression: disposable role copies, no host modules.

Only core include/assert/debug actions remain real. Every other host action is
replaced by a connection-free controller mock, including ordinary main/handlers.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROLE = Path(__file__).resolve().parents[1]
MOCK_ACTION = r'''import json
import os
from ansible.plugins.action import ActionBase
class ActionModule(ActionBase):
    _requires_connection = False
    def run(self, tmp=None, task_vars=None):
        args = dict(self._task.args)
        module = args.pop('_original_module')
        if self._task.check_mode and module == 'systemd_service':
            raise AssertionError('systemd must not run in check mode')
        with open(os.environ['GPU_OFFLINE_EVENTS'], 'a') as output:
            output.write(json.dumps({'module': module, 'args': args,
                                     'check': self._task.check_mode}) + '\n')
        if module == 'template' and args.get('validate') and os.environ.get('GPU_OFFLINE_FAIL_VALIDATE'):
            return {'failed': True, 'msg': 'synthetic schema validation failure'}
        if module == 'systemd_service' and 'state' in args and os.environ.get('GPU_OFFLINE_FAIL_STATE'):
            return {'failed': True, 'msg': 'synthetic helper readback failure'}
        changed = module == 'systemd_service' and args.get('state') == 'restarted'
        return {'changed': changed}
'''


def mock_role(source, target):
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    for folder in ('tasks', 'handlers'):
        for path in (target / folder).glob('*.yml'):
            tasks = yaml.safe_load(path.read_text()) or []
            for task in tasks:
                for key in list(task):
                    if key.startswith(('ansible.builtin.', 'ansible.posix.')) and key not in (
                            'ansible.builtin.include_tasks', 'ansible.builtin.assert', 'ansible.builtin.debug'):
                        args = task.pop(key)
                        if not isinstance(args, dict):
                            args = {'_raw_params': args}
                        args['_original_module'] = key.rsplit('.', 1)[1]
                        task['ansible.legacy.gpu_offline_mock'] = args
                        # Ordinary async/reboot is NOT exercised as a host action.
                        task.pop('async', None)
                        task.pop('poll', None)
            path.write_text(yaml.safe_dump(tasks, sort_keys=False))


def clean_env(root, config, collections):
    # Read ONLY HOME/PATH-independent public fixture values. No inherited
    # ANSIBLE_* or credentials copied or displayed.
    return {'HOME': str(root / 'home'), 'PATH': str(Path(sys.executable).parent) + os.pathsep + os.defpath,
            'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
            'ANSIBLE_CONFIG': str(config), 'ANSIBLE_COLLECTIONS_PATH': str(collections),
            'GPU_OFFLINE_EVENTS': str(root / 'events.jsonl')}


class ManagedFilesServicesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='linux-common-offline-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.collections = self.root / 'source'
        target = self.collections / 'ansible_collections/nixknight/general/roles/linux-common'
        mock_role(ROLE, target)
        plugins = self.root / 'actions'
        plugins.mkdir()
        (plugins / 'gpu_offline_mock.py').write_text(MOCK_ACTION)
        self.config = self.root / 'public-only.cfg'
        self.config.write_text('[defaults]\nvars_plugins_enabled =\nhost_key_checking = True\n'
                               'collections_scan_sys_path = False\naction_plugins = ' + str(plugins) +
                               '\n[inventory]\nenable_plugins = host_list\n')
        self.env = clean_env(self.root, self.config, self.collections)
        self.playbook = self.root / 'play.yml'

    def run_role(self, variables=None, entry='managed_files_services', check=False):
        play = [{'name': 'Offline generic role', 'hosts': 'offline', 'gather_facts': False,
                 'collections': ['nixknight.general'], 'vars': variables or {},
                 'tasks': [{'name': 'Resolve short collection role', 'ansible.builtin.include_role':
                            {'name': 'linux-common', 'tasks_from': entry}}]}]
        self.playbook.write_text(yaml.safe_dump(play, sort_keys=False))
        return subprocess.run(['ansible-playbook', '-i', 'offline,', str(self.playbook), *(['--check'] if check else [])],
                              env=self.env, cwd=self.root, text=True, capture_output=True, timeout=30)

    def events(self):
        path = self.root / 'events.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def inputs(self):
        return {'LC_ADDITIONAL_PATHS': ['/fixture/string', {'path': '/fixture/mapping', 'owner': 'root',
                                                          'group': 'root', 'mode': '0700', 'recurse': False}],
                'LC_MISC_FILES': [{'src': '/fixture/helper', 'dest': '/fixture/installed-helper',
                                   'mode': '0755', 'owner': 'root', 'group': 'root'}],
                'LC_MISC_TEMPLATES': [{'src': '/fixture/config', 'dest': '/fixture/rendered',
                                       'mode': '0644', 'owner': 'root', 'group': 'root',
                                       'validate': '/fixture/installed-helper --validate-config %s'},
                                      {'src': '/fixture/unit', 'dest': '/fixture/unit.service',
                                       'mode': '0644', 'owner': 'root', 'group': 'root'}],
                'LC_SYSTEMD_SERVICES_ACTIONS': [{'service_name': 'fixture.service', 'state': 'restarted',
                                                'daemon_reload': True, 'enabled': True}]}

    def test_default_entry_is_empty_and_fact_free(self):
        self.assert_success(self.run_role())
        self.assertEqual(self.events(), [])

    def test_string_mapping_copy_before_template_optional_validate_and_order(self):
        result = self.run_role(self.inputs())
        self.assert_success(result)
        events = self.events()
        self.assertEqual([e['module'] for e in events], ['file', 'file', 'copy', 'template', 'template',
                                                       'systemd_service', 'systemd_service'])
        self.assertEqual(events[0]['args'], {'path': '/fixture/string', 'state': 'directory', 'recurse': True})
        self.assertEqual(events[1]['args'], {'path': '/fixture/mapping', 'state': 'directory', 'recurse': False,
                                           'owner': 'root', 'group': 'root', 'mode': '0700'})
        self.assertIn('validate', events[3]['args'])
        self.assertNotIn('validate', events[4]['args'])
        self.assertEqual(events[-2]['args'], {'name': 'fixture.service', 'state': 'restarted', 'daemon_reload': True})
        self.assertEqual(events[-1]['args'], {'name': 'fixture.service', 'enabled': True})

    def test_first_install_check_skips_all_systemd(self):
        self.assert_success(self.run_role(self.inputs(), check=True))
        self.assertEqual([e['module'] for e in self.events()], ['file', 'file', 'copy', 'template', 'template'])
        self.assertTrue(all(e['check'] for e in self.events()))

    def test_validation_or_state_failure_prevents_enablement(self):
        for variable in ('GPU_OFFLINE_FAIL_VALIDATE', 'GPU_OFFLINE_FAIL_STATE'):
            with self.subTest(failure=variable):
                self.env[variable] = '1'
                (self.root / 'events.jsonl').unlink(missing_ok=True)
                result = self.run_role(self.inputs())
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any('enabled' in e['args'] for e in self.events()))
                if variable.endswith('VALIDATE'):
                    self.assertFalse(any(e['module'] == 'systemd_service' for e in self.events()))
                del self.env[variable]

    def test_required_copy_template_service_fields_remain_required(self):
        for interface, key in (('LC_MISC_FILES', 'owner'), ('LC_MISC_TEMPLATES', 'mode'),
                               ('LC_SYSTEMD_SERVICES_ACTIONS', 'daemon_reload')):
            with self.subTest(interface=interface):
                inputs = self.inputs()
                del inputs[interface][0][key]
                result = self.run_role(inputs)
                self.assertNotEqual(result.returncode, 0)

    def test_ordinary_main_keeps_upgrade_guards_and_remaining_tasks(self):
        variables = self.inputs() | {'LC_CHANGE_HOSTNAME': False, 'LC_CHANGE_APT_DEFAULT_SOURCES_LIST': False,
                                     'LC_REMOVE_EXIM': False, 'LC_INSTALL_PACKAGES': False, 'LC_SETUP_SUDO': False,
                                     'LC_SETUP_THIRD_PARTY_REPOS': False, 'LC_SET_KERNEL_PARAMETERS': False,
                                     'LC_REBOOT': False}
        self.assert_success(self.run_role(variables, entry='main'))
        events = self.events()
        self.assertEqual(events[0]['module'], 'apt')
        self.assertEqual(events[0]['args'], {'upgrade': 'dist', 'update_cache': True})
        self.assertEqual(len([e for e in events if e['module'] == 'apt']), 1)
        self.assertEqual([e['module'] for e in events[1:]], ['file', 'file', 'copy', 'template', 'template',
                                                          'systemd_service', 'systemd_service'])
        tasks = yaml.safe_load((ROLE / 'tasks/main.yml').read_text())
        included = [t for t in tasks if 'ansible.builtin.include_tasks' in t]
        self.assertEqual(len(included), 1)
        self.assertTrue(any('ansible.posix.sysctl' in t for t in tasks))
        self.assertTrue(any('ansible.builtin.wait_for' in t for t in tasks))


if __name__ == '__main__':
    unittest.main()
