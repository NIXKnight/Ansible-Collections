from ansible.plugins.lookup import LookupBase
from ansible.errors import AnsibleError
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class LookupModule(LookupBase):
    def _exrtact_output(self, opentofu_state, output_name):
        if 'outputs' not in opentofu_state:
            raise AnsibleError("No outputs found in state")

        if output_name not in opentofu_state['outputs']:
            raise AnsibleError(f"Output '{output_name}' not found")

        return [opentofu_state['outputs'][output_name]['value']]

    def _extract_metadata_and_encrypted_data(self, encrypted_state, enc_key_provider_name):
        try:
            b64_decoded_metadata = base64.b64decode(encrypted_state['meta'][f'key_provider.pbkdf2.{enc_key_provider_name}'])
            b64_decoded_metadata = json.loads(b64_decoded_metadata.decode('utf-8'))

            b64_decoded_encrypted_data = base64.b64decode(encrypted_state['encrypted_data'])
            return b64_decoded_metadata, b64_decoded_encrypted_data
        except Exception as e:
            raise AnsibleError(f"Failed to extract metadata or encrypted data: {str(e)}")

    def _decrypt_opentofu_state(self, enc_passphrase, encryption_metadata, encrypted_data):
        key_provider_hash_function_map = {
            'sha512': hashes.SHA512,
            'sha256': hashes.SHA256
        }

        pbkdf2_metadata_salt = base64.b64decode(encryption_metadata['salt'])
        pbkdf2_metadata_iterations = encryption_metadata['iterations']
        pbkdf2_metadata_algorithm = key_provider_hash_function_map[encryption_metadata['hash_function']]
        pbkdf2_metadata_length = encryption_metadata['key_length']

        pbkdf2_deriver = PBKDF2HMAC(
            algorithm=pbkdf2_metadata_algorithm(),
            length=pbkdf2_metadata_length,
            salt=pbkdf2_metadata_salt,
            iterations=pbkdf2_metadata_iterations
        )

        pbkdf2_derived_key = pbkdf2_deriver.derive(enc_passphrase.encode('utf-8'))
        pbkdf2_nonce = encrypted_data[:12]
        pbkdf2_ciphertext = encrypted_data[12:]

        try:
            aesgcm = AESGCM(pbkdf2_derived_key)
            plaintext_state = aesgcm.decrypt(pbkdf2_nonce, pbkdf2_ciphertext, None)
            return json.loads(plaintext_state.decode('utf-8'))
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")

    def _decrypt_state_if_needed(self, state, enc_passphrase, enc_key_provider_name, output_name):
        if enc_passphrase:
            metadata, encrypted_data = self._extract_metadata_and_encrypted_data(state, enc_key_provider_name)
            state = self._decrypt_opentofu_state(enc_passphrase, metadata, encrypted_data)
        return self._exrtact_output(state, output_name)

    def _get_state_from_file(self, state_file_path, enc_passphrase, enc_key_provider_name, output_name):
        try:
            with open(state_file_path, 'r') as f:
                state = json.load(f)
            return self._decrypt_state_if_needed(state, enc_passphrase, enc_key_provider_name, output_name)
        except FileNotFoundError:
            raise AnsibleError(f"State file not found: {state_file_path}")
        except json.JSONDecodeError:
            raise AnsibleError("Invalid JSON in state file")
        except ValueError as e:
            raise AnsibleError(f"Decryption failed: {str(e)}")
        except Exception as e:
            raise AnsibleError(f"Error processing state file: {str(e)}")

    def _get_state_from_pg_db_schema(self, pg_conn_string, pg_schema, enc_passphrase, enc_key_provider_name, output_name):
        try:
            conn = psycopg2.connect(pg_conn_string)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(f"SELECT data FROM {pg_schema}.states WHERE name = 'default'")
            result = cur.fetchone()

            if not result:
                raise AnsibleError("State not found in database")

            state = json.loads(result['data'])
            return self._decrypt_state_if_needed(state, enc_passphrase, enc_key_provider_name, output_name)
        except psycopg2.Error as e:
            raise AnsibleError(f"Database error: {str(e)}")
        except ValueError as e:
            raise AnsibleError(f"Decryption or decoding error: {str(e)}")
        except Exception as e:
            raise AnsibleError(f"Error processing state from database: {str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()

    def run(self, terms, variables=None, **kwargs):
        output_name = terms[0]
        state_file_path = kwargs.get('state_file_path')
        pg_conn_string = kwargs.get('pg_conn_string')
        pg_schema = kwargs.get('pg_schema', 'terraform_remote_state')
        enc_passphrase = kwargs.get('enc_passphrase', None)
        enc_key_provider_name = kwargs.get('enc_key_provider_name', None)

        if not (state_file_path or pg_conn_string):
            raise AnsibleError("Either file path or database connection string required")

        if enc_passphrase and not enc_key_provider_name:
            raise AnsibleError("If 'enc_passphrase' is provided, 'enc_key_provider_name' must also be provided")

        try:
            if state_file_path:
                return self._get_state_from_file(state_file_path, enc_passphrase, enc_key_provider_name, output_name)
            else:
                return self._get_state_from_pg_db_schema(pg_conn_string, pg_schema, enc_passphrase, enc_key_provider_name, output_name)
        except Exception as e:
            raise AnsibleError(f"Error retrieving state: {str(e)}")
