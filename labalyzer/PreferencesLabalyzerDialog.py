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

# This is your preferences dialog.
#
# Define your preferences dictionary in the __init__.main() function.
# The widget names in the PreferencesTestProjectDialog.ui
# file need to correspond to the keys in the preferences dictionary.
#
# Each preference also need to be defined in the 'widget_methods' map below
# to show up in the dialog itself.  Provide three bits of information:
#  1) The first entry is the method on the widget that grabs a value from the
#	 widget.
#  2) The second entry is the method on the widget that sets the widgets value
#	  from a stored preference.
#  3) The third entry is a signal the widget will send when the contents have
#	 been changed by the user. The preferences dictionary is always up to
# date and will signal the rest of the application about these changes.
# The values will be saved to desktopcouch when the application closes.
#

'''preferences dialog, pretty much not used'''


widget_methods = {
	'example_entry': ['get_text', 'set_text', 'changed'],
}

#import gettext
#from gettext import gettext as _
#gettext.textdomain('labalyzer')

import logging
logger = logging.getLogger('labalyzer')

from labalyzer_lib.PreferencesDialog import PreferencesDialog

class PreferencesLabalyzerDialog(PreferencesDialog):
	'''preferences dialog'''
	__gtype_name__ = "PreferencesLabalyzerDialog"

	def finish_initializing(self, builder): # pylint: disable=E1002
		"""Set up the preferences dialog"""
		super(PreferencesLabalyzerDialog, self).finish_initializing(builder)

		# populate the dialog from the preferences dictionary
		# using the methods from widget_methods
		self.widget_methods = widget_methods
		self.set_widgets_from_preferences() # pylint: disable=E1101

		# Code for other initialization actions should be added here.
