from ansible.plugins.lookup import LookupBase
from ansible.errors import AnsibleError
import json

class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        output_name = terms[0]
        state_file = kwargs.get('file')

        if not state_file:
            raise AnsibleError("State file path is required")

        try:
            with open(state_file, 'r') as f:
                state = json.load(f)

            if 'outputs' not in state:
                raise AnsibleError("No outputs found in state file")

            if output_name not in state['outputs']:
                raise AnsibleError(f"Output '{output_name}' not found")

            return [state['outputs'][output_name]['value']]

        except FileNotFoundError:
            raise AnsibleError(f"State file not found: {state_file}")
        except json.JSONDecodeError:
            raise AnsibleError("Invalid JSON in state file")
