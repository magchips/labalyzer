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

'''provide dialog to show datalog'''

import gtk

from labalyzer_lib.helpers import get_builder
from labalyzer.plotter import functionPlotter
from collections import namedtuple
from labalyzer.LabalyzerSettings import settings
from labalyzer_lib.plotter import fitter

#import gettext
#from gettext import gettext as _
#gettext.textdomain('labalyzer')


import logging
logger = logging.getLogger('labalyzer')

class DatalogDialog(gtk.Dialog):
	'''dialog to show datalog'''
	__gtype_name__ = "DatalogDialog"

	def __new__(cls):
		"""Special static method that's automatically called by Python when 
		constructing a new instance of this class.
		
		Returns a fully instantiated DatalogDialog object.
		"""
		builder = get_builder('DatalogDialog')
		new_object = builder.get_object('datalog_dialog')
		new_object.finish_initializing(builder)
		return new_object

	def finish_initializing(self, builder):
		"""Called when we're finished initializing.

		finish_initalizing should be called after parsing the ui definition
		and creating a DatalogDialog object with it in order to
		finish initializing the start of the new DatalogDialog
		instance.
		"""
		# Get a reference to the builder and set up the signals.
		self.builder = builder
		self.ui = builder.get_ui(self)
		
		self.connect("delete-event", self.on_delete)
		
		self.plot = functionPlotter(self.builder.get_object('bxHost'))
				
		self.data = {}
		self.maxScanID = -1
		self.activeScanID = None
		
		self.lsScanSelector = builder.get_object('lsScanSelector')
		cmbScanSelector = builder.get_object('cmbScanSelector')
		cell = gtk.CellRendererText()
		cmbScanSelector.pack_start(cell, True)
		cmbScanSelector.add_attribute(cell, 'text', 0)
		
		cmbGraphSelector = builder.get_object('cmbGraphSelector')
		cell = gtk.CellRendererText()
		cmbGraphSelector.pack_start(cell, True)
		cmbGraphSelector.add_attribute(cell, 'text', 0)
		cmbGraphSelector.set_active(0)
		
		cmbFitSelector = builder.get_object('cmbFitFunctionSelector')
		cell = gtk.CellRendererText()
		cmbFitSelector.pack_start(cell, True)
		cmbFitSelector.add_attribute(cell, 'text', 0)
		cmbFitSelector.set_active(0)
		
		self.dataStore = namedtuple('ScanInformation', ['columnNames', 'xdataDark', 'xdata', 'ydata'])
		
	def addDataPoint(self, scanID, xdata, fitResult):
		'''add new point to existing scan'''
		self.data[scanID].xdata.append(xdata)
		parmsX, parmsY, mean = fitResult
		ys = [parmsX[0], parmsY[0], mean[0], parmsX[1], parmsY[1], parmsX[2], parmsY[2], parmsX[3], parmsY[3], mean[1], mean[2], mean[3], mean[4], mean[5]]
		for i, y in enumerate(ys):
			try:
				self.data[scanID].ydata[i].append(y)
			except IndexError:
				self.data[scanID].ydata.append([y])
		if self.activeScanID == scanID:
			self.updatePlot()
		
	def addScan(self, scanID, name, columnNames, xdataDark=None):
		'''add new scan to list of scans'''
		logger.info('added Scan with ID=%d', (scanID))
		if scanID <= self.maxScanID:
			raise RuntimeError('Scan already existing!') 
		self.maxScanID = scanID
		self.lsScanSelector.append([name, scanID])
		self.data[scanID] = self.dataStore(columnNames, xdataDark, [], [])
			
	def setActiveScan(self, scanID):
		'''select active scan'''
		self.builder.get_object('cmbScanSelector').set_active(scanID)
	
	def getNewScanID(self):
		'''return valid ID for a new scan'''
		return self.maxScanID + 1
		
	def on_cmbScanSelector_changed(self, widget):
		'''update view if active scan changed'''
		scanID = self.lsScanSelector[widget.get_active()][1]
		self.activeScanID = scanID
		self.updatePlot()
		
	def on_cmbGraphSelector_changed(self, widget):
		'''update view if active graph (of scan) is changed'''
		self.graphID = widget.get_active()
		# 0=Amplitude, 1=Width, 2=Position, 3=AtomNumber
		self.updatePlot()
		
	def on_cmbFitFunctionSelector_changed(self, widget):
		self.fitFunction = eval(settings[widget.get_model()[widget.get_active()][1]])
		
	def on_btnFit_clicked(self, widget):
		ft = fitter()
				
	def updatePlot(self):
		'''update plot'''
		if self.activeScanID is None:
			return
		x = self.data[self.activeScanID].xdata
		if self.graphID == 0:
			ys = self.data[self.activeScanID].ydata[0:3]
		elif self.graphID < 5:
			ys = self.data[self.activeScanID].ydata[1 + 2*self.graphID:3 + 2*self.graphID]
		else:
			ys = self.data[self.activeScanID].ydata[self.graphID + 6]
		dark = self.data[self.activeScanID].xdataDark
		if len(ys)  > 0:
			self.plot.setData(x, ys, dark)
	
	def on_delete(self, dialog, event):
		settings['main.showDataLog'] = False
		return True

if __name__ == "__main__":
	dialog = DatalogDialog()
	dialog.show()
	gtk.main()
