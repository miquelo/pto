from tools.glassfish import asadmin

class Machine:

	def __init__(self, ip_address, public_key_path,
			management_private_key_path):
		self.__ip_address = ip_address
		self.__public_key_path = public_key_path
		self.__management_private_key_path = management_private_key_path

	@property
	def ip_address(self):
		return self.__ip_address
		
	@property
	def public_key_path(self):
		return self.__public_key_path

	def asadmin(self):
		return asadmin.AsAdmin(
			self.__ip_address,
			self.__management_private_key_path
		)
