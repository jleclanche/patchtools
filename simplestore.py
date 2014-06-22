from io import StringIO


def load(file):
	ret = {}
	while True:
		line = file.readline().strip()
		if line.startswith("#"):
			# comment
			continue

		if not line:
			# end of file
			break

		assert line.count("=") == 1
		if line.endswith("="):
			# no value
			key = line.split("=")[0]
			value = None
		else:
			key, value = line.split(" = ")
			if " " in value:
				value = value.split()
		ret[key] = value

	return ret


def loads(text):
	return load(StringIO(text))

