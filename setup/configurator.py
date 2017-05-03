import getpass

class UnknownPropertyError(Exception):

	def __init__(self, name):
		super().__init__("Unknown property {}".format(name))
		
class Configurator:

	def __init__(self, config, unattended=False):
		self.__config = config
		self.__unattended = unattended
		
	def get(self, name, title, ex_values=None, def_value=None, secret=False):
		if not name in self.__config:
			if self.__unattended:
				raise UnknownProperpertyError(name)
			value = self.__ask(title, ex_values, def_value, secret)
			if len(value) <= 0:
				value = def_value
			self.__config[name] = value
		return self.__config[name]
		
	def __ask(self, title, ex_values, def_value, secret):
		msg = title
		if ex_values is not None:
			msg = "{} ({})".format(msg, ex_values)
		if def_value is not None:
			msg = "{} [{}]".format(msg, def_value)
		print("{}:".format(msg))
		return input() if not secret else getpass.getpass("")

