import docker
import getpass
import os
import tools.artifacts.maven
import tools.glassfish

class Updater:

	def __init__(self, config):
		self.__management_public_key_path = config.get(
			name="management-public-key",
			title="Management public key",
			def_value=self.__default_management_public_key()
		)
		self.__management_private_key_path = config.get(
			name="management-private-key",
			title="Management private key",
			def_value=self.__default_management_private_key()
		)

		self.__docker_config_environment = config.get(
			name="docker-config-environment",
			title="Docker configuration comes from environment",
			ex_values="yes/no",
			def_value="no"
		) == "yes"

		if not self.__docker_config_environment:
			self.__docker_endpoint = config.get(
				name="docker-endpoint",
				title="Docker endpoint",
				def_value=self.__default_docker_endpoint()
			)
			self.__docker_tls_enabled = config.get(
				name="docker-tls-enabled",
				title="Docker communication is secured",
				ex_values="yes/no",
				def_value=self.__default_docker_tls_enabled()
			) == "yes"

			if self.__docker_tls_enabled:
				self.__docker_certificate = config.get(
					name="docker-certificate",
					title="Docker certificate path",
					def_value=self.__default_docker_certficate()
				)
				self.__docker_key = config.get(
					name="docker-key",
					title="Docker key path",
					def_value=self.__default_docker_key()
				)

		self.__glassfish_image_version = config.get(
			name="glassfish-image-version",
			title="GlassFish image version",
			def_value="latest"
		)
		self.__glassfish_container_prefix = config.get(
			name="glassfish-container-prefix",
			title="GlassFish container prefix",
			def_value="pto-test"
		)
		self.__glassfish_instance_count = config.get(
			name="glassfish-instance-count",
			title="Number of available instances by GlassFish",
			def_value="1"
		)

		self.__domain_name = config.get(
			name="domain-name",
			title="Domain name",
			def_value="pto-test"
		)
		self.__domain_master_password = config.get(
			name="domain-master-password",
			title="Domain master password",
			secret=True
		)

		self.__domain_admin_name = config.get(
			name="domain-admin-name",
			title="Domain administrator name",
			def_value="admin"
		)
		self.__domain_admin_password = config.get(
			name="domain-admin-password",
			title="Domain administrator password",
			secret=True
		)

		self.__docker_client = None
		self.__glassfish_agent = None

		self.__repo = tools.artifacts.maven.LocalRepository()

	def __enter__(self):
		if self.__docker_config_environment:
			base_url = self.__docker_env_endpoint()
			tls = docker.tls.TLSConfig(
				client_cert=(
					self.__docker_env_certificate(),
					self.__docker_env_key()
				)
			) if self.__docker_env_tls_enabled() else None
		else:
			base_url = self.__docker_endpoint
			tls = docker.tls.TLSConfig(
				client_cert=(
					self.__docker_certificate,
					self.__docker_key
				)
			) if self.__docker_tls_enabled else None
		self.__docker_client = docker.APIClient(
			base_url=base_url,
			tls=tls,
			version="1.23"
		)

		self.__glassfish_agent = tools.glassfish.restore(
			"docker",
			{
				"docker-client": self.__docker_client,
				"image-version": self.__glassfish_image_version,
				"container-prefix": self.__glassfish_container_prefix
			},
			self.__management_public_key_path,
			self.__management_private_key_path,
			self.__domain_master_password,
			build_images=True
		)
		return self

	def __exit__(self, type, value, tp):
		self.__glassfish_agent.close()
		self.__docker_client.close()

	def __default_management_public_key(self):
		return os.path.expanduser("~/.ssh/id_rsa.pub")

	def __default_management_private_key(self):
		return os.path.expanduser("~/.ssh/id_rsa")

	def __default_docker_endpoint(self):
		try:
			return self.__docker_env_endpoint()
		except KeyError:
			return "unix:///var/run/docker.sock"

	def __default_docker_tls_enabled(self):
		return "yes" if self.__docker_env_tls_enabled() else "no"

	def __default_docker_certificate(self):
		try:
			return self.__docker_env_certificate()
		except KeyError:
			return "cert.pem"

	def __default_docker_key(self):
		try:
			return self.__docker_env_key()
		except KeyError:
			return "key.pem"

	def __docker_env_endpoint(self):
		return os.environ["DOCKER_HOST"]

	def __docker_env_tls_enabled(self):
		return "DOCKER_CERT_PATH" in os.environ

	def __docker_env_certificate(self):
		return os.path.join(os.environ["DOCKER_CERT_PATH"], "cert.pem")

	def __docker_env_key(self):
		return os.path.join(os.environ["DOCKER_CERT_PATH"], "key.pem")

	def __glassfish_domain(self):
		for domain in self.__glassfish_agent.domains():
			if domain.name == self.__domain_name:
				return domain
		return self.__glassfish_agent.create_domain(
			self.__domain_admin_name,
			self.__domain_admin_password,
			self.__domain_name
		)

	def __configure(self, cluster):
		cluster.deploy(
			name="pto-ma-web",
			artifact=self.__repo.artifact(
				group_id="net.preparatusopos.member",
				artifact_id="pto-ma-web",
				version="0.1.0-SNAPSHOT",
				packaging="war"
			),
			context_root="/member",
			force=True
		)
		cluster.start()

	def __domain_node(self, mgd_domain, name):
		for node in mgd_domain.nodes():
			if name == node.name:
				return node.restored()
		return mgd_domain.create_node(name)

	def __domain_cluster(self, mgd_domain, name):
		for cluster in mgd_domain.clusters():
			if name == cluster.name:
				return cluster
		return mgd_domain.create_cluster(name)

	def __domain_instance(self, node, name, cluster):
		for inst in node.instances():
			if name == inst.name:
				return inst
		return node.create_instance(name, cluster)

	def update(self):
		mgd_domain = self.__glassfish_domain().manage(
			self.__domain_admin_name,
			self.__domain_admin_password
		)

		node01 = self.__domain_node(mgd_domain, "node-01")
		node02 = self.__domain_node(mgd_domain, "node-02")
		node03 = self.__domain_node(mgd_domain, "node-03")

		cluster = self.__domain_cluster(mgd_domain, "cluster-01")
		inst01 = self.__domain_instance(node01, "inst-01", cluster)
		inst02 = self.__domain_instance(node02, "inst-02", cluster)
		inst03 = self.__domain_instance(node03, "inst-03", cluster)

		self.__configure(cluster)
