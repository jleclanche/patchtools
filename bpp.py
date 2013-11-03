"""
python-bpp
Blizzard patching protocol
"""
import json
import os
from collections import namedtuple
from urllib.request import urlopen
from urllib.error import HTTPError
from xml.dom.minidom import getDOMImplementation, parseString
from xml.parsers.expat import ExpatError


class ServerError(Exception):
	pass

Record = namedtuple("Record", ("program", "component", "version"))
ResponseRecord = namedtuple("Record", ("program", "component", "text"))

class BPPConnection(object):
	def __init__(self, program):
		self.program = program
		self.records = []

	def getXML(self):
		dom = getDOMImplementation().createDocument(None, "version", None)
		dom.documentElement.setAttribute("program", self.program)
		for record in self.records:
			e = dom.createElement("record")
			e.setAttribute("program", record.program)
			e.setAttribute("component", record.component)
			e.setAttribute("version", record.version)
			dom.documentElement.appendChild(e)

		return dom.documentElement.toxml("utf-8")

	def open(self, server):
		xml = self.getXML()

		try:
			f = urlopen(server, xml)
		except HTTPError as e:
			raise ServerError("Could not open %s: %s" % (server, e))

		response = f.read()
		if not response:
			raise ServerError("No response from server")

		self.responseRecords = []
		for e in parseString(response).getElementsByTagName("record"):
			record = ResponseRecord(e.getAttribute("program"), e.getAttribute("component"), e.firstChild.data.strip())
			self.responseRecords.append(record)

		return self.responseRecords

	def addRecord(self, program, component, version):
		self.records.append(Record(program, component, version))


class ConfigurationError(Exception):
	pass


class TorrentFile(object):
	def __init__(self, info):
		self.info = info
		self.path = "/".join(info["path"])
		self.size = info["length"]

	def __repr__(self):
		return "%s(%r)" % (self.__class__.__name__, self.path)

class MFILPatch(object):
	def __init__(self, configUrl, torrentHash, mfilHash, build):
		self.configUrl = configUrl
		self.torrentHash = torrentHash
		self.mfilHash = mfilHash
		self.build = int(build)

	def _urlopen(self, url):
		try:
			f = urlopen(url)
		except HTTPError as e:
			raise ServerError("Could not open %s: %s" % (url, e))
		return f

	def _path(self, path):
		return self._server + path

	def configure(self, program, server=None):
		self.program = program
		f = self._urlopen(self.configUrl)

		response = f.read()
		try:
			self.dom = parseString(response)
		except ExpatError as e:
			raise ServerError("Invalid XML file at %s: %s" % (self.configUrl, e))

		if self.dom.documentElement.tagName != "config":
			raise ServerError("XML file at %s is not a valid config file")

		# read the available servers
		self.servers = {}
		for version in self.dom.getElementsByTagName("version"):
			if version.getAttribute("product") == self.program:
				for e in version.getElementsByTagName("server"):
					self.servers[e.getAttribute("id")] = e.getAttribute("url")

		if server:
			# Set the preferred server
			if server not in self.servers:
				raise ConfigurationError("Server %r is not available. Valid ids are: %s" % (server, ", ".join(self.servers.keys())))
			self._server = self.servers[server]
		else:
			# Just pick whatever
			self._server = self.servers.values()[0]

	def mfil(self):
		return self._path("%s-%i-%s.mfil" % (self.program.lower(), self.build, self.mfilHash))

	def tfil(self):
		return self._path("%s-%i-%s.torrent" % (self.program.lower(), self.build, self.torrentHash))

	def getTorrent(self):
		return self._urlopen(self.tfil()).read()

	def getDirectDownload(self):
		from bcoding import bdecode
		torrent = self.getTorrent()
		d = bdecode(torrent)
		bases = d["direct download"].split("|")
		# Always make sure the url ends with a slash, so we don't
		# get a different result depending on whether it does or not
		for i, base in enumerate(bases):
			if not base.endswith("/"):
				bases[i] += "/"

		# cache the file list
		torrentFiles = set()
		for f in d["info"]["files"]:
			if f["type"] == "alignment":
				continue
			torrentFiles.add(TorrentFile(f))

		return bases, torrentFiles


class Resource(object):
	def _urlopen(self, url):
		try:
			f = urlopen(url)
		except HTTPError as e:
			raise ServerError("Could not open %s: %s" % (url, e))
		return f

	def data(self):
		if not hasattr(self, "_data"):
			self._data = self._urlopen(self.url()).read()
		return self._data

	def cache(self, path):
		if os.path.exists(path):
			return

		base = os.path.dirname(path)
		if not os.path.exists(base):
			os.makedirs(base)

		with open(path, "wb") as f:
			data = self.data()
			f.write(data)
			print("Written %i bytes to %s" % (len(data), path))


class SimpleResource(Resource):
	def __init__(self, base, name):
		if not base.endswith("/"):
			base += "/"
		self.base = base
		self.name = name

	def __repr__(self):
		return "<SimpleResource %s>" % (self.name)

	def url(self):
		return self.base + self.name


class Blob(Resource):
	BLOB_FORMAT = "%s_%s_%s.blob"
	GAME = "game"
	INSTALL = "install"

	def __init__(self, base, hash, type, program):
		if not base.endswith("/"):
			base += "/"
		self.base = base
		self.hash = hash
		self.type = type
		self.program = program

	def __repr__(self):
		return "<Blob %s>" % (self.name())

	def name(self):
		return self.BLOB_FORMAT % (self.program.lower(), self.type, self.hash)

	def url(self):
		return self.base + self.name()


class Catalog(Resource):
	"""
	Used in the Battle.net desktop client
	"""

	CATALOGS_KEY = "catalogs"
	CLOG_FORMAT = "%s-%s.clog"

	def __init__(self, base, hash, name=None):
		if not base.endswith("/"):
			base += "/"
		self.base = base
		self.hash = hash
		self.name = name

	def __repr__(self):
		if self.name:
			return "<Catalog %s: %s>" % (self.name, self.hash)
		else:
			return "<Catalog %s>" % (self.hash)

	def filename(self):
		return self.CLOG_FORMAT % (self.name, self.hash)

	def path(self):
		return "%s/%s/%s" % (self.hash[0:2], self.hash[2:4], self.hash)

	def url(self):
		return self.base + self.path()

	def fetch(self):
		d = json.loads(self.data().decode("utf-8"))

		self.catalogs = {}
		for key, c in d[self.CATALOGS_KEY].items():
			assert "hash" in c
			self.catalogs[key] = self.__class__(self.base, c["hash"], name=key)

		return self.catalogs, d
