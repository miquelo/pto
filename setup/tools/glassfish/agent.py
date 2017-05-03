import sys

from tools.glassfish import domain

class Agent:

	def __init__(self, machines, master_password):
		self.__machines = machines
		self.__master_password = master_password

	def __enter__(self):
		return self

	def __exit__(self, type, value, tp):
		self.close()

	def __find_domain(self, name):
		for d in self.domains():
			if d.name == name:
				return d
		raise LookupError("Domain {} not found".format(name))

	def domains(self):
		machine_das = self.__machines.machine_das()
		with machine_das.asadmin() as admin:
			for d in admin.list_domains():
				yield domain.Domain(
					self.__machines,
					machine_das,
					self.__master_password,
					d["name"],
					d["admin-host"],
					d["admin-port"],
					d["running"] == "true",
					d["restart-required"] == "true"
				)

	def create_domain(self, admin_user, admin_password, name):
		with self.__machines.machine_das().asadmin() as admin:
			admin.create_domain(
				self.__master_password,
				admin.ssh_ip_address,
				admin_user,
				admin_password,
				name
			)
			created_domain = self.__find_domain(name)
			created_domain.prepare(admin, admin_user, admin_password)
			return self.__find_domain(name)

	def close(self):
		pass
