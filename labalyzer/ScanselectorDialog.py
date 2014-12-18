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

'''edit scan settings'''

import gtk

from labalyzer_lib.helpers import get_builder

#import gettext
#from gettext import gettext as _
#gettext.textdomain('labalyzer')

class ScanselectorDialog(gtk.Dialog):
	'''edit scan settings'''
	__gtype_name__ = "ScanselectorDialog"

	def __new__(cls):
		"""Special static method that's automatically called by Python when 
		constructing a new instance of this class.
		
		Returns a fully instantiated ScanselectorDialog object.
		"""
		builder = get_builder('ScanselectorDialog')
		new_object = builder.get_object('scanselector_dialog')
		new_object.finish_initializing(builder)
		return new_object

	def finish_initializing(self, builder):
		"""Called when we're finished initializing.

		finish_initalizing should be called after parsing the ui definition
		and creating a ScanselectorDialog object with it in order to
		finish initializing the start of the new ScanselectorDialog
		instance.
		"""
		# Get a reference to the builder and set up the signals.
		self.builder = builder
		self.ui = builder.get_ui(self)
		
		
		builder.get_object('btnFlip12').connect('clicked', self.on_Flip, 1)
		builder.get_object('btnFlip23').connect('clicked', self.on_Flip, 2)

		self.lblRowname = [None, None, None]
		self.lblColname = [None, None, None]
		self.adjStart = [None, None, None]
		self.spinStart = [None, None, None]
		self.adjEnd = [None, None, None]
		self.spinEnd = [None, None, None]
		self.adjSteps = [None, None, None]
		self.spinSteps = [None, None, None]
		self.adjStepsize = [None, None, None]
		self.chkEnable = [None, None, None]
		for i in range(3):
			self.lblRowname[i] = builder.get_object('lblRowname' + str(i+1))
			self.lblColname[i] = builder.get_object('lblColname' + str(i+1))
			self.chkEnable[i] = builder.get_object('chk_lvl' + str(i + 1))

			self.adjStart[i] = gtk.Adjustment(0, -50e6, 50e6, 1, 1)
			self.adjStart[i].connect('value-changed', self.parameterChanged, i, 'start')
			self.spinStart[i] = builder.get_object('spinStart' + str(i+1))
			self.spinStart[i].set_adjustment(self.adjStart[i])
			self.adjEnd[i] = gtk.Adjustment(0, -50e6, 50e6, 1, 1)
			self.adjEnd[i].connect('value-changed', self.parameterChanged, i, 'end')
			self.spinEnd[i] = builder.get_object('spinEnd' + str(i+1))
			self.spinEnd[i].set_adjustment(self.adjEnd[i])
			self.adjSteps[i] = gtk.Adjustment(0, 2, 1e6, 1, 10)
			self.adjSteps[i].connect('value-changed', self.parameterChanged, i, 'steps')
			self.spinSteps[i] = builder.get_object('spinSteps' + str(i+1))
			self.spinSteps[i].set_adjustment(self.adjSteps[i])
			self.adjStepsize[i] = gtk.Adjustment(0, -1e6, 1e6, 0.02, 1)
			builder.get_object('spinStepsize' + str(i+1)).set_adjustment(self.adjStepsize[i])

			self.chkEnable[i].connect('clicked', self.enableChanged, i)

		self.toggleLock = False



	def setScanParameters(self, parms):
		'''set scan parameters'''
		self.scanParameters = parms
		self.builder.get_object('txtScanName').set_text(parms.name)
		for i in range(3):
			prms = parms.data[i]
			self.lblRowname[i].set_text(prms['rowname'])
			self.lblColname[i].set_text(prms['colname'])
			self.adjStart[i].set_value(prms['start'])
			self.adjEnd[i].set_value(prms['end'])
			self.adjSteps[i].set_value(prms['steps'])
			try:
				self.adjStepsize[i].set_value((prms['end'] - prms['start'])/(prms['steps'] - 1))
			except ZeroDivisionError: 
				pass
		if parms.depth > 0:
			self.chkEnable[parms.depth - 1].set_active(True)

	def enableChanged(self, widget, lvl):
		'''enable additional level of scan'''
		# lvl defines which depth changed
		if self.toggleLock:
			return
		self.toggleLock = True
		if widget.get_active():
			self.scanParameters.depth = lvl + 1
		else:
			self.scanParameters.depth = lvl
		for i in range(3): # enable/disable fields
			if self.scanParameters.depth > i:
				self.spinStart[i].set_sensitive(True)
				self.spinEnd[i].set_sensitive(True)
				self.spinSteps[i].set_sensitive(True)
				self.chkEnable[i].set_active(True)
			else:
				self.spinStart[i].set_sensitive(False)
				self.spinEnd[i].set_sensitive(False)
				self.spinSteps[i].set_sensitive(False)
				self.chkEnable[i].set_active(False)

		self.toggleLock = False


	def on_Flip(self, _widget, lvl):
		'''flip two scan levels'''
		# data defines which two levels changed:
		# data = 1 for flipping 1 and 2
		# data = 2 for flipping 2 and 3
		self.scanParameters.data[lvl - 1], self.scanParameters.data[lvl] = self.scanParameters.data[lvl], self.scanParameters.data[lvl - 1]
		self.setScanParameters(self.scanParameters)

	def parameterChanged(self, widget, lvl, field):
		'''parameter changed'''
		# lvl defines which level changed
		start = self.adjStart[lvl].get_value()
		end = self.adjEnd[lvl].get_value()
		steps = self.adjSteps[lvl].get_value()
		self.scanParameters.data[lvl][field] = widget.get_value()
		try:
			self.adjStepsize[lvl].set_value((end - start)/(steps - 1))
		except ZeroDivisionError: 
			pass

	def on_btn_ok_clicked(self, _widget, _data=None):
		"""The user has elected to save the changes.

		Called before the dialog returns gtk.RESONSE_OK from run().
		"""
		# update self.scanParameters with current values
		# since self.scanParameters has been passed by reference, this should also 
		# update the values in the main programme
		self.scanParameters.name = self.builder.get_object('txtScanName').get_text()

	def on_btn_cancel_clicked(self, widget, data=None):
		"""The user has elected cancel changes.

		Called before the dialog returns gtk.RESPONSE_CANCEL for run()
		"""
		pass


if __name__ == "__main__":
	dialog = ScanselectorDialog()
	dialog.show()
	gtk.main()
