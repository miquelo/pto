import paramiko
import re
import sys
import random
import string
import time

from tools.glassfish import domain

class AsAdmin:

	def __init__(self, ssh_ip_address, ssh_private_key_path):
		self.__ssh_client = paramiko.SSHClient()
		self.__ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		self.__ssh_ip_address = ssh_ip_address
		self.__ssh_private_key_path = ssh_private_key_path
		self.__domain_dir = "/var/glassfish/domains"
		self.__node_dir = "/var/glassfish/nodes"

	def __enter__(self):
		# XXX Race condition: Waiting SSH server to be ready
		for i in range(0, 5):
			try:
				self.__ssh_client.connect(
					hostname=self.__ssh_ip_address,
					username="glassfish",
					allow_agent=False,
					look_for_keys=False,
					key_filename=self.__ssh_private_key_path
				)
				return self
			except ConnectionRefusedError:
				time.sleep(1)
			except paramiko.ssh_exception.NoValidConnectionsError:
				time.sleep(1)
		raise LookupError("SSH server not available")

	def __exit__(self, type, value, tp):
		self.__ssh_client.close()

	def __run(self, cmd, params=None, host=None, port=None, user=None,
			passwords=None):
		try:
			passwords_file_path = None
			if passwords is not None:
				passwords_file_path = "$HOME/passwords-{}.txt".format(
					"".join(
						random.choice(string.ascii_lowercase + string.digits)
						for _ in range(8)
					)
				)
				for name, value in passwords.items():
					self.__ssh_client.exec_command("echo {}={} >> {}".format(
						name,
						value,
						passwords_file_path
					))

			args = "$HOME/bin/asadmin --terse"
			if host is not None:
				args = "{} --host {}".format(args, host)
			if port is not None:
				args = "{} --port {}".format(args, port)
			if user is not None:
				args = "{} --user {}".format(args, user)
			if passwords_file_path is not None:
				args = "{} --passwordfile {}".format(
					args,
					passwords_file_path
				)
			args = "{} --echo true --interactive false {}".format(args, cmd)
			if params is not None:
				for param in params:
					args = "{} {}".format(args, param)
			stdin, stdout, stderr = self.__ssh_client.exec_command(args)

			print(stdout.readline().strip())

			line = stderr.readline().strip()
			while len(line) > 0:
				print(line)
				line = stderr.readline().strip()

			line = stdout.readline().strip()
			while len(line) > 0:
				yield line
				line = stdout.readline().strip()

		finally:
			if passwords_file_path is not None:
				self.__ssh_client.exec_command("rm {}".format(passwords_file_path))

	def __install_stored_master_password(self, domain_name, node_name,
			node_host):
		cmd = "" \
			"ssh -oStrictHostKeyChecking=no glassfish@{} " \
			"'mkdir -p /var/glassfish/nodes/{}/agent'".format(
			node_host,
			node_name
		)
		print(cmd)
		stdin, stdout, stderr = self.__ssh_client.exec_command(cmd)
		line = stderr.readline().strip()
		while len(line) > 0:
			print(line)
			line = stderr.readline().strip()

		cmd = "" \
			"scp -oStrictHostKeyChecking=no {}/{}/config/master-password " \
			"glassfish@{}:{}/{}/agent".format(
				self.__domain_dir,
				domain_name,
				node_host,
				self.__node_dir,
				node_name
			)
		print(cmd)
		stdin, stdout, stderr = self.__ssh_client.exec_command(cmd)
		line = stderr.readline().strip()
		while len(line) > 0:
			print(line)
			line = stderr.readline().strip()

	@property
	def ssh_ip_address(self):
		return self.__ssh_ip_address

	def setup_ssh(self, hosts, password=None, generate_key=False):
		params = []
		params.extend([
			"--generatekey",
			"true" if generate_key else "false"
		])
		params.extend(hosts)
		for line in self.__run("setup-ssh", params, passwords={
			"AS_ADMIN_SSHPASSWORD": password
		} if password is not None else None):
			pass

	def list_domains(self):
		params = []
		params.append("--long")
		params.extend([ "--header", "false" ])
		for line in self.__run("list-domains", params):
			values = line.split()
			yield {
				"name": values[0],
				"admin-host": values[1],
				"admin-port": values[2],
				"running": values[3],
				"restart-required": values[4]
			}

	def create_domain(self, master_password, host, admin_user, admin_password,
			name):
		params = []
		params.extend([ "--usemasterpassword", "true" ])
		params.extend([ "--savemasterpassword", "true" ])
		params.append(name)
		for line in self.__run(
			"create-domain",
			params,
			host=host,
			user=admin_user,
			passwords={
				"AS_ADMIN_MASTERPASSWORD": master_password,
				"AS_ADMIN_PASSWORD": admin_password
		}):
			print(line)

	def list_nodes_ssh(self, admin_host, admin_port, admin_user,
			admin_password):
		params = []
		params.append("--long")
		for line in self.__run(
			"list-nodes-ssh",
			params,
			host=admin_host,
			port=admin_port,
			user=admin_user,
			passwords={
				"AS_ADMIN_PASSWORD": admin_password
		}):
			if not line.startswith("Node Name"):
				values = line.split()
				yield {
					"name": values[0],
					"type": values[1],
					"host": values[2]
				}

	# TODO Restore domain_name from admin_host:admin_port with asking for...
	# ...  own domain name and remove parameter
	def create_node_ssh(self, admin_host, admin_port, admin_user,
			admin_password, host, name, domain_name):
		params = []
		params.extend([ "--nodehost", host ])
		params.extend([ "--nodedir", self.__node_dir ])
		params.append(name)
		for line in self.__run(
			"create-node-ssh",
			params,
			host=admin_host,
			port=admin_port,
			user=admin_user,
			passwords={
				"AS_ADMIN_PASSWORD": admin_password
		}):
			print(line)
		self.__install_stored_master_password(domain_name, name, host)

	def start_domain(self, name, master_password):
		params = []
		params.append(name)
		for line in self.__run(
			"start-domain",
			params,
			passwords={
				"AS_ADMIN_MASTERPASSWORD": master_password
		}):
			print(line)

	def stop_domain(self, name, master_password):
		params = []
		params.append(name)
		for line in self.__run(
			"stop-domain",
			params,
			passwords={
				"AS_ADMIN_MASTERPASSWORD": master_password
		}):
			print(line)

	def restart_domain(self, name, master_password):
		params = []
		params.append(name)
		for line in self.__run(
			"restart-domain",
			params,
			passwords={
				"AS_ADMIN_MASTERPASSWORD": master_password
		}):
			print(line)

	def start_cluster(self, admin_host, admin_port, admin_user, admin_password,
			name, master_password):
		params = []
		params.append(name)
		for line in self.__run(
			"start-cluster",
			params,
			host=admin_host,
			port=admin_port,
			user=admin_user,
			passwords={
				"AS_ADMIN_MASTERPASSWORD": master_password,
				"AS_ADMIN_PASSWORD": admin_password
		}):
			print(line)

	def stop_cluster(self, admin_host, admin_port, admin_user, admin_password,
			name, master_password):
		params = []
		params.append(name)
		for line in self.__run(
			"stop-cluster",
			params,
			host=admin_host,
			port=admin_port,
			user=admin_user,
			passwords={
				"AS_ADMIN_MASTERPASSWORD": master_password,
				"AS_ADMIN_PASSWORD": admin_password
		}):
			print(line)

	def enable_secure_admin(self, admin_host, admin_port, admin_user,
			admin_password):
		for line in self.__run(
			"enable-secure-admin",
			host=admin_host,
			port=admin_port,
			user=admin_user,
			passwords={
				"AS_ADMIN_PASSWORD": admin_password
		}):
			print(line)

	def set(self, admin_host, admin_port, admin_user, admin_password, name,
			value):
		params = []
		params.append("{}={}".format(name, value))
		for line in self.__run(
			"set",
			params,
			host=admin_host,
			port=admin_port,
			user=admin_user,
			passwords={
				"AS_ADMIN_PASSWORD": admin_password
		}):
			print(line)
