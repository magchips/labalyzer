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

'''provide dialog to edit timeframes in programme'''

import gtk

from labalyzer_lib.helpers import get_builder

# import gettext
# from gettext import gettext as _
# gettext.textdomain('labalyzer')

from labalyzer import TimeframeCompiler
from labalyzer.constants import (TF_COLNAMES, COL_VARNAME, COL_DEVICE, COL_VALUE)
from labalyzer.LabalyzerSettings import settings
from labalyzer.helpers import (openTimeframe, saveTimeframe, getChoice, getText)

import logging

class TimeframeeditorDialog(gtk.Dialog):
	'''class to provide dialog for editing timeframes'''
	__gtype_name__ = "TimeframeeditorDialog"

	def __new__(cls):
		"""Special static method that's automatically called by Python when 
		constructing a new instance of this class.
		
		Returns a fully instantiated TimeframeeditorDialog object.
		"""
		builder = get_builder('TimeframeeditorDialog')
		new_object = builder.get_object('timeframeeditor_dialog')
		new_object.finish_initializing(builder)
		return new_object

	def finish_initializing(self, builder):
		"""Called when we're finished initializing.

		finish_initalizing should be called after parsing the ui definition
		and creating a TimeframeeditorDialog object with it in order to
		finish initializing the start of the new TimeframeeditorDialog
		instance.
		"""
		# Get a reference to the builder and set up the signals.
		self.builder = builder
		self.ui = builder.get_ui(self)
		
		self._timeframeFileName = None

		# prepare timeframe listview
		self._twTimeframe = builder.get_object("twTimeframe")
		self._lsTimeframe = builder.get_object("lsTimeframe")

		builder.get_object("twDigitalChannels").connect("row-activated", self.on_AddFromDeviceList, 0)
		builder.get_object("twAnalogChannels").connect("row-activated", self.on_AddFromDeviceList, 1)


		for i in xrange(7):
			cell = gtk.CellRendererText()
			cell.connect('edited', self.onTimeframeCellEdited, i)
			cell.set_property("editable", True)
			column = gtk.TreeViewColumn(TF_COLNAMES[i], cell, text=i)
			column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
			column.set_resizable(True)
			column.set_expand(False)
			self._twTimeframe.append_column(column)

		# prepare variable name listview
		self._twVariableNames = builder.get_object("twVariableNames")
		self._lsVariableNames = builder.get_object("lsVariableNames")
		cell = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Variable Name", cell, text=0)
		column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		column.set_expand(False)
		self._twVariableNames.append_column(column)

		self._twDigitalChannels = builder.get_object("twDigitalChannels")
		self._lsDigitalChannels = builder.get_object("lsDigitalChannels")
		cell = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Digital Channels", cell, text=0)
		column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		column.set_expand(False)
		self._twDigitalChannels.append_column(column)
		for channel in settings['DigitalChannels']:
			self._lsDigitalChannels.append([channel])

		self._twAnalogChannels = builder.get_object("twAnalogChannels")
		self._lsAnalogChannels = builder.get_object("lsAnalogChannels")
		cell = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Analog Channels", cell, text=0)
		column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		column.set_expand(False)
		self._twAnalogChannels.append_column(column)
		for channel in settings['AnalogChannels']:
			self._lsAnalogChannels.append([channel])

		self.reloadMaster = False
		self.lineBuffer = None


	def onTimeframeCellEdited(self, _cell, path, new_text, column):
		'''called if a cell was edited'''
		self._lsTimeframe[path][column] = new_text
		if column == COL_VARNAME: # if we might have changed a variable name
			self.__updateVariableView__()

	def LoadTimeframe(self, filename=None):
		'''load timeframe file from disk'''
		self._lsTimeframe.clear()
		fn = openTimeframe(filename, self._lsTimeframe)
		if fn == None:
			logging.error('problem opening filename %s', filename)
		else:
			self._timeframeFileName = fn
			if filename == None:
				self.reloadMaster = True
		self.__updateVariableView__()

	def __updateVariableView__(self):
		c = TimeframeCompiler.TimeframeCompiler()
		self._lsVariableNames.clear()
		try:
			vardict = c.parseVariables(self._lsTimeframe)
			for key in vardict:
				self._lsVariableNames.append([key])
		except TimeframeCompiler.RecursionError as e:
			self._lsVariableNames.append(["Could not update variable view!"])
			self._lsVariableNames.append(["The following entries could not be parsed:"])
			for key in e.unparsed:
				self._lsVariableNames.append([key + ": " + e.unparsed[key]])

	
	
	def on_btnOpen_clicked(self, _widget, _data=None):
		'''load timeframe'''
		self.reloadMaster = True 
		self.LoadTimeframe()

	def on_btnSave_clicked(self, _widget, _data=None):
		'''save timeframe'''
		fn = saveTimeframe(self._timeframeFileName, self._lsTimeframe)
		if fn is not None:
			self.reloadMaster = True
		
	def on_btnSaveAs_clicked(self, _widget, _data=None):
		'''save timeframe'''
		fn = saveTimeframe(None, self._lsTimeframe)
		if fn is not None:
			self.reloadMaster = True
			self._timeframeFileName = fn

	def on_btnReload_clicked(self, _widget, _data=None):
		'''reload current timeframe'''
		self.LoadTimeframe(self._timeframeFileName)

	def on_InsertLine_activate(self, _widget, _data=None):
		'''add new line to timeframe'''
		(_, itr) = self._twTimeframe.get_selection().get_selected()
		self._lsTimeframe.insert_after(itr)

	def on_CutLine_activate(self, _widget, _data=None):
		'''cut current line in timeframe'''
		(_, itr) = self._twTimeframe.get_selection().get_selected()
		self.lineBuffer = [row for row in self._lsTimeframe[itr]]
		self._lsTimeframe.remove(itr)

	def on_PasteLine_activate(self, _widget, _data=None):
		'''paste line from buffer'''
		(_, itr) = self._twTimeframe.get_selection().get_selected()
		self._lsTimeframe.insert_after(itr, self.lineBuffer)

	def on_CopyLine_activate(self, _widget, _data=None):
		'''copy current line in timeframe'''
		(_, itr) = self._twTimeframe.get_selection().get_selected()
		self.lineBuffer = [row for row in self._lsTimeframe[itr]]

	def on_AddFromDeviceList(self, _widget, path, _view_column, data=None):
		'''add new line entry from double clicking sth in device list'''
		# get selected row in timeframe store
		(_, itr) = self._twTimeframe.get_selection().get_selected()

		if itr is None or not self._lsTimeframe.iter_is_valid(itr):
			logging.warn("invalid Timeframe line selected")
			return
		if data == 0: # Digital Data
			key = self._lsDigitalChannels[path][0]
			val = getChoice('Please select new value', settings['DigitalChannels'][key].highname, settings['DigitalChannels'][key].lowname, 'Will be set automatically')
		elif data == 1: # Analog Data
			key = self._lsAnalogChannels[path][0]
			val = getText('Please enter new value', 'Value:', 'Will be set automatically')
		else: return # something wrong, should never happen
		self._lsTimeframe[itr][COL_DEVICE] = key
		self._lsTimeframe[itr][COL_VALUE] = val
		
	
	def run(self):
		'''run dialog'''
		gtk.Dialog.run(self)
		if self.reloadMaster:
			logging.debug('TF changed; need to reload!')
			return self._timeframeFileName


if __name__ == "__main__":
	dialog = TimeframeeditorDialog()
	dialog.show()
	gtk.main()
