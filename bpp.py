"""
python-bpp
Blizzard patching protocol
"""

import json
import os
import struct
import requests
import simplestore
from binascii import hexlify
from collections import namedtuple
from hashlib import md5
from io import BytesIO
from math import ceil
from urllib.parse import urlparse
from urllib.request import urlopen
from urllib.error import HTTPError
from xml.dom.minidom import getDOMImplementation, parseString
from xml.parsers.expat import ExpatError


Record = namedtuple("Record", ("program", "component", "version"))
ResponseRecord = namedtuple("Record", ("program", "component", "text"))


class ServerError(Exception):
	pass


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


class BlizzardCSV(object):
	def __init__(self, text):
		self.text = text
		rows = text.strip().splitlines()
		self.header = rows[0].split("|") if rows else []
		self.rows = [c.split("|") for c in rows[1:]]
		self.column_names = [c.split("!")[0].lower() for c in self.header]

	def get(self, row, column):
		column = column.lower()
		index = self.column_names.index(column)
		return row[index]


class NGDPConnection(object):
	def __init__(self, server, save_path):
		self.server = server
		self.save_path = save_path
		self.base_path = None

		self.cdn = None
		self._cache = {}

	def _cached_csv(self, path):
		if path not in self._cache:
			self._cache[path] = BlizzardCSV(self._query(path).text)
		return self._cache[path]

	def _query(self, path):
		r = requests.get(self.server + path)
		return r

	def blobs(self):
		return self._cached_csv("/blobs")

	def cdns(self):
		return self._cached_csv("/cdns")

	def versions(self):
		return self._cached_csv("/versions")

	def blob_install(self):
		return self._query("/blob/install")

	def blob_game(self):
		return self._query("/blob/game")

	def _get_config(self, region, column):
		if not self.cdn:
			cdns = self.cdns()
			assert cdns.rows, repr(cdns.text)
			host = cdns.get(cdns.rows[0], "hosts")
			path = cdns.get(cdns.rows[0], "path")
			self.set_cdn(host, path)

		versions = self.versions()
		for row in versions.rows:
			if versions.get(row, "region") == region:
				hash = versions.get(row, column)
				path = self.cache_hash(hash, type="config")
				if path is None:
					print("WARNING: %r missing. Ignoring..." % (hash))
					continue
				with open(path, "r") as f:
					return simplestore.load(f)

	def _data_md5(self, data):
		h = data.read(8)
		magic, header_size = struct.unpack(">4si", h)
		assert magic == b"BLTE", repr(magic)
		h += data.read(header_size-8)
		return md5(h).hexdigest()

	def build_config(self, region="xx"):
		return self._get_config(region, "buildconfig")

	def cdn_config(self, region="xx"):
		return self._get_config(region, "cdnconfig")

	def cache_data_index(self, hash):
		assert self.cdn
		assert self.base_path
		url, path = self.get_paths(hash, "index")
		if not os.path.exists(path):
			_prep_dir_for(path)
			r = requests.get(url)
			assert r.status_code == 200

			# calculate the .index md5
			data = BytesIO(r.content)
			data.seek(-12, os.SEEK_END)
			entries, = struct.unpack("i", data.read(4))
			blocks = ceil(entries / 170)
			blocks_len = blocks * 24

			data.seek(-28 - blocks_len, os.SEEK_END)
			index_hash = md5(data.read(blocks_len)).digest()
			hash_chk = data.read(8)
			# We only deal with 8 byte md5
			assert index_hash[:8] == hash_chk, "%r != %r" % (index_hash[:8], hash_chk)

			data.seek(0)
			for i in range(blocks):
				block_hash = md5(data.read(4096)).digest()
				pos = data.tell()
				data.seek(blocks * (4096+16) + i*8)
				hash_chk = data.read(8)
				assert block_hash[:8] == hash_chk, "%r != %r for block %r" % (block_hash[:8], hash_chk, i)
				data.seek(pos)

			# Write the file now
			with open(path, "wb") as f:
				print("Writing to %r" % (path))
				f.write(r.content)

	def cache_hash(self, hash, type):
		assert self.cdn
		assert self.base_path
		url, path = self.get_paths(hash, type)
		if type == "data":
			index = self.cache_data_index(hash)
		if not os.path.exists(path):
			_prep_dir_for(path)
			print("Downloading %r" % (url))
			r = requests.get(url)
			if r.status_code != 200:
				print("Got HTTP %r" % (r.status_code))
				return None

			if type == "data":
				...
				# download the .index file too

				#content_hash = self._data_md5(BytesIO(r.content))
				#if hash != content_hash:
				#	print("%r != %r" % (hash, content_hash))

			elif type == "config":
				content_hash = md5(r.content).hexdigest()
				assert hash == content_hash

			with open(path, "wb") as f:
				f.write(r.content)

		return path

	def get_paths(self, hash, type):
		if type == "index":
			url = "%s/%s/%s.index" % (self.cdn, "data", _hash(hash))
			path = os.path.join(self.base_path, _hash(hash) + ".index")
		else:
			url = "%s/%s/%s" % (self.cdn, type, _hash(hash))
			path = os.path.join(self.base_path, _hash(hash))
		return url, path

	def set_cdn(self, host, path, scheme="http"):
		self.cdn = "%s://%s/%s" % (scheme, host, path)
		self.base_path = os.path.join(self.save_path, "NGDP", path)


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


def _hash(hash):
	"Helper that returns <hash:0-2>/<hash:2-4>/<hash>"
	return "%s/%s/%s" % (hash[0:2], hash[2:4], hash)


def _prep_dir_for(filename):
	"Helper that ensures the directory for \a filename exists"
	dirname = os.path.dirname(filename)
	if not os.path.exists(dirname):
		os.makedirs(dirname)


class BaseCatalog(object):
	def __init__(self, server, path, hash, region_code, save_path, scheme="http"):
		if path.startswith("http://"):
			# Support for old catalogs
			path = urlparse(path).path[1:].lstrip("/")

		self.server = server
		self.path = path
		self.scheme = scheme
		self.hash = hash
		self.save_path = save_path
		self.region_code = region_code

		self.base_path = os.path.join(save_path, "Clog", path)

	def __str__(self):
		return self.root.__str__()

	def __repr__(self):
		return "<LazyCatalog at %r>" % (self.get_paths(self.hash)[0])

	@property
	def root(self):
		if not hasattr(self, "_root"):
			self._root = self.get_json(self.hash)
		return self._root

	def cache(self, hash):
		url, path = self.get_paths(hash)
		if not os.path.exists(path):
			_prep_dir_for(path)
			r = requests.get(url)
			assert md5(r.content).hexdigest() == hash
			with open(path, "wb") as f:
				print("Downloading %r to %r" % (r.url, path))
				f.write(r.content)

		return path

	def get_json(self, hash):
		path = self.cache(hash)
		with open(path, "r") as f:
			return json.load(f)

	def get_paths(self, hash):
		url = "%s://%s/%s/%s" % (self.scheme, self.server, self.path, _hash(hash))
		path = os.path.join(self.base_path, _hash(hash))
		return url, path

	def preload(self):
		# Cache the root hash by just accessing it
		self.root


class Catalog(BaseCatalog):
	def __init__(self, *args, **kwargs):
		kwargs["region_code"] = None
		super().__init__(*args, **kwargs)

	def __repr__(self):
		return "<Catalog at %r>" % (self.get_paths(self.hash)[0])

	@property
	def regions(self):
		ret = {}
		for region, d in self.root["catalogs"].items():
			ret[region] = BaseCatalog(self.server, self.path, d["hash"], region, self.save_path, self.scheme)
		return ret

	def preload(self):
		for catalog in self.regions.values():
			catalog.preload()

		if "manifest" not in self.root:
			print("WARNING: No manifest found. Old catalog?")
			return

		for filename, resource in self.root["manifest"]["lookup"].items():
			path = self.cache(resource)
			link_path = os.path.join(self.save_path, "Clog", filename)
			if not os.path.exists(link_path):
				print("Linking %r -> %r" % (path, link_path))
				_prep_dir_for(link_path)
				os.symlink(path, link_path)
