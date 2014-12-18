# -*- Mode: Python; coding: utf-8; indent-tabs-mode: tab; tab-width: 2 -*-
### BEGIN LICENSE
# Copyright (C) 2010 <Atreju Tauschinsky> <Atreju.Tauschinsky@gmx.de>
# This program is free software: you can redistribute it and/or modify it 
# under the terms of the GNU General Public License version 3, as published 
# by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranties of 
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR 
# PURPOSE.  See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE


'''docstring'''

import optparse

# import gettext #don't care about internationalization
# from gettext import gettext as _
# gettext.textdomain('labalyzer')

import gtk

from labalyzer_lib import set_up_logging, get_version

def parse_options():
	"""Support for command line options"""
	parser = optparse.OptionParser(version="%%prog %s" % get_version())
	parser.add_option(
		"-v", "--verbose", action="count", dest="verbose",
		help=("Show debug messages (-vv debugs labalyzer_lib also)"))
	(options, _) = parser.parse_args()

	set_up_logging(options)

def main():
	'''constructor for your class instances'''
	parse_options()
	
	from labalyzer import LabalyzerWindow #pylint: disable=W0404
	from labalyzer.LabalyzerSettings import settings #pylint: disable=W0404

	# preferences
	settings.loadSettings()

	# Run the application.
	window = LabalyzerWindow.LabalyzerWindow()
	window.show()
	gtk.main()
	
	settings.saveSettings()
