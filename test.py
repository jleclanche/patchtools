#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from sys import maxint
from random import randint
from etr import extract
from bencode import bdecode

DIR = "./tests/"

def runtests():
	try:
		files = os.listdir(DIR)
	except OSError:
		print "You need a readable 'tests' directory to run extractions on."
		os.exit(1)
	
	for f in files:
		out = "tmp_test_%i.torrent" % (randint(-maxint, maxint))
		extract(DIR+f, out=out)
		_f = open(out)
		bdecode(_f.read())
		print "%s extracted OK" % (f)
		os.remove(out)
	print "No error in %i files" % len(files)

if __name__ == "__main__":
	runtests()