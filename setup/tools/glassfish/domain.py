import json
import requests
import time

class Domain:

	def __init__(self, machines, machine_das, master_password, name, admin_host,
			admin_port, running, restart_required):
		self.__machines = machines
		self.__machine_das = machine_das
		self.__master_password = master_password
		self.__name = name
		self.__admin_host = admin_host
		self.__admin_port = admin_port
		self.__running = running
		self.__restart_required = restart_required

	@property
	def name(self):
		return self.__name

	def prepare(self, admin, admin_user, admin_password):
		admin.start_domain(self.__name, self.__master_password)
		admin.enable_secure_admin(
			self.__admin_host,
			self.__admin_port,
			admin_user,
			admin_password
		)
		admin.set(
			self.__admin_host,
			self.__admin_port,
			admin_user,
			admin_password,
			"configs.config.server-config.network-config.network-listeners."
			"network-listener.admin-listener.address",
			admin.ssh_ip_address
		)
		admin.stop_domain(self.__name, self.__master_password)

	def manage(self, admin_user, admin_password):
		domain_mgr = DomainManager(
			self.__name,
			self.__machines,
			self.__machine_das,
			self.__master_password,
			self.__admin_host,
			self.__admin_port,
			admin_user,
			admin_password
		)
		if not self.__running:
			domain_mgr.start()
			self.__running = True
		elif self.__restart_required:
			domain_mgr.restart()
			self.__restart_required = False
		return ManagedDomain(domain_mgr)

class ManagedDomain:

	def __init__(self, domain_mgr):
		self.__domain_mgr = domain_mgr

	def nodes(self):
		yield from self.__domain_mgr.list_nodes()

	def clusters(self):
		yield from self.__domain_mgr.list_clusters()

	def create_node(self, name):
		return self.__domain_mgr.create_node(name)

	def create_cluster(self, name):
		return self.__domain_mgr.create_cluster(name)

class Node:

	def __init__(self, domain_mgr, name, host):
		self.__domain_mgr = domain_mgr
		self.__name = name
		self.__host = host

	@property
	def name(self):
		return self.__name

	def restored(self):
		if not self.__domain_mgr.node_available(self.__name):
			# TODO Destroy instances and recreate node
			raise Exception("Not implemented")
		return self

	def instances(self):
		yield from self.__domain_mgr.list_instances(self.__name)

	def create_instance(self, name, cluster):
		return cluster.create_instance(name, self.__name)

class Cluster:

	def __init__(self, domain_mgr, name):
		self.__domain_mgr = domain_mgr
		self.__name = name

	@property
	def name(self):
		return self.__name

	def create_instance(self, name, node_name):
		return self.__domain_mgr.create_instance(name, node_name, self.__name)

	def deploy(self, name, artifact, context_root=None, force=False):
		with artifact.open() as f:
			self.__domain_mgr.deploy(self.__name, name, f, context_root, force)

	def start(self):
		self.__domain_mgr.start_cluster(self.__name)

class Instance:

	def __init__(self, domain_mgr, name):
		self.__domain_mgr = domain_mgr
		self.__name = name

	@property
	def name(self):
		return self.__name

class DomainManager:

	def __init__(self, name, machines, machine_das, master_password, admin_host,
			admin_port, admin_user, admin_password):
		self.__name = name
		self.__machines = machines
		self.__machine_das = machine_das
		self.__master_password = master_password
		self.__admin_host = admin_host
		self.__admin_port = admin_port
		self.__admin_user = admin_user
		self.__admin_password = admin_password

	def __target(self, path):
		return "https://{}:{}/management/domain{}".format(
			self.__admin_host,
			self.__admin_port,
			path
		)

	def __auth(self):
		return requests.auth.HTTPBasicAuth(
			self.__admin_user,
			self.__admin_password
		)

	def __node_asadmin(self, node_name):
		with self.__machine_das.asadmin() as admin:
			for node_info in admin.list_nodes_ssh(
				self.__admin_host,
				self.__admin_port,
				self.__admin_user,
				self.__admin_password
			):
				if node_name == node_info["name"]:
					return self.__machines.asadmin(node_info["host"])
			raise LookupError("Node '{}' was not found".format(node_name))

	def __entity(self, resp):
		return resp.json()["extraProperties"]["entity"]

	def __child_resources(self, resp):
		extraProperties = resp.json()["extraProperties"]
		for name, url in extraProperties["childResources"].items():
			yield name, requests.get(
				url,
				headers={
					"Accept": "application/json",
					"X-Requested-By": "GlassFish REST HTML interface"
				},
				verify=False,
				auth=self.__auth()
			)

	def start(self):
		with self.__machine_das.asadmin() as admin:
			admin.start_domain(self.__name, self.__master_password)

	def stop(self):
		with self.__machine_das.asadmin() as admin:
			admin.restart_domain(self.__name, self.__master_password)

	def restart(self):
		with self.__machine_das.asadmin() as admin:
			admin.restart_domain(self.__name, self.__master_password)

	def list_nodes(self):
		resp = requests.get(
			self.__target("/nodes/node"),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth()
		)
		for name, sub_resp in self.__child_resources(resp):
			yield Node(self, name, self.__entity(sub_resp)["nodeHost"])

	def node_available(self, node_name):
		resp = requests.get(
			self.__target("/nodes/node/{}/ping-node-ssh".format(node_name)),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth()
		)
		return resp.json()["exit_code"] == "SUCCESS"

	def create_node(self, name):
		machine = self.__machines.machine_inst(
			name, [
				self.__machine_das.public_key_path
			]
		)
		# XXX Race condition: Waiting SSH node server to be ready for...
		# ... subsequent connections
		time.sleep(5)
		with self.__machine_das.asadmin() as admin:
			admin.create_node_ssh(
				self.__admin_host,
				self.__admin_port,
				self.__admin_user,
				self.__admin_password,
				machine.ip_address,
				name,
				self.__name
			)
			return Node(self, name, machine.ip_address)

	def list_clusters(self):
		resp = requests.get(
			self.__target("/clusters/cluster"),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth()
		)
		for name, sub_resp in self.__child_resources(resp):
			yield Cluster(self, name)

	def create_cluster(self, name):
		resp = requests.post(
			self.__target("/clusters/create-cluster"),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth(),
			data={
				"id": name
			}
		)

		resp = requests.get(
			self.__target("/clusters/cluster/{}".format(name)),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth()
		)
		config_ref = self.__entity(resp)["configRef"]

		resp = requests.get(
			self.__target("/configs/config/{}/java-config".format(
				config_ref
			)),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth()
		)
		data = resp.json()["extraProperties"]["entity"]
		data["debugEnabled"] = "true"

		resp = requests.post(
			self.__target("/configs/config/{}/java-config".format(
				config_ref
			)),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth(),
			data=data
		)
		return Cluster(self, name)

	def list_instances(self, node_name):
		resp = requests.get(
			self.__target("/servers/server"),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth()
		)
		for name, sub_resp in self.__child_resources(resp):
			if self.__entity(sub_resp)["nodeRef"] == node_name:
				yield Instance(self, name)

	def create_instance(self, name, node_name, cluster_name):
		resp = requests.post(
			self.__target("/create-instance"),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth(),
			data={
				"id": name,
				"nodeagent": node_name,
				"cluster": cluster_name
			}
		)
		print(resp.json())
		return None

	def start_cluster(self, cluster_name):
		resp = requests.post(
			self.__target("/clusters/cluster/{}/start-cluster".format(
				cluster_name
			)),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth()
		)
		print(resp.json())
		return None

	def deploy(self, target, name, artifact_file, context_root, force):
		data = {
			"target": target,
			"name": name,
			"force": "true" if force else "false"
		}
		if context_root is not None:
			data["contextroot"] = context_root
		resp = requests.post(
			self.__target("/applications/application"),
			headers={
				"Accept": "application/json",
				"X-Requested-By": "GlassFish REST HTML interface"
			},
			verify=False,
			auth=self.__auth(),
			data=data,
			files={
				"id": artifact_file
			}
		)
