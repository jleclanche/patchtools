#!/usr/bin/env python

import os
import bpp


def humanizedsize(bytes, precision=1):
	"""
	Return a humanized string representation of a number of bytes.
	"""
	abbrevs = (
		(1<<50, "PiB"),
		(1<<40, "TiB"),
		(1<<30, "GiB"),
		(1<<20, "MiB"),
		(1<<10, "KiB"),
		(1, "bytes")
	)
	if bytes == 1:
		return "1 byte"
	for factor, suffix in abbrevs:
		if bytes >= factor:
			break
	return "%.*f %s" % (precision, bytes / factor, suffix)

MPQ_BASE_DIR = os.environ.get("MPQ_BASE_DIR", os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")), "mpq"))


def cache_blob(blob):
	directory = blob.base.split("/")[-2]
	baseDir = os.path.join(MPQ_BASE_DIR, blob.program, directory)
	if not os.path.exists(baseDir):
		os.makedirs(baseDir)
	path = os.path.join(baseDir, blob.name())
	if not os.path.exists(path):
		data = blob.data()
		with open(path, "wb") as f:
			f.write(data)
		print("Written %i bytes to %s" % (len(data), path))

def cache_clog(clog):
	baseDir = os.path.join(MPQ_BASE_DIR, "Clog", *clog.base.split("/")[-3:-1])
	if not os.path.exists(baseDir):
		os.makedirs(baseDir)
	name = "%s-%s.clog" % (clog.name, clog.hash)
	path = os.path.join(baseDir, name)
	if not os.path.exists(path):
		data = clog.data()
		with open(path, "wb") as f:
			f.write(data)
		print("Written %i bytes to %s" % (len(data), path))


def main():
	records = []

	live = bpp.BPPConnection(program="Release1")
	live.addRecord(program="Agnt", component="blob", version="1")
	live.addRecord(program="Agnt", component="cdn", version="1")
	live.addRecord(program="Agnt", component="cfg", version="1")
	live.addRecord(program="Agnt", component="Win", version="1")

	live.addRecord(program="Bnet", component="Win", version="1")

	live.addRecord(program="Clnt", component="blob", version="1")
	live.addRecord(program="Clnt", component="Win", version="1")

	live.addRecord(program="bd3", component="Win", version="1")
	live.addRecord(program="BD3R", component="Win", version="1")
	live.addRecord(program="BS2R", component="Win", version="1")
	live.addRecord(program="BWWR", component="Win", version="1")
	live.addRecord(program="BBNR", component="Win", version="1")
	live.addRecord(program="BCLT", component="blob", version="1")
	live.addRecord(program="D3", component="blob", version="1")
	live.addRecord(program="D3", component="enUS", version="1")
	live.addRecord(program="D3T", component="enUS", version="2")

	live.addRecord(program="bs2", component="Win", version="1")
	live.addRecord(program="S2", component="enUS", version="1")
	live.addRecord(program="S2", component="blob", version="1")

	live.addRecord(program="bwow", component="Win", version="1")
	live.addRecord(program="WoW", component="Win", version="1")
	live.addRecord(program="WoW", component="enUS", version="1")
	live.addRecord(program="WoW", component="enUS", version="3")
	live.addRecord(program="WoW", component="enUS", version="4")
	live.addRecord(program="WoW", component="blob", version="1")

	records += live.open("http://enUS.patch.battle.net:1119/patch")


	liveMac = bpp.BPPConnection(program="Release1Mac")
	liveMac.addRecord(program="Agnt", component="Mac", version="1")
	liveMac.addRecord(program="Bnet", component="Mac", version="1")
	liveMac.addRecord(program="Clnt", component="Mac", version="1")

	liveMac.addRecord(program="bwow", component="Mac", version="1")
	liveMac.addRecord(program="WoW", component="Mac", version="1")

	liveMac.addRecord(program="bd3", component="Mac", version="1")
	liveMac.addRecord(program="bs2", component="Mac", version="1")
	liveMac.addRecord(program="BD3R", component="Mac", version="1")
	liveMac.addRecord(program="BS2R", component="Mac", version="1")
	liveMac.addRecord(program="BWWR", component="Mac", version="1")
	liveMac.addRecord(program="BBNR", component="Mac", version="1")

	records += liveMac.open("http://enUS.patch.battle.net:1119/patch")

	#live.addRecord(program="TCG", component="blob", version="1")


	ptr = bpp.BPPConnection(program="Test1")
	ptr.addRecord(program="Agnt", component="blob", version="1")
	ptr.addRecord(program="Agnt", component="cfg", version="1")
	ptr.addRecord(program="Agnt", component="cdn", version="1")
	ptr.addRecord(program="AgtB", component="blob", version="1")
	ptr.addRecord(program="AgtB", component="Win", version="1")
	ptr.addRecord(program="Bnet", component="Win", version="1")
	ptr.addRecord(program="Clnt", component="blob", version="1")

	ptr.addRecord(program="Clog", component="PUB", version="1")
	ptr.addRecord(program="Clog", component="PUB", version="2")
	ptr.addRecord(program="Clog", component="PUB", version="3")

	ptr.addRecord(program="D3", component="blob", version="1")
	ptr.addRecord(program="D3", component="enUS", version="1")
	ptr.addRecord(program="D3B", component="blob", version="1")
	ptr.addRecord(program="D3B", component="enUS", version="3")
	ptr.addRecord(program="D3T", component="blob", version="1")
	ptr.addRecord(program="D3T", component="enUS", version="2")

	ptr.addRecord(program="S2", component="blob", version="1")
	ptr.addRecord(program="S2B", component="enUS", version="3")
	ptr.addRecord(program="S2B", component="blob", version="1")
	ptr.addRecord(program="S2T", component="blob", version="1")

	ptr.addRecord(program="bwow", component="Win", version="1")
	ptr.addRecord(program="WoW", component="blob", version="1")
	ptr.addRecord(program="WoW", component="enUS", version="1")
	ptr.addRecord(program="WoWT", component="enUS", version="1")
	ptr.addRecord(program="WoWB", component="enUS", version="1")
	ptr.addRecord(program="WoWB", component="enUS", version="3")

	ptr.addRecord(program="TCGB", component="blob", version="1")

	records += ptr.open("http://public-test.patch.battle.net:1119/patch")


	ptr2 = bpp.BPPConnection(program="Test2")
	ptr2.addRecord(program="Bnet", component="Win", version="2")
	ptr2.addRecord(program="WoW", component="enUS", version="2")
	ptr2.addRecord(program="WoWT", component="enUS", version="2")

	records += ptr2.open("http://public-test.patch.battle.net:1119/patch")


	ptrMac = bpp.BPPConnection(program="Test2")

	ptrMac.addRecord(program="AgtB", component="Mac", version="1")
	ptrMac.addRecord(program="Bnet", component="Mac", version="1")
	ptrMac.addRecord(program="BnaB", component="Mac", version="1")
	ptrMac.addRecord(program="BD3T", component="Mac", version="1")
	ptrMac.addRecord(program="BD3B", component="Mac", version="1")
	ptrMac.addRecord(program="BS2B", component="Mac", version="1")
	ptrMac.addRecord(program="BWWT", component="Mac", version="1")
	ptrMac.addRecord(program="BWWB", component="Mac", version="1")
	ptrMac.addRecord(program="BTCB", component="Mac", version="1")
	ptrMac.addRecord(program="BBNB", component="Mac", version="1")

	records += ptrMac.open("http://public-test.patch.battle.net:1119/patch")

	for record in records:
		print("%s->%s" % (record.program, record.component))

		if record.component == "enUS":
			miss, hit = [], []
			patch = bpp.MFILPatch(*record.text.split(";"))
			try:
				patch.configure(program=record.program, server="akamai")
			except bpp.ServerError as e:
				print(e)
				continue
			bases, files = patch.getDirectDownload()
			base = bases[0]

			baseDir = os.path.join(MPQ_BASE_DIR, record.program, base.split("/")[-2])

			for file in files:
				local = os.path.join(baseDir, file.path)
				remote = base + file.path
				if os.path.exists(local):
					hit.append((remote, local, file))
				else:
					miss.append((remote, local, file))

			fmt = "curl -# --fail {remote} -o {local}"
			for remote, local, file in miss:
				print(fmt.format(remote=remote, local=local))

			for remote, local, file in hit:
				localsize = os.path.getsize(local)
				if localsize != file.size:
					print("WARNING: %i != %i for %s at %s" % (localsize, file.size, remote, local))

		if record.component == "blob":
			base, installHash, gameHash, _ = record.text.split(";")

			if not base.startswith("http"):
				print("Skipping %r: %r" % (base, record.text))
				continue

			gameBlob = bpp.Blob(base, gameHash, "game", record.program)
			cache_blob(gameBlob)

			if installHash:
				installBlob = bpp.Blob(base, installHash, "install", record.program)
				cache_blob(installBlob)

		if record.component == "cdn":
			pass

		if record.component == "cfg":
			# deprecated, empty
			print(record.text)

		if record.component == "Win":
			print(record.text)

		if record.component == "PUB":
			url, hash = record.text.split(";")
			clog = bpp.Catalog(url, hash, name="base")
			clog.fetch()
			cache_clog(clog)
			for catalog in clog.catalogs.values():
				cache_clog(catalog)


if __name__ == "__main__":
	main()
