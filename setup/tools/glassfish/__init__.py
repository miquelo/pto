import importlib
import sys

from tools.glassfish import agent, infrastructure

def restore(ifrs_type, ifrs_params, management_public_key_path,
		management_private_key_path, master_password, build_images=False,
		log_out=sys.stdout):
	ifrs = importlib.import_module(
		"tools.glassfish.infrastructure.{}".format(ifrs_type)
	)
	machines = ifrs.Machines(
		ifrs_params,
		management_public_key_path,
		management_private_key_path,
		log_out
	)
	if build_images:
		machines.build_images()
	return agent.Agent(machines, master_password)
