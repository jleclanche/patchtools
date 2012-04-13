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
import sys
from argparse import ArgumentParser
try:
	from io import StringIO
except ImportError:
	from cStringIO import StringIO
try:
	from urllib.request import urlopen
except ImportError:
	from urllib import urlopen

from xml.dom.minidom import getDOMImplementation, parseString
from xml.parsers.expat import ExpatError

from bencode import _decode_dict as parseTorrent
from mfil import MFIL2 as MFIL


LIVE = 1
PTR  = 2
MPQ_BASE_DIR = os.environ.get("MPQ_BASE_DIR", os.path.join(os.path.expanduser("~"), "mpq", "WoW"))

class ServerError(Exception):
	pass

class Downloader(object):

	SERVER = "http://%s.patch.battle.net:1119/patch"

	def __init__(self, *args):
		arguments = ArgumentParser(prog="patchdl")
		arguments.add_argument("-c", "--client", type=int, dest="client", default=LIVE, help="client version (1 for live, 2 for PTR)")
		arguments.add_argument("-s", "--server", type=str, dest="server", default="enUS", help="server to connect to (locale xxXX or public-test)")
		arguments.add_argument("--base", type=str, dest="base", default=MPQ_BASE_DIR, help="Base directory for file storage")
		arguments.add_argument("--check-sizes", action="store_true", dest="checksizes", help="Check all downloaded files against their respective sizes. Not available for all downloads.")
		arguments.add_argument("--debug", action="store_true", dest="debug", help="enable debug output")
		arguments.add_argument("--component", type=str, dest="component", default="enUS", help="program component")
		arguments.add_argument("--mfil", type=str, dest="mfil", help="Force a specific mfil url")
		arguments.add_argument("--tool", type=int, dest="tool", help="Tool version (if downloading tool patches)")
		arguments.add_argument("--network", type=str, dest="network", default="akamai", help="Content Distribution Network (possible choices are akamai, att, limelight)")
		arguments.add_argument("--show-avi", action="store_true", dest="avi", help="include .avi files in the output")
		arguments.add_argument("--show-downloaded", action="store_true", dest="downloaded", help="include downloaded files in the output")
		arguments.add_argument("--post-data", type=str, dest="data", help="Send this data (emulates wget --post-data)")
		arguments.add_argument("program", type=str, nargs="?", default="WoW", help="possible choices are WoW, WoWB, WoWT, S2, D3, D3B, Agnt, Clnt")
		self.args = arguments.parse_args(*args)

	def debug(self, output):
		if self.args.debug:
			print(output)

	def error(self, output):
		print("error: %s" % (output))

	def warn(self, output):
		sys.stderr.write("warning: %s\n" % (output))

	def exec_(self):
		xml = self.getProgramXML()
		server = self.SERVER % (self.args.server)

		self.debug("xml=%r" % (xml))

		f = urlopen(server, xml)

		response = f.read()
		if not response:
			raise ServerError("No response from %s" % (server))

		downloadTypes = {
			"Agnt": self.downloadAgent,
			"Bnet": self.downloadClassic,
			"Clnt": self.downloadAgent,
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
				self.error("Don't know how to download.")
				continue

			try:
				downloadTypes[serverProgram](record)
			except ServerError as e:
				self.error("Error: %s" % (e))
				continue

	def downloadAgent(self, record):
		data = record.firstChild.data.strip()
		self.debug("data=%r" % (data))

		incrementalTorrent, fullTorrent, toBuild, fromBuild, zero = data.split(";")

		files = set()
		for url in (incrementalTorrent, fullTorrent):
			torrent = urlopen(url).read()
			if torrent == "File not found.":
				raise ServerError("File not found: %r" % (tfilUrl))

			d, length = parseTorrent(torrent)
			directDownload = d["direct download"]
			self.debug("directDownload=%r" % (directDownload))
			# Always make sure the url ends with a slash, so we don't
			# get a different result depending on whether it does or not
			if not directDownload.endswith("/"):
				directDownload += "/"

			for f in d["info"]["files"]:
				files.add("/".join(f["path"]))

		self.outputFiles(files, directDownload)

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
			raise ServerError("File not found: %r" % (tfilUrl))

		d, length = parseTorrent(torrent)
		directDownload = d[b"direct download"].decode("utf-8")
		self.debug("directDownload=%r" % (directDownload))
		# Always make sure the url ends with a slash, so we don't
		# get a different result depending on whether it does or not
		if not directDownload.endswith("/"):
			directDownload += "/"

		mfil = MFIL(urlopen(mfilUrl))

		files = set()
		for file, fileInfo in mfil["file"].items():

			if isinstance(fileInfo["size"], str) and int(fileInfo["size"]) == 0:
				# Directory
				continue

			files.add(file)

		self.outputFiles(files, directDownload, mfil["file"])

	def getBaseUrl(self, base, product, network):
		response = urlopen(base).read()
		if response == "File not found.":
			raise ServerError("File not found: %r" % (base))

		try:
			dom = parseString(response)
		except ExpatError as e:
			raise ServerError("Invalid XML in %r: %s" %(base, e))

		assert dom.documentElement.tagName == "config"
		def getServer(dom, product, network=None):
			for version in dom.getElementsByTagName("version"):
				#self.debug("version=%s" % (version.toxml()))
				if version.getAttribute("product") == product:
					for server in version.getElementsByTagName("server"):
						if not network or server.getAttribute("id") == network:
							return server.getAttribute("url")

		ret = getServer(dom, product, network)
		if not ret:
			self.warn("Could not find a base url for %r with %r as preferred network. Trying with all networks." % (base, network))

		ret = getServer(dom, product)
		if not ret:
			raise ServerError("Could not find a base url for %r" % (base))

		return ret

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

		return dom.documentElement.toxml("utf-8")

	def outputFiles(self, files, baseUrl, mfil):
		baseDir = baseUrl.split("/")[-2]
		targetDir = os.path.join(self.args.base, self.args.program, baseDir)
		total = 0
		output = []
		if files:
			for file in files:
				path = os.path.join(targetDir, file)
				if os.path.exists(path):
					if self.args.checksizes:
						disksize = os.path.getsize(path)
						filesize = int(mfil[file]["size"])
						self.debug("disksize=%r, filesize=%r" % (disksize, filesize))
						if disksize != filesize:
							self.error("Size mismatch: %r (Expected %r, got %r)" % (path, filesize, disksize))
							output.append("curl -# --fail --create-dirs %s -o %s" % (baseUrl + file, path))

						continue

					elif not self.args.downloaded:
						continue

				if file.endswith(".avi"):
					if not self.args.avi and not self.args.checksizes:
						continue

				output.append("curl -# --fail --create-dirs %s -o %s" % (baseUrl + file, path))
				total += 1

		print(" &&\n".join(output))
		print("%i/%i files" % (total, len(files)))

def main():
	app = Downloader(sys.argv[1:])
	exit(app.exec_())

if __name__ == "__main__":
	main()
