from tools.glassfish import asadmin
from tools.glassfish import machine

import os
import time

class Machines:

	def __init__(self, params, management_public_key_path,
			management_private_key_path, log_out):
		self.__docker_client = params["docker-client"]
		self.__image_version = params["image-version"]
		self.__container_prefix = params["container-prefix"]
		self.__management_public_key_path = management_public_key_path
		self.__management_private_key_path = management_private_key_path
		self.__log_out = log_out
		self.__machine_reg = {}

	def __image_tag(self, image_type):
		return "miquelo/glassfish-4.1.1-{}:{}".format(
			image_type,
			self.__image_version
		)

	def __container_name(self, name):
		return "{}-{}".format(self.__container_prefix, name)

	def __branch_name(self):
		if self.__image_version == "latest":
			return "master"
		return self.__image_version

	def __find_container(self, name):
		container_name = self.__container_name(name)
		cont_list = self.__docker_client.containers(all=True, filters={
			"name": container_name
		})
		return Container(
			self.__docker_client,
			cont_list[0],
			self.__public_key_target_path(container_name),
			self.__management_private_key_path
		) if len(cont_list) > 0 else None

	def __create_container(self, name, image_type, user_path,
			authorized_key_paths):
		container_name = self.__container_name(name)
		public_key_target_path = self.__public_key_target_path(container_name)
		binds = {
			public_key_target_path: {
				"bind": self.__ssh_public_key_path(user_path),
				"mode": "rw"
			}
		}
		binds.update({
			authorized_key_path: {
				"bind": self.__ssh_authorized_key_path(
					user_path,
					"authorized-key-{}.pem".format(i + 1)
				),
				"mode": "ro"
			}
			for i, authorized_key_path
			in enumerate(authorized_key_paths or ())
		})
		host_config = self.__docker_client.create_host_config(
			binds=binds
		)
		return Container(
			self.__docker_client,
			self.__docker_client.create_container(
				image=self.__image_tag(image_type),
				name=container_name,
				environment={
					# "DOCKER_CONTAINER_NAME": name
				},
				host_config=host_config
			),
			public_key_target_path,
			self.__management_private_key_path
		)

	def __machine_up(self, name, image_type, user_path,
			authorized_key_paths=None):
		if name in self.__machine_reg:
			return self.__machine_reg[name]

		cont = self.__find_container(name)
		if cont is None:
			cont = self.__create_container(
				name,
				image_type,
				user_path,
				authorized_key_paths
			)
		elif cont.outdated(self.__image_tag(image_type)):
			cont.remove()
			cont = self.__create_container(
				name,
				image_type,
				user_path,
				authorized_key_paths
			)

		running_cont = cont.running()
		self.__machine_reg[name] = running_cont.container_machine()
		return self.__machine_reg[name]

	def __public_key_target_path(self, container_name):
		path = os.path.expanduser("~/.docker-glassfish")
		if not os.path.exists(path):
			os.mkdir(path)
		path = os.path.join(path, "{}.pem".format(container_name))
		if not os.path.exists(path):
			f = open(path, "a")
			f.close()
		return path

	def __ssh_path(self, user_path, path):
		return os.path.join(
			os.path.join(user_path, ".ssh"),
			path
		)

	def __ssh_public_key_path(self, user_path):
		return os.path.join(
			os.path.join(user_path, ".ssh"),
			"id_rsa.pub"
		)

	def __ssh_authorized_key_path(self, user_path, path):
		return os.path.join(
			self.__ssh_path(user_path, "authorized_keys.dir"),
			path
		)

	def __build_image(self, image_type):
		for line in self.__docker_client.build(
			path="https://github.com/{}#{}:{}-{}".format(
				"miquelo/docker-glassfish.git",
				self.__branch_name(),
				"image/glassfish-4.1.1",
				image_type
			),
			tag=self.__image_tag(image_type),
			rm=True
		):
			line_dict = eval(line.decode("UTF-8"))
			if "stream" in line_dict:
				self.__log_out.write(line_dict["stream"])

	def build_images(self):
		self.__build_image("debian")
		self.__build_image("server")

	def asadmin(self, ip_address):
		return asadmin.AsAdmin(
			ip_address,
			self.__management_private_key_path
		)

	def machine_das(self):
		return self.__machine_up(
			"appserver-das",
			"server",
			"/usr/lib/glassfish4", [
				self.__management_public_key_path
			]
		)

	def machine_inst(self, name, authorized_das_key_paths=None):
		authorized_key_paths = [
			self.__management_public_key_path
		]
		if authorized_das_key_paths is not None:
			authorized_key_paths.extend(authorized_das_key_paths)
		return self.__machine_up(
			"appserver-inst-{}".format(name),
			"server",
			"/usr/lib/glassfish4",
			authorized_key_paths
		)

class Container:

	def __init__(self, client, cont, public_key_target_path,
			management_private_key_path):
		self.__client = client
		self.__cont = cont
		self.__public_key_target_path = public_key_target_path
		self.__management_private_key_path = management_private_key_path

	def __refresh_cont(self):
		cont_list = self.__client.containers(all=True, filters={
			"id": self.__cont["Id"]
		})
		self.__cont = cont_list[0]

	def outdated(self, image_tag):
		cont_image_tag = self.__cont["Image"]
		return image_tag != cont_image_tag # or image_tag.endswith(":latest")

	def running(self):
		self.__refresh_cont()
		if self.__cont["State"] != "running":
			self.__client.start(container=self.__cont["Id"])
			self.__refresh_cont()
		return RunningContainer(
			self.__client,
			self.__cont,
			self.__public_key_target_path,
			self.__management_private_key_path
		)

	def remove(self):
		self.__client.remove_container(
			container=self.__cont["Id"],
			force=True
		)

class RunningContainer:

	def __init__(self, client, cont, public_key_target_path,
			management_private_key_path):
		self.__client = client
		self.__cont = cont
		self.__public_key_target_path = public_key_target_path
		self.__management_private_key_path = management_private_key_path

	def __ip_address(self):
		network = self.__cont["NetworkSettings"]["Networks"]["bridge"]
		return network["IPAddress"]

	def container_machine(self):
		return machine.Machine(
			self.__ip_address(),
			self.__public_key_target_path,
			self.__management_private_key_path
		)
