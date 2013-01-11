#!/usr/bin/env python3
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
from urllib.request import urlopen
from urllib.error import HTTPError
from xml.dom.minidom import getDOMImplementation, parseString
from xml.parsers.expat import ExpatError

from bencode import _decode_dict as parseTorrent
from mfil import MFIL2 as MFIL


PROGRAM = "patchdl"
LIVE = 1
PTR  = 2
MPQ_BASE_DIR = os.environ.get("MPQ_BASE_DIR", os.path.join(os.path.expanduser("~"), "mpq"))

class ServerError(Exception):
	pass

class Cache(object):
	"""
	Simple caching mechanism that assumes file integrity by file name.
	Only useful for mfil/tfils as those have file hashes in the file name.
	"""
	def __init__(self, program):
		HOME = os.path.expanduser("~")
		XDG_CACHE_HOME  = os.environ.get("XDG_CACHE_HOME", os.path.join(HOME, ".cache"))
		self.path = os.path.join(XDG_CACHE_HOME, program)
		self._makedirs(self.path)

	def _makedirs(self, dir):
		if not os.path.exists(dir):
			os.makedirs(dir)

	def _path(self, item):
		path = os.path.join(self.path, os.path.basename(item))
		self._makedirs(os.path.dirname(path))
		return path

	def get(self, item):
		path = self._path(item)
		if os.path.exists(path):
			return path

	def set(self, item, data):
		path = self._path(item)
		with open(path, "wb") as f:
			f.write(data)

		return path

class Downloader(object):

	SERVER = "http://%s.patch.battle.net:1119/patch"

	def __init__(self, *args):
		arguments = ArgumentParser(prog=PROGRAM)
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

		self.cache = Cache(PROGRAM)

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

		try:
			f = urlopen(server, xml)
		except HTTPError as e:
			self.error("Could not open %s: %s" % (server, e))
			return 1

		response = f.read()
		if not response:
			self.error("No response from %s" % (server))
			return 1

		downloadTypes = {
			"Agnt": self.downloadAgent,
			"Bnet": self.downloadClassic,
			"Clnt": self.downloadAgent,
			"D3": self.downloadMfil,
			"D3B": self.downloadMfil,
			"D3T": self.downloadMfil,
			"S2": self.downloadMfil,
			"S2B": self.downloadMfil,
			"Tool": self.downloadClassic,
			"WoW": self.downloadMfil,
			"WoWB": self.downloadMfil,
			"WoWT": self.downloadMfil,
		}

		for record in parseString(response).getElementsByTagName("record"):
			serverProgram = record.getAttribute("program")
			component = record.getAttribute("component")
			print("%s::%s" % (serverProgram, component))
			self.debug("record=%r" % (record.toxml()))

			if serverProgram not in downloadTypes:
				self.error("Don't know how to download.")
				continue

			if component == "blob":
				self.downloadBlob(record)
				continue

			try:
				downloadTypes[serverProgram](record)
			except ServerError as e:
				self.error(e)
				continue

		return 0

	def downloadAgent(self, record):
		data = record.firstChild.data.strip()
		self.debug("data=%r" % (data))

		component = record.getAttribute("component")
		if component == "cdn":
			cdns = data.split("|")
			print("Available CDNs: %s" % (", ".join(cdns)))
			return

		incrementalTorrent, fullTorrent, toBuild, fromBuild, zero = data.split(";")

		files = set()
		for url in (incrementalTorrent, fullTorrent):
			torrent = urlopen(url).read()
			if torrent == "File not found.":
				raise ServerError("File not found: %r" % (tfilUrl))

			d, length = parseTorrent(torrent)
			directDownload = d[b"direct download"].decode("utf-8")
			self.debug("directDownload=%r" % (directDownload))

			# As of S2 1.5, directDownload supports mirrors, e.g.:
			# "http://dist.blizzard.com.edgesuite.net/sc2-pod-retail/NA/22342.direct|http://llnw.blizzard.com/sc2-pod-retail/NA/22342.direct"
			directDownload = directDownload.split("|")[0]

			# Always make sure the url ends with a slash, so we don't
			# get a different result depending on whether it does or not
			if not directDownload.endswith("/"):
				directDownload += "/"

			for f in d[b"info"][b"files"]:
				path = "/".join(str(x, "utf-8") for x in f[b"path"])
				if path != "alignment":
					files.add(path)

		self.outputFiles(files, directDownload)

	def downloadBlob(self, record):
		data = record.firstChild.data.strip()
		self.debug("data=%r" % (data))
		print(data)

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
		self.debug("baseUrl=%r" % (baseUrl))
		tfilUrl = baseUrl + "%s-%i-%s.torrent" % (program.lower(), build, thash)
		if self.args.mfil:
			mfilUrl = self.args.mfil
		else:
			mfilUrl = baseUrl + "%s-%i-%s.mfil" % (program.lower(), build, mhash)

		self.debug("tfilUrl=%r" % (tfilUrl))
		self.debug("mfilUrl=%r" % (mfilUrl))
		self.debug("build=%r" % (build))

		torrent = self.cache.get(tfilUrl)
		if torrent:
			self.debug("cache hit: torrent=%r" % (torrent))
			torrent = open(torrent, "rb").read()
		else:
			self.debug("Downloading torrent file...")
			try:
				torrent = urlopen(tfilUrl).read()
			except HTTPError as e:
				raise ServerError("Could not open %s: %s" % (tfilUrl, e))

			if torrent == "File not found.":
				raise ServerError("File not found: %r" % (tfilUrl))

			path = self.cache.set(tfilUrl, torrent)
			self.debug("Cache torrent path=%r" % (path))

		self.debug("Parsing torrent...")
		d, length = parseTorrent(torrent)
		directDownload = d[b"direct download"].decode("utf-8")
		self.debug("directDownload=%r" % (directDownload))

		# As of S2 1.5, directDownload supports mirrors, e.g.:
		# "http://dist.blizzard.com.edgesuite.net/sc2-pod-retail/NA/22342.direct|http://llnw.blizzard.com/sc2-pod-retail/NA/22342.direct"
		directDownload = directDownload.split("|")[0]

		# Always make sure the url ends with a slash, so we don't
		# get a different result depending on whether it does or not
		if not directDownload.endswith("/"):
			directDownload += "/"

		mfil = self.cache.get(mfilUrl)
		if mfil:
			self.debug("cache hit: mfil=%r" % (mfil))
		else:
			self.debug("Downloading manifest file...")
			try:
				mfil = urlopen(mfilUrl).read()
			except HTTPError as e:
				raise ServerError("Could not open %s: %s" % (mfilUrl, e))

			mfil = self.cache.set(mfilUrl, mfil)
			self.debug("Cache manifest path=%r" % (path))

		mfil = MFIL(mfil)

		files = set()
		for file, fileInfo in mfil["file"].items():

			if isinstance(fileInfo["size"], str) and int(fileInfo["size"]) == 0:
				# Directory
				continue

			files.add(file)

		if True: # add a flag to disable?
			for f in d[b"info"][b"files"]:
				path = "/".join(str(x, "utf-8") for x in f[b"path"])
				if path != "alignment":
					files.add(path)

		self.outputFiles(files, directDownload, mfil["file"])

	def getBaseUrl(self, base, product, network):
		try:
			response = urlopen(base).read()
		except HTTPError as e:
			raise ServerError("%s: %r" % (e, base))
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
			return self.args.data.encode("utf-8")

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
		record.setAttribute("program", "Agnt")
		record.setAttribute("component", "cdn")
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

	def outputFiles(self, files, baseUrl, mfil=None):
		formats = {
			"curl": "curl -# --fail --create-dirs %(url)s -o %(output)s &&",
			"plain": "%(url)s",
		}
		outputFormat = formats["curl"]

		baseDir = baseUrl.split("/")[-2]
		targetDir = os.path.join(self.args.base, self.args.program, baseDir)
		total = 0
		output = []
		if files:
			for file in files:
				path = os.path.join(targetDir, file)
				if os.path.exists(path):
					if self.args.checksizes:
						if not mfil:
							self.error("Size checks are not available for this download type.")

						if file not in mfil:
							# Happens when we have files only present in the torrent file
							self.warn("File %r not present in mfil. Skipping." % (file))
							continue

						disksize = os.path.getsize(path)
						filesize = int(mfil[file]["size"])
						self.debug("disksize=%r, filesize=%r" % (disksize, filesize))
						if disksize != filesize:
							self.error("Size mismatch: %r (Expected %r, got %r)" % (path, filesize, disksize))
							output.append(outputFormat % {"url": baseUrl + file, "output": path})

						continue

					elif not self.args.downloaded:
						continue

				if file.endswith(".avi"):
					if not self.args.avi and not self.args.checksizes:
						continue

				output.append(outputFormat % {"url": baseUrl + file, "output": path})
				total += 1

		print("\n".join(output))
		print("%i/%i files" % (total, len(files)))

def main():
	app = Downloader(sys.argv[1:])
	exit(app.exec_())

if __name__ == "__main__":
	main()
