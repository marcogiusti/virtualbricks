#!/usr/bin/env python
# coding: utf-8

"""
Virtualbricks - a vde/qemu gui written in python and GTK/Glade.
Copyright (C) 2011 Virtualbricks team

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; version 2.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

CURRENT_VERSION="1.0"
SUPPORTED_LANGS = ['it','nl','fr','de','es']

from distutils.core import setup
import os
import sys
import tempfile
import re

for arg in sys.argv:
	if arg.startswith('--build-base='):
		sys.prefix=arg.split('=')[1]

glade = open('share/virtualbricks.template.glade','r').read()
micro = open('.bzr/branch/last-revision','r').read().split(' ')[0]
if micro == '':
	micro = '000'

virtualbricks_version=CURRENT_VERSION+'.'+micro

open('share/virtualbricks.glade','w+').write(re.sub('___VERSION___', virtualbricks_version, glade))




FILES = [
			( 'bin', ['main/virtualbricks']),
			( 'share/virtualbricks/', ['share/virtualbricks.glade']),
			( 'share/applications', ['share/virtualbricks.desktop']),
			( 'share/pixmaps', ['share/virtualbricks.png']),
			( 'share/pixmaps', ['images/Connect.png']),
			( 'share/pixmaps', ['images/Disconnect.png']),
			( 'share/pixmaps', ['images/Event.png']),
			( 'share/pixmaps', ['images/Qemu.png']),
			( 'share/pixmaps', ['images/Switch.png']),
			( 'share/pixmaps', ['images/Tap.png']),
			( 'share/pixmaps', ['images/Capture.png']),
			( 'share/pixmaps', ['images/TunnelConnect.png']),
			( 'share/pixmaps', ['images/TunnelListen.png']),
			( 'share/pixmaps', ['images/Wirefilter.png']),
			( 'share/pixmaps', ['images/Wire.png']),
			( 'share/pixmaps', ['images/SwitchWrapper.png'])
]

tempdirs = []

for l in SUPPORTED_LANGS:
	directory_name = tempfile.mkdtemp()
	tempdirs.append(directory_name)
	command = 'msgfmt -o ' + directory_name + '/virtualbricks.mo ' + 'locale/virtualbricks/' + l + '.po'
	os.system(command)
	FILES.append(('share/locale/'+l+'/LC_MESSAGES/', [directory_name + '/virtualbricks.mo']))

setup( data_files=FILES, name='virtualbricks', version=virtualbricks_version,
	description='Virtualbricks Virtualization Tools',
	license='GPL2',
	author='Daniele Lacamera, Rainer Haage, Francesco Apollonio, Pierre-Louis Bonicoli, Simone Abbati',
	author_email='qemulator-list@createweb.de',
	url='http://www.virtualbricks.eu/',
	packages=['virtualbricks', 'virtualbricks.gui'],
	package_dir = {'': '.'}
	)

#Remove compiled l10n files
for d in tempdirs:
	try:
		#Remove the compiled file
		os.unlink(d + '/virtualbricks.mo')
		# Clean up the directory
		os.removedirs(d)
	except:
		print "Not critical error while removing: %s(.virtualbricks.mo)" %d
		continue
