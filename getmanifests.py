#!/usr/bin/env python

import os
import json
from urllib.request import urlopen
from urllib.error import HTTPError
"""
http://dist.blizzard.com.edgesuite.net/wow-pod/beta/0E1FFF21/NA/15890.direct/wowb-15961-B7747C2BF9CF22D4ACBB1AA17B644AB0.mfil
http://ak.worldofwarcraft.com.edgesuite.net/wow-pod/public-test/15050.direct/wowt-15595-1F77FE028D645FFDE55D4CAA01A3CB7A.torrent
http://ak.worldofwarcraft.com.edgesuite.net/wow-pod/wowt-13316-22B71346E1073AE32DA806262A9AE825.torrent
http://blizzard.vo.llnwd.net/o16/content/wow-pod-retail/NA/15050.direct/wow-15595-7B4881788F3979AE698A8420A294C4E0.torrent
"""

bases = {
	"http://ak.worldofwarcraft.com.edgesuite.net/wow-pod/ptr/streaming",
	"http://ak.worldofwarcraft.com.edgesuite.net/d3-pod/20FB5BE9/NA/7162.direct",
	"http://ak.worldofwarcraft.com.edgesuite.net/d3-pod-retail/NA/8370.direct",
	"http://ak.worldofwarcraft.com.edgesuite.net/sc2-pod/beta/2FDD100A/NA/21571.direct",
	"http://ak.worldofwarcraft.com.edgesuite.net/wow-pod-retail/NA/12911.streaming",
	"http://ak.worldofwarcraft.com.edgesuite.net/wow-pod/public-test/15050.direct",
	"http://ak.worldofwarcraft.com.edgesuite.net/wow-pod",
	"http://blizzard.vo.llnwd.net/o16/content/wow-pod-retail/NA/15050.direct",
	"http://dist.blizzard.com.edgesuite.net/wow-pod/beta/0E1FFF21/NA/15890.direct",
	"http://dist.blizzard.com.edgesuite.net/wow-pod/beta/0E1FFF21/NA/15827.direct",
	"http://dist.blizzard.com.edgesuite.net/wow-pod/beta/0E1FFF21/NA/15464.direct",
}

MPQ_BASE_DIR = os.environ.get("MPQ_BASE_DIR", os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")), "mpq"))

NOT_FOUND = "File not found."

if __name__ == "__main__":
	db = []
	filesystem = []
	tried = []

	with open("db.json", "r") as f:
		db = json.loads(f.read())

	with open("tried.json", "r") as f:
		tried = json.loads(f.read())

	for root, dirnames, filenames in os.walk(MPQ_BASE_DIR):
		for file in filenames:
			if file.endswith(".mfil") or file.endswith(".torrent"):
				filesystem.append(file)

	for d in db:
		for type in ("torrent", "mfil"):
			hash = d["mHash" if type == "mfil" else "tHash"]
			build = d["build"]
			program = d["program"].lower()
			file = "%s-%s-%s.%s" % (program, build, hash, type)

			if file in filesystem:
				print("Already got %r, skipping" % (file))
				continue
			#else:
			#	print(file)

			for base in bases:
				url = "%s/%s" % (base, file)

				if url in tried:
					print("Already tried %r, skipping" % (url))
					continue

				try:
					f = urlopen(url)
					x = f.read(len(NOT_FOUND))
					if x != NOT_FOUND:
						print("Downloading... %r" % (url))
						x += f.read()
						with open(file, "wb") as out:
							out.write(x)
					else:
						tried.append(url)

				except HTTPError as e:
					print("%s: %s" % (url, e))
					tried.append(url)
					continue

	with open("tried.json", "w") as f:
		f.write(json.dumps(tried))
