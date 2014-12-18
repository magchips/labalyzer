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


'''about dialog'''

#import gettext
#from gettext import gettext as _
#gettext.textdomain('labalyzer')

import logging
logger = logging.getLogger('labalyzer')

from labalyzer_lib.AboutDialog import AboutDialog

# See labalyzer_lib.AboutDialog.py for more details about how this class works.
class AboutLabalyzerDialog(AboutDialog):
	'''about dialog'''
	__gtype_name__ = "AboutLabalyzerDialog"
	
	def finish_initializing(self, builder): # pylint: disable=E1002
		"""Set up the about dialog"""
		super(AboutLabalyzerDialog, self).finish_initializing(builder)

		# Code for other initialization actions should be added here.

