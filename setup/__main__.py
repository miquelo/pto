import argparse
import configparser
import configurator
import importlib
import sys

__setup_ini_file_name = "setup.ini"

def __main__():
	parser = argparse.ArgumentParser(
		prog=sys.argv[0]
	)
	parser.add_argument(
		"provider",
		metavar="provider",
		type=str,
		nargs=1,
		help="updater provider module name"
	)
	parser.add_argument(
		"configuration",
		metavar="configuration",
		type=str,
		nargs=1,
		help="configuration name"
	)
	args = parser.parse_args(sys.argv[1:])
	prov_name = args.provider[0]
	config_name = args.configuration[0]
	
	prov = importlib.import_module("updater.{}".format(prov_name))
	setup_ini = configparser.ConfigParser()
	
	try:
		with open(__setup_ini_file_name, "r") as setup_ini_file:
			setup_ini.read_file(setup_ini_file)
	except FileNotFoundError:
		pass
		
	with open(__setup_ini_file_name, "w") as setup_ini_file:
		try:
			if not config_name in setup_ini:
				setup_ini[config_name] = {}
			with prov.Updater(
				configurator.Configurator(setup_ini[config_name])
			) as updater:
				updater.update()
		finally:
			setup_ini.write(setup_ini_file)
			
__main__()

