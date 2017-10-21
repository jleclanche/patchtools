#!/usr/bin/env python
"""
Usage:
	checksizes $MPQ_BASE_DIR/WoW/15050.direct/wow-15354-E998F3B63FB3ABEBBAD1AA7212209086.mfil
Check the sizes of all the files relative to that path specified in the given mfil
"""

import os
import sys
from argparse import ArgumentParser

from xml.dom.minidom import getDOMImplementation, parseString
from xml.parsers.expat import ExpatError

from bencode import _decode_dict as parseTorrent
from mfil import MFIL2 as MFIL


LIVE = 1
PTR  = 2
MPQ_BASE_DIR = os.environ.get("MPQ_BASE_DIR", os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")), "mpq"))

class ServerError(Exception):
	pass

class Downloader(object):

	SERVER = "http://%s.patch.battle.net:1119/patch"

	def __init__(self, *args):
		arguments = ArgumentParser(prog="checksizes")
		arguments.add_argument("--debug", action="store_true", dest="debug", help="enable debug output")
		arguments.add_argument("mfil", type=str, nargs="+", help="path to the mfil (must be in the same directory as the files)")
		self.args = arguments.parse_args(*args)

	def debug(self, output):
		if self.args.debug:
			print(output)

	def error(self, output):
		print("error: %s" % (output))

	def message(self, output):
		print(output)

	def exec_(self):
		for path in self.args.mfil:
			with open(path, "rb") as f:
				total, errors = 0, 0
				baseDir = os.path.dirname(path)
				f = MFIL(f)
				if len(self.args.mfil) > 1:
					self.message(path)
				for file, fileInfo in f["file"].items():
					realSize = int(fileInfo["size"])
					diskSize = os.path.getsize(os.path.join(baseDir, file))
					if realSize: # Check for directory
						total += 1
						self.debug("%r: realSize=%r, diskSize=%r, %s" % (file, realSize, diskSize, realSize == diskSize and "OK" or "FAIL"))
						if realSize != diskSize:
							errors += 1
							self.error("%r: size mismatch: expected %r, got %r" % (file, realSize, diskSize))

				self.message("%i files checked, %i errors" % (total, errors))

def main():
	app = Downloader(sys.argv[1:])
	exit(app.exec_())

if __name__ == "__main__":
	main()
