#!/usr/bin/env python
"""
WoW Patches:
	patchdl WoW
WoW PTR (live-to-ptr):
	patchdl WoW --server public-test
WoW PTR (ptr-to-ptr):
	patchdl WoW --server public-test --client 2

D3:
	patchdl D3 --server public-test

S2:
	patchdl S2 --component <os> --client <version>

Tool:
	patchdl --tool <version>
"""

import os
from argparse import ArgumentParser
from cStringIO import StringIO
from urllib import urlopen
from xml.dom.minidom import getDOMImplementation, parseString

from bencode import decode_dict as parseTorrent
from mfil import MFIL2 as MFIL


LIVE = 1
PTR  = 2

class Downloader(object):

	SERVER = "http://%s.patch.battle.net:1119/patch"

	def __init__(self, *args):
		arguments = ArgumentParser(prog="patchdl")
		arguments.add_argument("-c", "--client", type=int, dest="client", default=LIVE, help="client version (1 for live, 2 for PTR)")
		arguments.add_argument("-s", "--server", type=str, dest="server", default="enUS", help="server to connect to (locale xxXX or public-test)")
		arguments.add_argument("--base", type=str, dest="base", default=os.path.join(os.environ.get("HOME"), "mpq"), help="Base directory for file storage")
		arguments.add_argument("--debug", action="store_true", dest="debug", help="enable debug output")
		arguments.add_argument("--component", type=str, dest="component", default="enUS", help="program component")
		arguments.add_argument("--mfil", type=str, dest="mfil", help="Force a specific mfil url")
		arguments.add_argument("--tool", type=int, dest="tool", help="Tool version (if downloading tool patches)")
		arguments.add_argument("--network", type=str, dest="network", default="akamai", help="Content Distribution Network (possible choices are akamai, att, limelight)")
		arguments.add_argument("--show-avi", action="store_true", dest="avi", help="include .avi files in the output")
		arguments.add_argument("--show-downloaded", action="store_true", dest="downloaded", help="include downloaded files in the output")
		arguments.add_argument("--post-data", type=str, dest="data", help="Send this data (emulates wget --post-data)")
		arguments.add_argument("program", type=str, nargs="?", default="WoW", help="possible choices are WoW, WoWB, WoWT, S2, D3, D3B")
		self.args = arguments.parse_args(*args)

	def debug(self, output):
		if self.args.debug:
			print(output)

	def exec_(self):
		xml = self.getProgramXML()
		server = self.SERVER % (self.args.server)

		self.debug("xml=%r" % (xml))

		f = urlopen(server, xml)

		response = f.read()
		if not response:
			print("No response from %s" % (server))
			return 1

		downloadTypes = {
			"Bnet": self.downloadClassic,
			"D3": self.downloadMfil,
			"D3B": self.downloadMfil,
			"S2": self.downloadClassic,
			"Tool": self.downloadClassic,
			"WoW": self.downloadMfil,
			"WoWB": self.downloadMfil,
			"WoWT": self.downloadMfil,
		}

		for record in parseString(response).getElementsByTagName("record"):
			serverProgram = record.getAttribute("program")
			print("%s::%s" % (serverProgram, record.getAttribute("component")))

			if serverProgram not in downloadTypes:
				print("Don't know how to download.")
				continue

			downloadTypes[serverProgram](record)

	def downloadClassic(self, record):
		data = record.firstChild.data.strip()
		self.debug("data=%r" % (data))

		base, name, md5, build = data.split(";")
		self.debug("base=%r" % (base))

		print("<binary data at %s>" % (base))

	def downloadMfil(self, record):
		program = self.args.program

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
		# Always make sure the url ends with a slash, so we don't
		# get a different result depending on whether it does or not
		if not directDownload.endswith("/"):
			directDownload += "/"
		baseDir = directDownload.split("/")[-2]

		mfil = MFIL(urlopen(mfilUrl))

		files = set()
		for file, fileInfo in mfil["file"].items():
			targetDir = os.path.join(self.args.base, program, baseDir)
			path = os.path.join(targetDir, file)

			if os.path.exists(path):
				if not self.args.downloaded:
					continue

			if isinstance(fileInfo["size"], basestring) and int(fileInfo["size"]) == 0:
				# Directory
				continue

			if file.endswith(".avi"):
				if not self.args.avi:
					continue

			files.add((file, path))
			#print("%s/%s" % (directDownload, file))

		if files:
			for file, path in files:
				print("curl -# --fail --create-dirs %s -o %s &&" % (directDownload + file, path))
			print("%i files" % (len(files)))

		return 0

	def getBaseUrl(self, base, product, network):
		response = urlopen(base).read()
		dom = parseString(response)
		assert dom.documentElement.tagName == "config"
		for version in dom.getElementsByTagName("version"):
			#self.debug("version=%s" % (version.toxml()))
			if version.getAttribute("product") == product:
				for server in version.getElementsByTagName("server"):
					if server.getAttribute("id") == network:
						return server.getAttribute("url")

	def getProgramXML(self):
		if self.args.data:
			return self.args.data

		program = self.args.program
		component = self.args.component
		clientVersion = self.args.client
		tool = self.args.tool

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
		record.setAttribute("version", str(clientVersion))
		dom.documentElement.appendChild(record)

		if tool is not None:
			record = dom.createElement("record")
			record.setAttribute("program", "Tool")
			record.setAttribute("component", "Win")
			record.setAttribute("version", str(tool))
			dom.documentElement.appendChild(record)

		return dom.documentElement.toxml()

def main():
	import sys

	app = Downloader(sys.argv[1:])
	exit(app.exec_())

if __name__ == "__main__":
	main()
