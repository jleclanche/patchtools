#!/usr/bin/env python

import requests
import hashlib
import os
import re
from urllib.parse import urlparse
from bpp import NGDPConnection, BPPConnection, Catalog

USER_AGENT = "NGDP12"
MPQ_BASE_DIR = os.environ.get("MPQ_BASE_DIR", os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")), "mpq"))
MD5_REGEX = re.compile(r"[0-9a-f]{32}", re.I)


def get_catalog(version):
	conn = BPPConnection(program="ngdp")
	conn.addRecord(program="Clog", component="PUB", version=str(version))
	conn.addRecord(program="Agnt", component="cdn", version="1")
	records = conn.open("http://public-test.patch.battle.net:1119/patch")
	cdns = []
	path, hash = "", ""
	for record in records:
		if record.program == "Agnt" and record.component == "cdn":
			cdns = record.text.split("|")
		elif record.program == "Clog":
			path, hash = record.text.split(";")

	# We only really need one url. Maybe use the other one(s) as fallback.
	return Catalog(cdns[0], path, hash, save_path=MPQ_BASE_DIR)


def cache_old(url):
	path = urlparse(url).path
	save_path = os.path.join(MPQ_BASE_DIR, "NGDPv0") + os.path.dirname(path)
	filename = os.path.basename(path)
	full_path = os.path.join(save_path, filename)

	if os.path.exists(full_path):
		return

	if not os.path.exists(save_path):
		os.makedirs(save_path)

	r = requests.get(url)
	if r.status_code == 404:
		print("Not found: %r" % (r.url))
		return
	print("%r -> %r" % (url, full_path))

	assert r.status_code == 200, r.url

	checksum = MD5_REGEX.findall(filename)
	if checksum:
		checksum = checksum[0].lower()
		content_hash = hashlib.md5(r.content).hexdigest()
		assert content_hash == checksum, "%r != %r" % (content_hash, checksum)

	with open(full_path, "wb") as f:
		f.write(r.content)


if __name__ == "__main__":
	import sys
	if len(sys.argv) > 1:
		version = sys.argv[1]
	else:
		version = 14
	catalog = get_catalog(version)
	# Old catalogs:
	# catalog = Catalog("dist.blizzard.com.edgesuite.net", "tools-pod/bna/cache", "45743849d79f0d8b21c4a15d24784d4f")
	# catalog = Catalog("dist.blizzard.com.edgesuite.net", "tools-pod/bna/cache", "53edb19ea85ae425aa5f48c4e39e7f55")
	# catalog = Catalog("dist.blizzard.com.edgesuite.net", "tools-pod/bna/cache", "8ed65f975dc4e830c44bf885332a219b")
	# catalog = Catalog("dist.blizzard.com.edgesuite.net", "tools-pod/bna/cache", "d0cb714772d51f35bf96475ea120a7a2")
	# catalog = Catalog("dist.blizzard.com.edgesuite.net", "tools-pod/bna/cache", "e8abcaca9b130e806c4baed122d4385c")

	print(repr(catalog))
	catalog.preload()

	for lang, clog in catalog.regions.items():
		for product, d in clog.root["installs"].items():

			if "instructions_url" not in d:
				# old-style catalog
				other_urls = set()

				if "configuration" in d:
					# eg. http://dist.blizzard.com.edgesuite.net/tools-pod/bna/cache/b5/05/b5056174e18346a7c6c5a1e06cc0e828
					for lang, dd in d["configuration"].items():
						for key, url in dd.items():
							if key != "instructions_url":
								other_urls.add(url)
					server = d["configuration"]["enus"]["instructions_url"]
				else:
					for lang, dd in d.items():
						if isinstance(dd, dict):
							for key, url in dd.items():
								if key != "instructions_url":
									other_urls.add(url)
					server = d["enus"]["instructions_url"]

				for url in other_urls:
					cache_old(url)

			else:
				server = d["instructions_url"].replace("{REGION_CODE}", "us") # XXX
			if server.endswith(":1119/patch"):
				# "Skipping old patch system
				continue
			ngdp = NGDPConnection(server, save_path=MPQ_BASE_DIR)

			# XXX Will there be more versions once stuff comes out of beta?
			buildconfig = ngdp.build_config(region="xx")
			cdnconfig = ngdp.cdn_config(region="xx")

			for archive in cdnconfig["archives"]:
				ngdp.cache_hash(archive, type="data")

		# XXX We only need one lang, they're all the same.
		break

