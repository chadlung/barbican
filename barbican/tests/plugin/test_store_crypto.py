# Copyright (c) 2014 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import base64
import mock
import testtools

from barbican.common import utils
from barbican.model import models
from barbican.plugin.crypto import crypto
from barbican.plugin.interface import secret_store
from barbican.plugin import store_crypto


class TestSecretStoreBase(testtools.TestCase):
    """Define common configurations for testing store_crypto.py."""
    def setUp(self):
        super(TestSecretStoreBase, self).setUp()

        self.patchers = []  # List of patchers utilized in this test class.

        self.project_id = '12345'
        self.content_type = 'application/octet-stream'
        self.secret = 'secret'
        self.decrypted_secret = 'decrypted_secret'
        self.cypher_text = 'cypher_text'
        self.kek_meta_extended = 'kek-meta-extended'
        self.spec_aes = secret_store.KeySpec('AES', 64, 'CBC')
        self.spec_rsa = secret_store.KeySpec(
            'RSA', 1024, passphrase='changeit')

        self.tenant_model = mock.MagicMock()
        self.tenant_model.id = 'tenant-model-id'
        self.tenant_model.keystone_id = self.project_id
        self.secret_dto = secret_store.SecretDTO(
            secret_store.SecretType.SYMMETRIC,
            self.secret,
            secret_store.KeySpec(),
            self.content_type
        )
        self.response_dto = crypto.ResponseDTO(
            self.cypher_text, kek_meta_extended=self.kek_meta_extended)
        self.private_key_dto = crypto.ResponseDTO(self.cypher_text)
        self.public_key_dto = crypto.ResponseDTO(self.cypher_text)
        self.passphrase_dto = crypto.ResponseDTO(self.cypher_text)

        self.kek_meta_tenant_model = models.KEKDatum()
        self.kek_meta_tenant_model.plugin_name = 'plugin-name'
        self.kek_meta_tenant_model.kek_label = 'kek-meta-label'
        self.kek_meta_tenant_model.algorithm = 'kek-meta-algo'
        self.kek_meta_tenant_model.bit_length = 1024
        self.kek_meta_tenant_model.mode = 'kek=meta-mode'
        self.kek_meta_tenant_model.plugin_meta = 'kek-meta-plugin-meta'

        self.encrypted_datum_model = models.EncryptedDatum()
        self.encrypted_datum_model.kek_meta_tenant = self.kek_meta_tenant_model
        self.encrypted_datum_model.cypher_text = base64.b64encode(
            'cypher_text')
        self.encrypted_datum_model.content_type = 'content_type'
        self.encrypted_datum_model.kek_meta_extended = 'extended_meta'

        self.secret_model = models.Secret(
            {
                'algorithm': 'myalg',
                'bit_length': 1024,
                'mode': 'mymode'
            }
        )
        self.secret_model.id = 'secret-model-id'
        self.secret_model.encrypted_data = [self.encrypted_datum_model]

        self.context = store_crypto.StoreCryptoContext(
            secret_model=self.secret_model,
            tenant_model=self.tenant_model,
            content_type=self.content_type)

    def tearDown(self):
        super(TestSecretStoreBase, self).tearDown()
        for patcher in self.patchers:
            patcher.stop()

    def init_patchers(self):
        self._config_get_secret_repository()
        self._config_get_tenant_secret_repository()
        self._config_get_encrypted_datum_repository()
        self._config_get_kek_datum_repository()

    def _start_patcher(self, patcher):
        mock = patcher.start()
        self.patchers.append(patcher)
        return mock

    def _config_get_secret_repository(self):
        """Mock the get_secret_repository() factory function."""
        self.secret_repo = mock.MagicMock()
        self.secret_repo.create_from.return_value = self.secret_model

        get_secret_repository_config = {
            'return_value': self.secret_repo
        }
        self.get_secret_repository_patcher = mock.patch(
            'barbican.model.repositories.get_secret_repository',
            **get_secret_repository_config
        )
        self._start_patcher(self.get_secret_repository_patcher)

    def _config_get_tenant_secret_repository(self):
        """Mock the get_tenant_secret_repository() factory function."""
        self.tenant_secret_repo = mock.MagicMock()
        self.tenant_secret_repo.create_from.return_value = None

        get_tenant_secret_repository_config = {
            'return_value': self.tenant_secret_repo
        }
        self.get_tenant_secret_repository_patcher = mock.patch(
            'barbican.model.repositories.get_tenant_secret_repository',
            **get_tenant_secret_repository_config
        )
        self._start_patcher(self.get_tenant_secret_repository_patcher)

    def _config_get_encrypted_datum_repository(self):
        """Mock the get_encrypted_datum_repository() factory function."""
        self.datum_repo = mock.MagicMock()
        self.datum_repo.create_from.return_value = None

        get_encrypted_datum_repository_config = {
            'return_value': self.datum_repo
        }
        self.get_encrypted_datum_repository_patcher = mock.patch(
            'barbican.model.repositories.get_encrypted_datum_repository',
            **get_encrypted_datum_repository_config
        )
        self._start_patcher(
            self.get_encrypted_datum_repository_patcher)

    def _config_get_kek_datum_repository(self):
        """Mock the get_kek_datum_repository() factory function."""
        kek_model = self.kek_meta_tenant_model
        self.kek_repo = mock.MagicMock()
        self.kek_repo.find_or_create_kek_datum.return_value = kek_model

        get_kek_datum_repository_config = {
            'return_value': self.kek_repo
        }
        self.get_kek_datum_repository_patcher = mock.patch(
            'barbican.model.repositories.get_kek_datum_repository',
            **get_kek_datum_repository_config
        )
        self._start_patcher(
            self.get_kek_datum_repository_patcher)


class WhenTestingStoreCrypto(TestSecretStoreBase):

    def setUp(self):
        super(WhenTestingStoreCrypto, self).setUp()

        self.init_patchers()
        self._config_crypto_plugin()
        self._config_private_methods()

        self.plugin_to_test = store_crypto.StoreCryptoAdapterPlugin()

    def test_store_secret_with_context_type(self):
        """Test storing a secret."""

        response_dict = self.plugin_to_test.store_secret(
            self.secret_dto, self.context)

        self.assertEqual(None, response_dict)

        # Verify encrypt plugin and method where invoked.
        encrypt_mock = self.encrypting_plugin.encrypt
        self.assertEqual(encrypt_mock.call_count, 1)
        args, kwargs = encrypt_mock.call_args
        test_encrypt_dto, test_kek_meta_dto, test_project_id = tuple(args)
        self.assertIsInstance(test_encrypt_dto, crypto.EncryptDTO)
        self.assertEqual(self.secret, test_encrypt_dto.unencrypted)
        self.assertEqual(self.kek_meta_dto, test_kek_meta_dto)
        self.assertEqual(self.project_id, test_project_id)

    def test_store_secret_without_context_type(self):
        """Test storing a secret."""
        self.context.content_type = None

        self.plugin_to_test.store_secret(
            self.secret_dto, self.context)

        self.assertEqual(self.content_type, self.context.content_type)

    def test_get_secret(self):
        """Test getting a secret."""

        secret_dto = self.plugin_to_test.get_secret(
            None,  # Secret metadata is not relevant to store_crypto process.
            self.context)

        # Verify response.
        self.assertIsInstance(secret_dto, secret_store.SecretDTO)
        self.assertEqual(secret_store.SecretType.SYMMETRIC, secret_dto.type)
        self.assertEqual(self.decrypted_secret, secret_dto.secret)
        self.assertEqual(
            self.encrypted_datum_model.content_type, secret_dto.content_type)
        self.assertIsInstance(secret_dto.key_spec, secret_store.KeySpec)
        self.assertEqual(
            self.secret_model.algorithm, secret_dto.key_spec.alg)
        self.assertEqual(
            self.secret_model.bit_length, secret_dto.key_spec.bit_length)
        self.assertEqual(
            self.secret_model.mode, secret_dto.key_spec.mode)

        # Verify decrypt plugin and method where invoked.
        decrypt_mock = self.retrieving_plugin.decrypt
        self.assertEqual(decrypt_mock.call_count, 1)
        args, kwargs = decrypt_mock.call_args
        (
            test_decrypt,
            test_kek_meta,
            test_kek_meta_extended,
            test_project_id
        ) = tuple(args)

        self.assertIsInstance(test_decrypt, crypto.DecryptDTO)
        self.assertEqual(
            base64.b64decode(self.encrypted_datum_model.cypher_text),
            test_decrypt.encrypted)

        self.assertIsInstance(test_kek_meta, crypto.KEKMetaDTO)
        self.assertEqual(
            self.kek_meta_tenant_model.plugin_name, test_kek_meta.plugin_name)

        self.assertEqual(
            self.encrypted_datum_model.kek_meta_extended,
            test_kek_meta_extended)

        self.assertEqual(self.project_id, test_project_id)

    def test_generate_symmetric_key(self):
        """test symmetric secret generation."""
        generation_type = crypto.PluginSupportTypes.SYMMETRIC_KEY_GENERATION
        self._config_determine_generation_type_private_method(
            generation_type)

        response_dict = self.plugin_to_test.generate_symmetric_key(
            self.spec_aes, self.context)

        self.assertEqual(None, response_dict)

        # Verify KEK objects finder was invoked.
        method_target = self.find_or_create_kek_objects_patcher.target
        method_mock = method_target._find_or_create_kek_objects
        self.assertEqual(method_mock.call_count, 1)

        # Verify generating plugin and method where invoked.
        self._verify_generating_plugin_args(
            self.generating_plugin.generate_symmetric,
            self.spec_aes.alg,
            self.spec_aes.bit_length)

        # Verify secret save was invoked.
        method_target = self.store_secret_and_datum_patcher.target
        method_mock = method_target._store_secret_and_datum
        self.assertEqual(method_mock.call_count, 1)

    def test_generate_asymmetric_key_with_passphrase(self):
        """test asymmetric secret generation with passphrase."""
        self._test_generate_asymmetric_key(passphrase='passphrase')

    def test_generate_asymmetric_key_without_passphrase(self):
        """test asymmetric secret generation with passphrase."""
        self._test_generate_asymmetric_key(passphrase=None)

    def test_generate_supports(self):
        """test generate_supports."""
        # False return if KeySpec == None
        self.assertFalse(self.plugin_to_test.generate_supports(None))

        # AES KeySpec should be supported.
        key_spec = secret_store.KeySpec(alg='AES', bit_length=64, mode='CBC')
        self.assertTrue(self.plugin_to_test.generate_supports(key_spec))
        key_spec = secret_store.KeySpec(alg='aes', bit_length=64, mode='CBC')
        self.assertTrue(self.plugin_to_test.generate_supports(key_spec))

        # RSA KeySpec should be supported.
        key_spec = secret_store.KeySpec(alg='RSA', bit_length=2048)
        self.assertTrue(self.plugin_to_test.generate_supports(key_spec))
        # Camellia KeySpec should not be supported.
        self.key_spec = secret_store.KeySpec('Camellia', 64)
        self.assertFalse(self.plugin_to_test.generate_supports(self.key_spec))
        # Bogus KeySpec should not be supported.
        key_spec = secret_store.KeySpec(alg='bogus', bit_length=2048)
        self.assertFalse(self.plugin_to_test.generate_supports(key_spec))

    def test_store_secret_supports(self):
        # All spec types are supported for storage.
        key_spec = secret_store.KeySpec(
            alg='anyalg', bit_length=64, mode='CBC')
        self.assertTrue(self.plugin_to_test.store_secret_supports(key_spec))

    def test_delete_secret(self):
        """Delete is not implemented, so just verify passes."""
        self.plugin_to_test.delete_secret(None)

    def test_should_raise_secret_not_found_get_secret_with_no_model(self):
        self.context.secret_model = None

        self.assertRaises(
            secret_store.SecretNotFoundException,
            self.plugin_to_test.get_secret,
            None,  # get_secret() doesn't use the secret metadata argument
            self.context
        )

    def test_should_raise_secret_not_found_get_secret_no_encrypted_data(self):
        self.context.secret_model.encrypted_data = []

        self.assertRaises(
            secret_store.SecretNotFoundException,
            self.plugin_to_test.get_secret,
            None,  # get_secret() doesn't use the secret metadata argument
            self.context
        )

    def test_should_raise_algorithm_not_supported_generate_symmetric_key(self):
        generation_type = crypto.PluginSupportTypes.ASYMMETRIC_KEY_GENERATION
        self._config_determine_generation_type_private_method(
            generation_type)

        self.assertRaises(
            secret_store.SecretAlgorithmNotSupportedException,
            self.plugin_to_test.generate_symmetric_key,
            self.spec_aes,
            self.context
        )

    def test_should_raise_algo_not_supported_generate_asymmetric_key(self):
        generation_type = crypto.PluginSupportTypes.SYMMETRIC_KEY_GENERATION
        self._config_determine_generation_type_private_method(
            generation_type)

        self.assertRaises(
            secret_store.SecretAlgorithmNotSupportedException,
            self.plugin_to_test.generate_asymmetric_key,
            self.spec_rsa,
            self.context
        )

    def _test_generate_asymmetric_key(self, passphrase=None):
        """test asymmetric secret generation with passphrase parameter."""
        self.spec_rsa.passphrase = passphrase

        generation_type = crypto.PluginSupportTypes.ASYMMETRIC_KEY_GENERATION
        self._config_determine_generation_type_private_method(
            generation_type)

        response_dto = self.plugin_to_test.generate_asymmetric_key(
            self.spec_rsa, self.context)

        # Verify response.
        self.assertIsInstance(
            response_dto, secret_store.AsymmetricKeyMetadataDTO)
        self.assertEqual(None, response_dto.private_key_meta)
        self.assertEqual(None, response_dto.public_key_meta)
        self.assertEqual(None, response_dto.passphrase_meta)

        # Verify KEK objects finder was invoked.
        method_target = self.find_or_create_kek_objects_patcher.target
        method_mock = method_target._find_or_create_kek_objects
        self.assertEqual(method_mock.call_count, 1)

        # Verify generating plugin and method where invoked.
        self._verify_generating_plugin_args(
            self.generating_plugin.generate_asymmetric,
            self.spec_rsa.alg,
            self.spec_rsa.bit_length)

        # Assert the secret save was called the proper number of times.
        call_count = 2
        if passphrase:
            call_count = 3
        method_target = self.store_secret_and_datum_patcher.target
        method_mock = method_target._store_secret_and_datum
        self.assertEqual(method_mock.call_count, call_count)

    def _verify_generating_plugin_args(self, generate_mock, alg, bit_length):
        """Verify generating plugin and method where invoked."""
        self.assertEqual(generate_mock.call_count, 1)
        args, kwargs = generate_mock.call_args
        test_generate_dto, test_kek_meta_dto, test_project_id = tuple(args)
        self.assertIsInstance(test_generate_dto, crypto.GenerateDTO)
        self.assertEqual(alg, test_generate_dto.algorithm)
        self.assertEqual(bit_length, test_generate_dto.bit_length)
        self.assertEqual(self.kek_meta_dto, test_kek_meta_dto)
        self.assertEqual(self.project_id, test_project_id)

        return generate_mock

    def _config_crypto_plugin(self):
        """Mock the crypto plugin."""

        # Create encrypting and generating plugins (the same plugin does both)
        response_dto = self.response_dto
        self.generating_plugin = mock.MagicMock()
        self.encrypting_plugin = self.generating_plugin
        self.generating_plugin.encrypt.return_value = response_dto
        self.generating_plugin.generate_symmetric.return_value = response_dto
        self.generating_plugin.generate_asymmetric.return_value = (
            self.private_key_dto, self.public_key_dto, self.passphrase_dto
        )

        # Create secret retrieving plugin
        self.retrieving_plugin = mock.MagicMock()
        self.retrieving_plugin.decrypt.return_value = self.decrypted_secret

        gen_plugin_config = {
            'get_plugin_store_generate.return_value': self.generating_plugin,
            'get_plugin_retrieve.return_value': self.retrieving_plugin,
        }
        self.gen_plugin_patcher = mock.patch(
            'barbican.plugin.crypto.manager.PLUGIN_MANAGER',
            **gen_plugin_config
        )
        self._start_patcher(self.gen_plugin_patcher)

    def _config_private_methods(self):
        """Mock store_crypto's private methods."""

        # Mock _find_or_create_kek_objects().
        self.kek_meta_dto = mock.MagicMock()
        find_or_create_kek_objects_config = {
            'return_value': (
                self.kek_meta_tenant_model, self.kek_meta_dto),
        }
        self.find_or_create_kek_objects_patcher = mock.patch(
            'barbican.plugin.store_crypto._find_or_create_kek_objects',
            **find_or_create_kek_objects_config
        )
        self._start_patcher(self.find_or_create_kek_objects_patcher)

        # Mock _store_secret_and_datum().
        self.store_secret_and_datum_patcher = mock.patch(
            'barbican.plugin.store_crypto._store_secret_and_datum'
        )
        self._start_patcher(self.store_secret_and_datum_patcher)

    def _config_determine_generation_type_private_method(self, type_to_return):
        """Mock _determine_generation_type()."""

        determine_generation_type_config = {
            'return_value': type_to_return,
        }
        self.determine_generation_type_patcher = mock.patch(
            'barbican.plugin.store_crypto._determine_generation_type',
            **determine_generation_type_config
        )
        self._start_patcher(self.determine_generation_type_patcher)


class WhenTestingStoreCryptoDetermineGenerationType(testtools.TestCase):
    """Tests store_crypto.py's _determine_generation_type() function."""

    def test_symmetric_algorithms(self):
        for algorithm in crypto.PluginSupportTypes.SYMMETRIC_ALGORITHMS:
            self.assertEqual(
                crypto.PluginSupportTypes.SYMMETRIC_KEY_GENERATION,
                store_crypto._determine_generation_type(algorithm))

        # Case doesn't matter.
        self.assertEqual(
            crypto.PluginSupportTypes.SYMMETRIC_KEY_GENERATION,
            store_crypto._determine_generation_type('AeS'))

    def test_asymmetric_algorithms(self):
        for algorithm in crypto.PluginSupportTypes.ASYMMETRIC_ALGORITHMS:
            self.assertEqual(
                crypto.PluginSupportTypes.ASYMMETRIC_KEY_GENERATION,
                store_crypto._determine_generation_type(algorithm))

        # Case doesn't matter.
        self.assertEqual(
            crypto.PluginSupportTypes.ASYMMETRIC_KEY_GENERATION,
            store_crypto._determine_generation_type('RsA'))

    def test_should_raise_not_supported_no_algorithm(self):
        self.assertRaises(
            secret_store.SecretAlgorithmNotSupportedException,
            store_crypto._determine_generation_type,
            None
        )

    def test_should_raise_not_supported_bogus_algorithm(self):
        self.assertRaises(
            secret_store.SecretAlgorithmNotSupportedException,
            store_crypto._determine_generation_type,
            'bogus'
        )


class WhenTestingStoreCryptoFindOrCreateKekObjects(TestSecretStoreBase):
    """Tests store_crypto.py's _find_or_create_kek_objects() function."""

    def setUp(self):
        super(WhenTestingStoreCryptoFindOrCreateKekObjects, self).setUp()
        self.init_patchers()
        self._config_private_methods()

    def test_kek_bind_completed(self):
        self.kek_meta_tenant_model.bind_completed = True
        plugin_inst = self

        kek_model, kek_meta_dto = store_crypto._find_or_create_kek_objects(
            plugin_inst, self.tenant_model)

        # Verify returns.
        self.assertEqual(self.kek_meta_tenant_model, kek_model)
        self.assertIsInstance(kek_meta_dto, crypto.KEKMetaDTO)

        # Verify the KEK repository interactions.
        self._verify_kek_repository_interactions(plugin_inst)

    def test_kek_bind_not_completed(self):
        self.kek_meta_tenant_model.bind_completed = False
        test_kek_metadata = 'metadata'
        plugin_inst = mock.MagicMock()
        plugin_inst.bind_kek_metadata.return_value = test_kek_metadata

        kek_model, kek_meta_dto = store_crypto._find_or_create_kek_objects(
            plugin_inst, self.tenant_model)

        # Verify returns.
        self.assertEqual(self.kek_meta_tenant_model, kek_model)
        self.assertEqual(test_kek_metadata, kek_meta_dto)

        # Verify the KEK repository interactions.
        self._verify_kek_repository_interactions(plugin_inst)

        # Verify bind operations.
        self.assertEqual(
            plugin_inst.bind_kek_metadata.call_count, 1)
        self.assertEqual(
            self.bind_completed_mock.call_count, 1)
        self.assertEqual(
            self.kek_repo.save.call_count, 1)
        args, kwargs = self.kek_repo.save.call_args
        kek_model = args[0]
        self.assertEqual(self.kek_meta_tenant_model, kek_model)

    def test_kek_raise_no_kek_bind_not_completed(self):
        self.kek_meta_tenant_model.bind_completed = False
        plugin_inst = mock.MagicMock()
        plugin_inst.bind_kek_metadata.return_value = None

        self.assertRaises(
            crypto.CryptoKEKBindingException,
            store_crypto._find_or_create_kek_objects,
            plugin_inst,
            self.tenant_model)

    def _verify_kek_repository_interactions(self, plugin_inst):
        """Verify the KEK repository interactions."""
        self.assertEqual(
            self.kek_repo.find_or_create_kek_datum.call_count, 1)
        args, kwargs = self.kek_repo.find_or_create_kek_datum.call_args
        test_tenant_model = args[0]
        test_full_plugin_name = args[1]
        self.assertEqual(self.tenant_model, test_tenant_model)
        plugin_name = utils.generate_fullname_for(plugin_inst)
        self.assertEqual(plugin_name, test_full_plugin_name)

    def _config_private_methods(self):
        """Mock store_crypto's private methods."""

        # Mock _indicate_bind_completed().
        indicate_bind_completed_config = {
            'return_value': None
        }
        self.indicate_bind_completed_patcher = mock.patch(
            'barbican.plugin.store_crypto._indicate_bind_completed',
            **indicate_bind_completed_config)
        self.bind_completed_mock = self._start_patcher(
            self.indicate_bind_completed_patcher)


class WhenTestingStoreCryptoStoreSecretAndDatum(TestSecretStoreBase):
    """Tests store_crypto.py's _store_secret_and_datum() function."""

    def setUp(self):
        super(WhenTestingStoreCryptoStoreSecretAndDatum, self).setUp()

        self.init_patchers()

    def test_without_existing_secret(self):

        self.secret_model.id = None

        store_crypto._store_secret_and_datum(
            self.context,
            self.secret_model,
            self.kek_meta_tenant_model,
            self.response_dto)

        # Verify the repository interactions.
        self._verify_secret_repository_interactions()
        self._verify_tenant_secret_repository_interactions()
        self._verify_encrypted_datum_repository_interactions()

    def test_with_existing_secret(self):
        store_crypto._store_secret_and_datum(
            self.context,
            self.secret_model,
            self.kek_meta_tenant_model,
            self.response_dto)

        # Verify the repository interactions.
        self._verify_encrypted_datum_repository_interactions()

        # Verify **not** these repository interactions.
        self.assertEqual(
            self.secret_repo.create_from.call_count, 0)
        self.assertEqual(
            self.tenant_secret_repo.create_from.call_count, 0)

    def _verify_secret_repository_interactions(self):
        """Verify the secret repository interactions."""
        self.assertEqual(
            self.secret_repo.create_from.call_count, 1)
        args, kwargs = self.secret_repo.create_from.call_args
        test_secret_model = args[0]
        self.assertEqual(self.secret_model, test_secret_model)

    def _verify_tenant_secret_repository_interactions(self):
        """Verify the tenant-secret repository interactions."""
        self.assertEqual(
            self.tenant_secret_repo.create_from.call_count, 1)
        args, kwargs = self.tenant_secret_repo.create_from.call_args
        test_tenant_secret_model = args[0]
        self.assertIsInstance(test_tenant_secret_model, models.TenantSecret)
        self.assertEqual(
            self.context.tenant_model.id, test_tenant_secret_model.tenant_id)
        self.assertEqual(
            models.States.ACTIVE, test_tenant_secret_model.status)

    def _verify_encrypted_datum_repository_interactions(self):
        """Verify the encrypted datum repository interactions."""
        self.assertEqual(
            self.datum_repo.create_from.call_count, 1)
        args, kwargs = self.datum_repo.create_from.call_args
        test_datum_model = args[0]
        self.assertIsInstance(test_datum_model, models.EncryptedDatum)
        self.assertEqual(
            self.content_type, test_datum_model.content_type)
        self.assertEqual(
            base64.b64encode(self.cypher_text), test_datum_model.cypher_text)
        self.assertEqual(
            self.response_dto.kek_meta_extended,
            test_datum_model.kek_meta_extended)


class WhenTestingStoreCryptoIndicateBindCompleted(TestSecretStoreBase):
    """Tests store_crypto.py's _indicate_bind_completed() function."""

    def test_bind_operation(self):
        kek_meta_dto = crypto.KEKMetaDTO(self.kek_meta_tenant_model)
        self.kek_meta_tenant_model.bind_completed = False

        store_crypto._indicate_bind_completed(
            kek_meta_dto, self.kek_meta_tenant_model)

        self.assertTrue(self.kek_meta_tenant_model.bind_completed)
        self.assertEqual(
            kek_meta_dto.algorithm, self.kek_meta_tenant_model.algorithm)
        self.assertEqual(
            kek_meta_dto.bit_length, self.kek_meta_tenant_model.bit_length)
        self.assertEqual(
            kek_meta_dto.mode, self.kek_meta_tenant_model.mode)
        self.assertEqual(
            kek_meta_dto.plugin_meta, self.kek_meta_tenant_model.plugin_meta)
