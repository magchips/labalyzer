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


'''main window'''

#import gettext
#from gettext import gettext as _
#gettext.textdomain('labalyzer')

import gtk
import logging
logger = logging.getLogger('labalyzer')

import datetime

from labalyzer_lib import Window
# from labalyzer.AboutLabalyzerDialog import AboutLabalyzerDialog
# from labalyzer.PreferencesLabalyzerDialog import PreferencesLabalyzerDialog
from labalyzer.TimeframeeditorDialog import TimeframeeditorDialog
from labalyzer.ScanselectorDialog import ScanselectorDialog
from labalyzer.LabalyzerSettings import settings
from labalyzer import DatalogDialog
from labalyzer.TimeframeController import (TimeframeController, TimeframeCompiler)
from labalyzer.constants import (TF_COLNAMES, COL_COLORHINT, MODE_CONTINUOUS, MODE_DIRECT, MODE_RUN, MODE_SCAN, MODE_STOPPED, ROWTYPE_PARAMETER, COL_VARNAME, COL_DEVICE, TF_COLNAMES)
from labalyzer.plotter import mainPlotter

import copy # for scanselect

import gc # only for debugging!

# this is important for settings accessible directly from the main window. all these settings need to be listed here by
# widget name, setting name, getter and setter functions, and activation signals
widget_data = {
	'chkSaveAllImages': ['main.saveAll', 'get_active', 'set_active', 'toggled'],
	'chkRunFit': ['main.runFit', 'get_active', 'set_active', 'toggled'],
	'chkFitOffset': ['fit.allowOffset', 'get_active', 'set_active', 'toggled'],
	'chkKeepAspect': ['plot.keepAspect', 'get_active', 'set_active', 'toggled'],
	'chkShowCursor': ['plot.showCursor', 'get_active', 'set_active', 'toggled'],
	'adjMaxOD': ['plot.maxOD', 'get_value', 'set_value', 'value_changed'],
	'adjMagnification': ['physics.magnification', 'get_value', 'set_value', 'value_changed'],
	'adjTrapfreq': ['physics.trapfreq', 'get_value', 'set_value', 'value_changed'],
	'adjTOF': ['physics.timeofflight', 'get_value', 'set_value', 'value_changed'],
	'adjNoDummies': ['scan.dummies', 'get_value', 'set_value', 'value_changed'],
	'cmbFitMethod': ['main.fitMethod', 'get_active', 'set_active', 'changed'],
	'chkUseScope': ['scope.use', 'get_active', 'set_active', 'toggled'],
	'chkShowDataLog': ['main.showDataLog', 'get_active', 'set_active', 'toggled']
}

# See labalyzer_lib.Window.py for more details about how this class works
class LabalyzerWindow(Window):
	'''main window'''
	__gtype_name__ = "LabalyzerWindow"
	
	def finish_initializing(self, builder): # pylint: disable=E1002
		"""Set up the main window"""
		super(LabalyzerWindow, self).finish_initializing(builder)

		# self.AboutDialog = AboutLabalyzerDialog
		# self.PreferencesDialog = PreferencesLabalyzerDialog
		
		settings.connect("changed", self.settingsChanged)
		
		# create datalog dialog
		self.dlgDataLog = DatalogDialog.DatalogDialog()
		# create timeframe controller
		self.timeframeController = TimeframeController(builder.get_object('lsTimeframe'), self)
		# get progress bar for timeframe progress
		self.pbTimeframeProgress = builder.get_object('pbTimeframeProgress')
		# create drawing area for image
		self.plotter = mainPlotter(builder.get_object('boxImage'))
		
		# prepare timeframe treeview
		twTimeframe = builder.get_object('twTimeframe')
		for i in xrange(9):
			cell = gtk.CellRendererText()
			cell.set_property('background-set', True)
			column = gtk.TreeViewColumn(TF_COLNAMES[i])
			column.pack_start(cell, True)
			column.set_attributes(cell, text=i, background=COL_COLORHINT)
			column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
			column.set_resizable(True)
			column.set_expand(False)
			column.sort_column_id = i
			twTimeframe.append_column(column)

		# initialize direct control things
		self.populateDirectControl()
		# things to set DDS frequency from direct control
		cmbDDSSelector = builder.get_object('cmbDDSSelect')
		cell = gtk.CellRendererText()
		cmbDDSSelector.pack_start(cell, True)
		cmbDDSSelector.add_attribute(cell, 'text', 0)
		cmbDDSSelector.set_active(0)
		
		
		self.builder.get_object('btnGo').connect('clicked', self.on_stateChange, MODE_RUN)
		self.builder.get_object('btnGoSteady').connect('clicked', self.on_stateChange, MODE_CONTINUOUS)
		self.builder.get_object('btnScan').connect('clicked', self.on_stateChange, MODE_SCAN)
		self.builder.get_object('btnStop').connect('clicked', self.on_stateChange, MODE_STOPPED)
		
		chkboxes = ['chkScopeChannelOneActive', 'chkScopeChannelTwoActive', 'chkScopeChannelThreeActive', 'chkScopeChannelFourActive']
		for i in range(1, 5):
			self.builder.get_object(chkboxes[i-1]).set_active(i in settings['scope.channels'])
			self.builder.get_object(chkboxes[i-1]).connect('toggled', self.on_chkScopeChannelSelect_toggled, i)

		# create combo box for selecting which fitting method is used
		cmbFitMethod = builder.get_object('cmbFitMethod')
		cell = gtk.CellRendererText()
		cmbFitMethod.pack_start(cell, True)
		cmbFitMethod.add_attribute(cell, 'text', 0)
		
		# create combo box for selecting which image is shown
		cmbImageSelector = builder.get_object('cmbImageSelector')
		cell = gtk.CellRendererText()
		cmbImageSelector.pack_start(cell, True)
		cmbImageSelector.add_attribute(cell, 'text', 0)

		# restore button states from settings, and connect widgets to settings changer
		for key in widget_data:
			widget = self.builder.get_object(key)
			
			signal = widget_data[key][3]
			value = settings[widget_data[key][0]]
			write_method_name = widget_data[key][2]
			method = getattr(widget, write_method_name)
			widget.connect(signal, self.setPreference, key)
			method(value)
		# we need to treat dataLog seperately, as it is not just a setting, it actually needs to show/hide the dialog on changes
		if settings['main.showDataLog']:
			self.dlgDataLog.show()
		
		## DEBUG
		gc.enable()
		#gc.set_debug(gc.DEBUG_LEAK)
	
	def settingsChanged(self, published, sets):
		if 'main.showDataLog' in sets:
			if settings['main.showDataLog']:
				self.dlgDataLog.show()
			else:
				self.dlgDataLog.hide()
			self.builder.get_object('chkShowDataLog').set_active(settings['main.showDataLog'])
		
	def on_stateChange(self, _widget, mode):
		'''state change button was pressed'''
		if not self.timeframeController.attemptStateChange(mode):
			logger.warn('onStateChange: setting new state to %d FAILED', mode)

	def on_btnDebug_clicked(self, _widget, _data=None):
		'''debug button'''
		self.timeframeController.compiler.compileTimeframe(self.builder.get_object('lsTimeframe'))

	def on_btnEditTimeframe_clicked(self, _widget, _data=None):
		'''edit timeframe'''
		EditDialog = TimeframeeditorDialog()
		EditDialog.LoadTimeframe(self.timeframeController.filename)
		response = EditDialog.run()
		EditDialog.destroy()

		if response is not None:
			self.loadTimeframe(response)

	def on_btnLoadTimeframe_clicked(self, _widget, data=None):
		'''load timeframe'''
		self.loadTimeframe(data)


	def on_btnSaveCurrentImage_clicked(self, _widget, data=None):
 		image = self.plotter.getImageAsPIL()
 		if image is None:
			return
		filename = './thispicture_'+datetime.datetime.utcnow().strftime("%Y-%m-%d-%H%M%S")+'.jpg'  # ask for filename and location, added above this time thing
		image.convert('RGB').save(filename)

	def on_chkScopeChannelSelect_toggled(self, widget, data=None): # beginnetje gemaakt door atreju , gebruiken on_chkScopeChannelSelect_toggled
		if data in settings['scope.channels']:
			indx = settings['scope.channels'].index(data)
			del settings['scope.channels'][indx]
		else:
			settings['scope.channels'].append(data)
			settings['scope.channels'] = sorted(settings['scope.channels'])


	def loadTimeframe(self, filename):
		'''load timeframe'''
		fn = self.timeframeController.setFilename(filename)
		if fn is not None:
			self.pbTimeframeProgress.set_text(fn)

	def on_btnTimeframeVsDirectControl_clicked(self, widget, _data=None):
		'''change between timeframe and direct control modes'''
		tab = self.builder.get_object('tbTimeframeVsDirectControl')
		if tab.get_current_page() == 0:
			if not self.timeframeController.attemptStateChange(MODE_DIRECT):
				return
			tab.set_current_page(1)
			widget.set_label("Timeframe")
		else:
			if not self.timeframeController.attemptStateChange(MODE_STOPPED):
				return
			tab.set_current_page(0)
			widget.set_label("Direct Control")

	def populateDirectControl(self):
		'''populate direct control from settings'''
		hbox = self.builder.get_object('hbxDirectControlContainer')

		## digital channels
		####################################
		dioChannels = dict()
		for k in settings['DigitalChannels']:
			dioChannels[(settings['DigitalChannels'][k].portNumber, settings['DigitalChannels'][k].channelNumber)] = k
		sKeys = sorted(dioChannels.iterkeys())

		for j in range(8):
			tbl = gtk.Table(8, 2, False)
			for i in range(8):
				lbl = gtk.Label(dioChannels[sKeys[8*j+i]] + ': ')
				lbl.set_alignment(0.9, 0.5)
				btn = gtk.ToggleButton(settings['DigitalChannels'][dioChannels[sKeys[8*j+i]]].lowname)
				btn.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#FF0000'))
				btn.modify_bg(gtk.STATE_ACTIVE, gtk.gdk.color_parse('#00FF00'))
				btn.set_size_request(60, -1)
				btn.connect("toggled", self.DCDigitalChange, settings['DigitalChannels'][dioChannels[sKeys[8*j+i]]])
				tbl.attach(lbl, 0, 1, i, i+1)
				tbl.attach(btn, 1, 2, i, i+1, gtk.SHRINK)
			tbl.show_all()
			hbox.pack_start(tbl, False, False, padding=5)


		## analog channels
		#########################################
		aoChannels = [dict(), dict(), dict()]
		for k in settings['AnalogChannels']:
			aoChannels[settings['AnalogChannels'][k].boardNumber][settings['AnalogChannels'][k].channelNumber] = k

		sKeys = [sorted(aoChannels[0]), sorted(aoChannels[1]), sorted(aoChannels[2])]
		for j in range(3):
			tbl = gtk.Table(8, 3, False)
			for i in range(8):
				curr = settings['AnalogChannels'][aoChannels[j][sKeys[j][i]]]
				adj = gtk.Adjustment(0, curr.minvalue, curr.maxvalue, 0.01, 0.2)
				adj.connect("value_changed", self.DCAnalogChange, curr)
				lbl = gtk.Label(aoChannels[j][sKeys[j][i]])
				lbl.set_alignment(0.9, 0.5)
				sld = gtk.HScale(adj)
				sld.set_draw_value(False)
				sld.set_size_request(60, -1)
				sb = gtk.SpinButton(adj, digits = 2)
				
				tbl.attach(lbl, 0, 1, i, i+1)
				tbl.attach(sld, 1, 2, i, i+1)
				tbl.attach(sb, 2, 3, i, i+1)
			tbl.show_all()
			hbox.pack_start(tbl, False, padding=5)
		hbox.show_all()

	def DCDigitalChange(self, widget, channel):
		'''digital output in direct mode'''
		lbl = widget.get_children()[0]
		if widget.get_active():
			lbl.set_text(channel.highname)
			self.timeframeController.directControlChangeDigital(channel, True)
		else:
			lbl.set_text(channel.lowname)
			self.timeframeController.directControlChangeDigital(channel, False)

	def DCAnalogChange(self, widget, channel):
		'''analog output in direct mode'''
		self.timeframeController.directControlChangeAnalog(channel, widget.get_value())
		
	def on_btnDDSUpdate_clicked(self, _widget, _data=None):
		'''DDS output in direct mode'''
		freq = self.builder.get_object('adjDDSFrequencyDirect').get_value()
		output = self.builder.get_object('chkDDSEnableOutput').get_active()
		self.timeframeController.directControlChangeDDS(freq, output)

	def on_btnAgilentUpdate_clicked(self, _widget, _data=None):
		'''Agilent output in direct mode'''
		freq = self.builder.get_object('adjAgilentFrequency').get_value()
		amp = self.builder.get_object('adjAgilentAmp').get_value()
		output = self.builder.get_object('chkAgilentEnableOutput').get_active()
		self.timeframeController.directControlAgilent(freq,amp,output)

	def on_btnAgilent2Update_clicked(self, _widget, _data=None):
		'''Agilent output in direct mode'''
		freq = self.builder.get_object('adjAgilentFrequency2').get_value()
		amp = self.builder.get_object('adjAgilentAmp2').get_value()
		output = self.builder.get_object('chkAgilentEnableOutput2').get_active()
		self.timeframeController.directControlAgilent2(freq,amp,output)

	def on_btnAgilentPulseUpdate_clicked(self, _widget, _data = None):
		pulse_length = str(self.builder.get_object('adjAgilentPulseLength').get_value()) + "E-9"
		ET = self.builder.get_object('AgilentPulseExtTrig').get_active()
		if ET == True:
			mode = "Ext"
		else:
			mode = "SS"
		self.timeframeController.directControlAgilentPulse(pulse_length, mode)

	def on_btnAgilent2PulseUpdate_clicked(self, _widget, _data = None):
		pulse_length = str(self.builder.get_object('adjAgilent2PulseLength').get_value())
		ET = self.builder.get_object('Agilent2PulseExtTrig').get_active()
		if ET == True:
			mode = "Ext"
		else:
			mode = "SS"
		self.timeframeController.directControlAgilent2Pulse(pulse_length, mode)



	def on_btnAgilentSineMode_clicked(self, _widget, _data=None):
		tab = self.builder.get_object('AgilentModes')
		tab.set_current_page(1)
		self.timeframeController.iniSine()


	def on_btnAgilentPulseMode_clicked(self, _widget, _data=None):
		tab = self.builder.get_object('AgilentModes')
		tab.set_current_page(0)
		self.timeframeController.iniBurst()


	def on_btnAgilent2SineMode_clicked(self, _widget, _data=None):
		tab = self.builder.get_object('Agilent2Modes')
		tab.set_current_page(1)
		self.timeframeController.iniSine2()


	def on_btnAgilent2PulseMode_clicked(self, _widget, _data=None):
		tab = self.builder.get_object('Agilent2Modes')
		tab.set_current_page(0)
		self.timeframeController.iniBurst2()


	def on_btnSRSPulseUpdate_clicked(self, _widget, _data=None):
		"""SRS pulse output in direct mode"""
		ET = self.builder.get_object('ExternalTriggerSRSPulse').get_active()
		channel_conf = {}
		if ET == True:
			mode = "Ext"
		else:
			mode = "SS"

		channel_conf["RD"] = self.builder.get_object('adjSRSRelativeDelay').get_value()
		channel_conf["AB"] = self.builder.get_object('adjSRSABPulseLength').get_value()
		channel_conf["CD"] = self.builder.get_object('adjSRSCDPulseLength').get_value()
		self.timeframeController.directControlSRSPulse(channel_conf, mode)

	def on_btnSendPulse_clicked(self, _widget, _data=None):
		"""docstring for on_btnSendPulse_clicked"""
		self.timeframeController.sendSRSPulse()

	def on_btnRohSchStartOutput_clicked(self, _widget, data=None):
		file_name = self.builder.filechooserbutton1.get_filename()
		if file_name is None:
			pass
		else:
			self.timeframeController.startRohSchOutput(file_name)

	def on_btnVoltageUpdate_clicked(self, _widget, _data=None):
		voltage = self.builder.get_object('adjVoltage').get_value()
		self.timeframeController.startVoltageOutput(voltage)


	def on_cmbImageSelector(self, widget, _data=None):
		'''shown image changed'''
		self.plotter.showImage(widget.get_active())
		
	def on_btnReFit(self, _widget, _data=None):
		'''force refit'''
		fitResult = self.plotter.getImageInfo()
		self.setFitResults(*fitResult)
		self.plotter.redraw()
		
	def setPreference(self, widget, key=None):
		'''handle widget changes that affect preferences'''
		read_method_name = widget_data[key][1]
		setting_key = widget_data[key][0]
		try:
			read_method = getattr(widget, read_method_name)
		except AttributeError:
			logger.warn("""'%s' does not have a '%s' method.
Please edit 'widget_methods' in %s"""
			% (key, read_method_name, self.__gtype_name__))
			return
		value = read_method()
		logger.debug('set_preference: %s = %s' % (key, str(value)))
		settings[setting_key] = value


	def setFitResults(self, resultsX, resultsY, other):
		'''display fit results'''
		lst = {'lblAmpX' : ['Amplitude: ', 0], 'lblPosX' : ['Position: ', 1], 'lblWidthX' : ['Width: ', 2], 'lblOffsetX' : ['Offset: ', 3]}
		for l in lst:
			lbl = self.builder.get_object(l)
			lbl.set_text(lst[l][0] + str(round(resultsX[lst[l][1]], 2)))
		lst = {'lblAmpY' : ['Amplitude: ', 0], 'lblPosY' : ['Position: ', 1], 'lblWidthY' : ['Width: ', 2], 'lblOffsetY' : ['Offset: ', 3]}
		for l in lst:
			lbl = self.builder.get_object(l)
			lbl.set_text(lst[l][0] + str(round(resultsY[lst[l][1]], 2)))
		lbl = self.builder.get_object('lblROIMean')
		lbl.set_text('ROI Mean: ' + str(round(other[0], 2)))
		lbl = self.builder.get_object('lblNSum')
		lbl.set_text('NSum: %.2E' %other[1])
		lbl = self.builder.get_object('lblNFit')
		lbl.set_text('NInt: %.2E' %other[2])
		lbl = self.builder.get_object('lblTemp')
		lbl.set_text('Temp(muK): %.2F' %other[3])
		lbl = self.builder.get_object('lbln0')
		lbl.set_text('n0: %.2E' %other[4])
		lbl = self.builder.get_object('lblPhi')
		lbl.set_text('Phi: %.2E' %other[5])

		
	def updateScanInfo(self, scanInfo):
		'''display scan info'''
		if scanInfo is None:
			# scan has ended!
			logger.debug('updateScanInfo has received end of SCAN')
			self.builder.get_object("lblScanName").set_text("No Scan Active")
			self.builder.get_object("tblScanInfo").hide()
		else:
			self.builder.get_object("tblScanInfo").show()
			self.builder.get_object("lblScanName").show()
			self.builder.get_object("lblScanName").set_text(self.timeframeController.scanParameters.name)
			
			i = 0
			for i, r in enumerate(scanInfo):
				for j in range(3):
					self.builder.get_object("lblScanInfo" + str(i) + str(j)).show()
					self.builder.get_object("lblScanInfo" + str(i) + str(j)).set_text(r[j])
			for i in range(i+1, 3):
				for j in range(3):
					self.builder.get_object("lblScanInfo" + str(i) + str(j)).hide()
					
	def updateModeInfo(self, mode, modeNext):
		'''display mode info in status bar'''
		logger.debug('update mode info to mode = ' + str(mode) + ' next mode = ' + str(modeNext))
		status = ''
		if mode == MODE_CONTINUOUS:
			status += 'running CONTINOUS'
		elif mode == MODE_SCAN:
			status += 'running SCAN'
		elif status == MODE_RUN:
			status += 'running RUN'
		#elif status == MODE_STOPPED:
		#	status += 'STOPPED'
		
		if modeNext == MODE_CONTINUOUS and mode != MODE_CONTINUOUS:
			status += ', about to run CONTINUOUS'
		elif modeNext == MODE_SCAN and mode != MODE_SCAN:
			status += ', about to start SCAN'
		elif modeNext == MODE_STOPPED and mode != MODE_STOPPED:
			status += ', about to STOP'
			
		self.builder.get_object('lblStatus').set_text(status)


	def on_scanSelectCell(self, _widget, path, column):
		'''when double clicking on timeframe cell, for scan settings'''
		column_id = column.sort_column_id
		rowtype = TimeframeCompiler.getRowType(self.timeframeController.timeframe[path])
		if rowtype == ROWTYPE_PARAMETER:
			rowname = self.timeframeController.timeframe[path][COL_VARNAME]
		else:
			rowname = self.timeframeController.timeframe[path][COL_DEVICE] + ' (' + 'row ' + str(path[0]) + ')'
		prms = {}
		prms['colname'] = TF_COLNAMES[column_id]
		prms['rowname'] = rowname
		try:
			prms['start'] = float(self.timeframeController.timeframe[path][column_id])
		except ValueError:
			prms['start'] = 0
		try:
			prms['end'] = float(self.timeframeController.timeframe[path][column_id])
		except ValueError:
			prms['end'] = 0
		prms['original'] = self.timeframeController.timeframe[path][column_id]
		prms['steps'] = 2
		prms['row'] = path[0]
		prms['column'] = column_id
		
		if self.timeframeController.scanParameters.depth < 1:
			self.timeframeController.scanParameters.depth = 1
		
		pass_parameters = copy.deepcopy(self.timeframeController.scanParameters)
		pass_parameters.data[0] = prms
		scanDialog = ScanselectorDialog()
		scanDialog.setScanParameters(pass_parameters)
		response = scanDialog.run()
		scanDialog.destroy()
		if response == gtk.RESPONSE_OK:
			# if ok was pressed, we copy pass_parameters (which have been changed by the dialog) over to our scan parameters.
			# if cancel was pressed we do nothing
			self.timeframeController.scanParameters = pass_parameters
			
			
	def on_chkShowDataLog_toggled(self, widget, _data=None):
		'''show datalog settings changed'''
		settings['main.showDataLog'] = False # force toggle, to force settings change, to redraw window
		settings['main.showDataLog'] = widget.get_active()
			
	def quit(self, _widget, _data=None):
		"""Signal handler for closing the LabalyzerWindow."""
		## DEBUG
		gc.collect()
		####
		self.destroy()

	def on_destroy(self, widget, data=None):
		"""Called when the LabalyzerWindow is closed."""
		# Clean up code for saving application state should be added here.
		self.timeframeController.shutdown()
		gtk.main_quit()
