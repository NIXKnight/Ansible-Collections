from ansible.plugins.lookup import LookupBase
from ansible.errors import AnsibleError
import json
import psycopg2
from psycopg2.extras import RealDictCursor

class LookupModule(LookupBase):
    def _exrtact_output(self, opentofu_state, output_name):
        if 'outputs' not in opentofu_state:
            raise AnsibleError("No outputs found in state")

        if output_name not in opentofu_state['outputs']:
            raise AnsibleError(f"Output '{output_name}' not found")

        return [opentofu_state['outputs'][output_name]['value']]

    def _get_state_from_file(self, state_file, output_name):
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
        except FileNotFoundError:
            raise AnsibleError(f"State file not found: {state_file}")
        except json.JSONDecodeError:
            raise AnsibleError("Invalid JSON in state file")

        return self._exrtact_output(state, output_name)

    def _get_state_from_pg_db_schema(self, pg_conn_string, pg_schema, output_name):
        try:
            conn = psycopg2.connect(pg_conn_string)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(f"SELECT data FROM {pg_schema}.states WHERE name = 'default'")
            result = cur.fetchone()

            if not result:
                raise AnsibleError("State not found in database")

            state = json.loads(result['data'])
            return self._exrtact_output(state, output_name)
        finally:
            if 'conn' in locals():
                conn.close()

    def run(self, terms, variables=None, **kwargs):
        output_name = terms[0]
        state_file_path = kwargs.get('state_file_path')
        pg_conn_string = kwargs.get('pg_conn_string')
        pg_schema = kwargs.get('pg_schema', 'terraform_remote_state')

        if not (state_file_path or pg_conn_string):
            raise AnsibleError("Either file path or database connection string required")
        try:
            if state_file_path:
                return self._get_from_file(state_file_path, output_name)
            else:
                return self._get_state_from_pg_db_schema(pg_conn_string, pg_schema, output_name)
        except Exception as e:
            raise AnsibleError(f"Error retrieving state: {str(e)}")
