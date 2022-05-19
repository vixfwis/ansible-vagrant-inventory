#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2022, vixfwis <vixfwis at github.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


DOCUMENTATION = '''---
module: vagrant
short_description: Vagrant inventory source
description:
    - Reads "vagrant ssh-config" output.
    - Uses Vagrantfile location
options:
    vagrantfile:
        description:
            - Path to Vagrantfile or containing directory.
            - Relative paths resolve from inventory file location.
        required: true

version_added: "2.13"
author: "vixfwis (@vixfwis)"
extends_documentation_fragment:
  - inventory_cache
'''

from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable
from ansible.module_utils.common.text.converters import to_native
from ansible.errors import AnsibleFileNotFound, AnsibleError
from subprocess import run, CalledProcessError
from pathlib import Path

class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = 'vagrant'

    def verify_file(self, path):
        return super(InventoryModule, self).verify_file(path)

    def populate(self, results):
        for host_info in results:
            self.inventory.add_host(host_info['host'])
            self.inventory.set_variable(host_info['host'], 'ansible_host', host_info['hostname'])
            self.inventory.set_variable(host_info['host'], 'ansible_user', host_info['user'])
            self.inventory.set_variable(host_info['host'], 'ansible_port', host_info['port'])
            self.inventory.set_variable(host_info['host'], 'ansible_host_key_checking', False)
            self.inventory.set_variable(host_info['host'], 'ansible_ssh_private_key_file', host_info['sshkey'])
    
    def parse_inventory(self, path):
        cfg = self._read_config_data(path)
        vf_path = Path(cfg['vagrantfile'])
        if not vf_path.is_absolute():
            vf_path = Path(path).parent / vf_path
        vf_path = vf_path.resolve()
        if vf_path.is_file():
            if vf_path.name == 'Vagrantfile':
                if not vf_path.exists():
                    raise AnsibleFileNotFound('%s does not exist' % str(vf_path))
                vf_path = vf_path.parent
            else:
                raise AnsibleFileNotFound('vagrantfile option must point to Vagrantfile or containing folder')
        else:
            vf_file = vf_path / 'Vagrantfile'
            if not (vf_file.is_file() and vf_file.exists()):
                raise AnsibleFileNotFound('%s does not contain Vagrantfile' % str(vf_path))
        try:
            proc = run(['vagrant', 'ssh-config'], check=True, capture_output=True, cwd=vf_path)
        except Exception as e:
            raise AnsibleError('"vagrant ssh-config" failed with: %s' % to_native(e))
        out = proc.stdout.decode('utf8')
        results = []
        host_info = {}
        for line in out.split('\n'):
            line = [e.strip() for e in line.strip().split(' ')]
            line = ' '.join([e for e in line if e != ''])
            if line == '':
                continue
            if line.startswith('Host '):
                if len(host_info) > 0:
                    results.append(host_info.copy())
                    host_info.clear()
                host_info['host'] = line.split(' ', 1)[1]
            if line.startswith('HostName '):
                host_info['hostname'] = line.split(' ', 1)[1]
            if line.startswith('User '):
                host_info['user'] = line.split(' ', 1)[1]
            if line.startswith('Port '):
                host_info['port'] = int(line.split(' ', 1)[1])
            if line.startswith('IdentityFile '):
                host_info['sshkey'] = line.split(' ', 1)[1]
        
        if len(host_info) > 0:
            results.append(host_info.copy())
            host_info.clear()
        return results

    def parse(self, inventory, loader, path, cache=True):
        super(InventoryModule, self).parse(inventory, loader, path, cache)
        self.load_cache_plugin()
        cache_key = self.get_cache_key(path)

        # https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html
        # cache may be True or False at this point to indicate if the inventory is being refreshed
        # get the user's cache option too to see if we should save the cache if it is changing
        user_cache_setting = self.get_option('cache')

        # read if the user has caching enabled and the cache isn't being refreshed
        attempt_to_read_cache = user_cache_setting and cache
        # update if the user has caching enabled and the cache is being refreshed; update this value to True if the cache has expired below
        cache_needs_update = user_cache_setting and not cache

        # attempt to read the cache if inventory isn't being refreshed and the user has caching enabled
        if attempt_to_read_cache:
            # print('reading cache')
            try:
                results = self._cache[cache_key]
            except KeyError:
                # This occurs if the cache_key is not in the cache or if the cache_key expired, so the cache needs to be updated
                cache_needs_update = True
        if not attempt_to_read_cache or cache_needs_update:
            # parse the provided inventory source
            # print('parsing inventory')
            results = self.parse_inventory(path)
        if cache_needs_update:
            # print('updating cache')
            self._cache[cache_key] = results

        # submit the parsed data to the inventory object (add_host, set_variable, etc)
        self.populate(results)
