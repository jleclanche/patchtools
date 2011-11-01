#!/usr/bin/env python

import os
from argparse import ArgumentParser
from cStringIO import StringIO
from urllib import urlopen
from xml.dom.minidom import getDOMImplementation, parseString

from bencode import decode_dict as parseTorrent
from mfil import MFIL2 as MFIL

LIVE = 1
PTR  = 2

servers = {
	LIVE: "http://enus.patch.battle.net:1119/patch",
	PTR:  "http://public-test.patch.battle.net:1119/patch",
}

class Downloader(object):
	def __init__(self, *args):
		arguments = ArgumentParser(prog="patchdl")
		arguments.add_argument("-c", "--client", type=int, dest="client", default=LIVE, help="client version (1 for live, 2 for PTR)")
		arguments.add_argument("-s", "--server", type=int, dest="server", default=LIVE, help="server version (1 for live, 2 for PTR)")
		arguments.add_argument("--base", type=str, dest="base", default=os.path.join(os.environ.get("HOME"), "mpq"), help="Base directory for file storage")
		arguments.add_argument("--debug", action="store_true", dest="debug", help="enable debug output")
		arguments.add_argument("--component", type=str, dest="component", default="enUS", help="program component")
		arguments.add_argument("--mfil", type=str, dest="mfil", help="Force a specific mfil url")
		arguments.add_argument("--network", type=str, dest="network", default="akamai", help="Content Distribution Network (possible choices are akamai, att, limelight)")
		arguments.add_argument("--show-avi", action="store_true", dest="avi", help="include .avi files in the output")
		arguments.add_argument("program", type=str, nargs="?", default="WoW", help="possible choices are WoW, S2, D3")
		self.args = arguments.parse_args(*args)

	def debug(self, output):
		if self.args.debug:
			print(output)

	def exec_(self):
		program = self.args.program
		component = self.args.component
		server = servers[self.args.server]
		xml = self.getProgramXML(program, component, self.args.client)

		self.debug("xml=%r" % (xml))

		f = urlopen(server, xml)

		response = f.read()
		if not response:
			print("No response from %s" % (server))
			return 1

		for record in parseString(response).getElementsByTagName("record"):
			serverProgram = record.getAttribute("program")
			if serverProgram == "Bnet":
				continue

			print("%s::%s" % (serverProgram, record.getAttribute("component")))

			data = record.firstChild.data.strip()
			self.debug("data=%r" % (data))

			base, thash, mhash, build = data.split(";")
			self.debug("base=%r" % (base))
			build = int(build)
			baseUrl = self.getBaseUrl(base, program, self.args.network)
			tfilUrl = baseUrl + "%s-%i-%s.torrent" % (program.lower(), build, thash)
			if self.args.mfil:
				mfilUrl = self.args.mfil
			else:
				mfilUrl = baseUrl + "%s-%i-%s.mfil" % (program.lower(), build, mhash)

			self.debug("tfilUrl=%r" % (tfilUrl))
			self.debug("mfilUrl=%r" % (mfilUrl))
			self.debug("build=%r" % (build))

			torrent = urlopen(tfilUrl).read()
			if torrent == "File not found.":
				print("File not found: %r" % (tfilUrl))
				return 1

			d, length = parseTorrent(torrent, 0)
			directDownload = d["direct download"]
			self.debug("directDownload=%r" % (directDownload))
			baseDir = directDownload.split("/")[-1]

			mfil = MFIL(urlopen(mfilUrl))

			dirs = set()
			files = set()
			for file, fileInfo in mfil["file"].items():
				targetDir = os.path.join(self.args.base, program, baseDir)
				if not os.path.exists(targetDir):
					dirs.add(targetDir)
				path = os.path.join(targetDir, file)

				if os.path.exists(path):
					continue

				if int(fileInfo["size"]) == 0:
					# Directory
					#print("mkdir -p %s" % (path))
					continue

				if file.endswith(".avi"):
					if not self.args.avi:
						continue

				files.add((file, path))
				#print("%s/%s" % (directDownload, file))

			if dirs:
				for directory in dirs:
					print("mkdir -p", directory)

			if files:
				for file, path in files:
					print("wget %s/%s -O %s &&" % (directDownload, file, path))
				print("%i new files" % (len(files)))
			else:
				print("No new files")

			return 0

	def getBaseUrl(self, base, product, preferredServer):
		dom = parseString(urlopen(base).read())
		assert dom.documentElement.tagName == "config"
		for version in dom.getElementsByTagName("version"):
			if version.getAttribute("product") == product:
				for server in version.getElementsByTagName("server"):
					if server.getAttribute("id") == preferredServer:
						return server.getAttribute("url")

	def getProgramXML(self, program, component, version):
		dom = getDOMImplementation().createDocument(None, "version", None)
		dom.documentElement.setAttribute("program", program)

		record = dom.createElement("record")
		record.setAttribute("program", "Bnet")
		record.setAttribute("component", "Win")
		record.setAttribute("version", "1")
		dom.documentElement.appendChild(record)

		record = dom.createElement("record")
		record.setAttribute("program", program)
		record.setAttribute("component", component)
		record.setAttribute("version", str(version))
		dom.documentElement.appendChild(record)

		return dom.documentElement.toxml()

def main():
	import sys

	app = Downloader(sys.argv[1:])
	exit(app.exec_())

if __name__ == "__main__":
	main()
