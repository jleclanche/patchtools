#!/usr/bin/env python

import os
import sys
from hashlib import md5


MPQ_BASE_DIR = os.environ.get("MPQ_BASE_DIR", os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")), "mpq"))

if __name__ == "__main__":
	for root, dirnames, filenames in os.walk(MPQ_BASE_DIR):
		for file in filenames:
			if file.endswith(".mfil") or file.endswith(".torrent"):
				prog, build, expectedHash = os.path.splitext(file)[0].split("-")
				expectedHash = expectedHash.lower()
				path = os.path.join(root, file)
				with open(path, "rb") as f:
					realHash = md5(f.read()).hexdigest()
					if realHash != expectedHash:
						print("%s: expected %r, got %r" % (path, expectedHash, realHash))
#					else:
#						print("%s: OK" % (file))



	for file in sys.argv[1:]:
		with open(file, "rb") as f:
			print(md5(f.read()).hexdigest())
