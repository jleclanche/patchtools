#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Blizzard Downloader torrent extractor
By Jerome Leclanche <adys.wh@gmail.com>
"""

from bencode import decode_dict
from re import sub

def extract(fname, out=""):
	tname = sub(fname, ".exe$", ".torrent")
	file = open(fname, "rb")
	data = file.read()
	file.close()
	i = 0
	datafrom = ""
	while i < len(data) - 11:
		d = data[i:i+11]
		if d == "d8:announce":
			datafrom = data[i:]
			break
		i += 1
	
	decoded, length = decode_dict(datafrom, 0)
	datafrom = datafrom[:length]
	
	out = out or fname + ".torrent"
	out = open(out, "wb")
	out.write(datafrom)
	out.close()

def main():
	import sys
	fname = sys.argv[1]
	extract(fname)

if __name__ == "__main__":
	main()
