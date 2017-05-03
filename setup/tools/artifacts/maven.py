import os

class LocalArtifact:

	def __init__(self, path):
		self.__path = path
		
	def open(self):
		return open(self.__path, "rb")
		
class LocalRepository:

	def __init__(self):
		self.__base_path = os.path.expanduser("~/.m2/repository")
		
	def artifact(self, group_id, artifact_id, version, packaging="jar"):
		comps = []
		comps.append(self.__base_path)
		comps.extend(group_id.split("."))
		comps.append(artifact_id)
		comps.append(version)
		comps.append("{}-{}.{}".format(artifact_id, version, packaging))
		return LocalArtifact(os.path.join(*comps))

