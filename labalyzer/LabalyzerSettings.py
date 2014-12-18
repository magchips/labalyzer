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


'''settings'''

from labalyzer.constants import (ANDOR_KINETIC, FIT_MOMS2D)
import numpy

import gtk # for signalling
import gobject

import os, pickle

import logging
logger = logging.getLogger('labalyzer')

SETTINGS_VERSION = 0.3

class AnalogChannelDescriptor:
	'''describes analog channels'''
	def __init__(self, boardNumber, channelNumber, minvalue=-10, maxvalue=10, scalefactor=1):
		self.boardNumber = boardNumber
		self.channelNumber = channelNumber
		self.maxvalue = maxvalue
		self.minvalue = minvalue
		self.scalefactor = scalefactor
	def __str__(self):
		return 'AO' + str(self.channelNumber)
	def GetDeviceString(self):
		'''get string for device to pass to DAQmx'''
		return 'Dev' + str(self.boardNumber+1) + '/ao' + str(self.channelNumber) # NIDAQ starts counting at 1, we start counting at 0, hence the + 1

class DigitalChannelDescriptor:
	'''describes digital channels'''
	def __init__(self, port, channel, highname='high', lowname='low'):
		self.channelNumber = channel
		self.bitmask = numpy.uint16(2**channel)
		self.invertedBitmask = numpy.invert(self.bitmask)
		self.portNumber = port
		self.highname = highname
		self.lowname = lowname
	def __str__(self):
		return 'DIO' + str(self.channelNumber)


class RampFunctionDescriptor:
	'''describes ramp functions'''
	def __init__(self, sample_definition, time_calculation, value_calculation):
		self.sample_definition = sample_definition
		self.time_calculation = time_calculation
		self.value_calculation = value_calculation

class LabalyzerSettings(dict):
	'''saves settings'''
	
	def __init__(self, *args, **kwds):
		class Publisher(gtk.Invisible): # pylint: disable=R0904
			'''set up signals in a separate class			
			gtk.Invisible has 230 public methods'''
			__gsignals__ = {'changed' : (gobject.SIGNAL_RUN_LAST,
				 gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
				 'loaded' : (gobject.SIGNAL_RUN_LAST,
				 gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,))}
		
		dict.__init__(self, *args, **kwds)
		
		publisher = Publisher()
		self.emit  = publisher.emit
		self.connect  = publisher.connect
		
		if os.name == 'posix':
			# we're on Linux
			from xdg import BaseDirectory #pylint bug; #pylint: disable=W0404
			basePath = BaseDirectory.xdg_config_home
			self.configPath = os.path.join(basePath, 'labalyzer')
			if not os.path.exists(self.configPath):
				os.makedirs(self.configPath)
		elif os.name == 'nt':
			# we're on Windows
			basePath = os.environ['AppData']
			self.configPath = os.path.join(basePath, 'labalyzer')
			if not os.path.exists(self.configPath):
				os.makedirs(self.configPath)
			
		versionPath = os.path.join(self.configPath, 'version') 
		if os.path.exists(versionPath):
			with open(versionPath, 'rb') as f:
				self.version = pickle.load(f)
		else:
			self.version = 0
			


	def loadSettings(self):
		'''load settings from file'''
		settingsPath = os.path.join(self.configPath, 'settings')
		if self.version != SETTINGS_VERSION or not os.path.exists(settingsPath):
			# we need to rest to default
			logger.warn('settings are out of date, need to reset to defaults')
			self.setDefaults()
		else:
			with open(settingsPath, 'rb') as f:
				self.update(pickle.load(f))
		
	def setDefaults(self):
		'''set default values if file can't be read'''
		#pylint: disable=R0915
		self.version = SETTINGS_VERSION
		self['SamplesPerMillisecond'] = 100
		self['DigitalSamplesPerMillisecond'] = 10000
		
		self['AnalogChannels'] = dict()
		self['AnalogChannels']['AOM'] = AnalogChannelDescriptor(1, 0, minvalue=0)
		self['AnalogChannels']['EOM'] = AnalogChannelDescriptor(1, 1, minvalue=0, maxvalue=6)
		self['AnalogChannels']['Big coils'] = AnalogChannelDescriptor(1, 2, minvalue=-12, maxvalue=12, scalefactor=0.847)
		self['AnalogChannels']['MOT coil'] = AnalogChannelDescriptor(1, 3, minvalue=-12, maxvalue=12, scalefactor=0.83333)
		self['AnalogChannels']['Small coil'] = AnalogChannelDescriptor(1, 4, minvalue=-20, maxvalue=20, scalefactor=0.836)
		self['AnalogChannels']['z-wire'] = AnalogChannelDescriptor(1, 5, minvalue=-20, maxvalue=20, scalefactor=0.502)
		self['AnalogChannels']['MC'] = AnalogChannelDescriptor(1, 6, minvalue=-12, maxvalue=12, scalefactor=0.83333)
		self['AnalogChannels']['Repump EOM'] = AnalogChannelDescriptor(1, 7, minvalue=0)
		self['AnalogChannels']['pinch wires'] = AnalogChannelDescriptor(0, 0, minvalue=0, maxvalue=10, scalefactor=1./1.97)
		self['AnalogChannels']['Opt pump AOM'] = AnalogChannelDescriptor(0, 1, minvalue=0)
		self['AnalogChannels']['unused'] = AnalogChannelDescriptor(0, 2)
		self['AnalogChannels']['Probe AOM Detuning'] = AnalogChannelDescriptor(0, 3, minvalue=-5)
		self['AnalogChannels']['extra x-field'] = AnalogChannelDescriptor(0, 4)
		self['AnalogChannels']['Attenuate rf'] = AnalogChannelDescriptor(0, 5)
		self['AnalogChannels']['u-wire'] = AnalogChannelDescriptor(0, 6, minvalue=0)
		self['AnalogChannels']['extra8'] = AnalogChannelDescriptor(0, 7, minvalue=0)

		# digital channels 0-4 correspong to boards a-d
		self['DigitalChannels'] = dict()
		self['DigitalChannels']['Camera trigger'] = DigitalChannelDescriptor(0, 0, 'high', 'low')
		self['DigitalChannels']['OptPump Shutter'] = DigitalChannelDescriptor(0, 1, 'open', 'shut')
		self['DigitalChannels']['MOT Shutter'] = DigitalChannelDescriptor(0, 2, 'open', 'shut')
		self['DigitalChannels']['Probe  shutter'] = DigitalChannelDescriptor(0, 3, 'open', 'shut')
		self['DigitalChannels']['Repump Shutter'] = DigitalChannelDescriptor(0, 4, 'open', 'shut')
		self['DigitalChannels']['None'] = DigitalChannelDescriptor(0, 5, 'open', 'shut')
		self['DigitalChannels']['Rb dispenser'] = DigitalChannelDescriptor(0, 6, 'on', 'off')
		self['DigitalChannels']['FET switches'] = DigitalChannelDescriptor(0, 7, 'on', 'off')
		self['DigitalChannels']['rf sweep'] = DigitalChannelDescriptor(0, 8, 'on', 'off')
		self['DigitalChannels']['RF switch'] = DigitalChannelDescriptor(0, 9, 'output2', 'output1')
		self['DigitalChannels']['MW switch'] = DigitalChannelDescriptor(0, 10, 'on', 'off')
		self['DigitalChannels']['Probe AOM Switch'] = DigitalChannelDescriptor(0, 11, 'on', 'off')
		self['DigitalChannels']['UZ FET switch'] = DigitalChannelDescriptor(0, 12, 'on', 'off')
		self['DigitalChannels']['EIT Shutter'] = DigitalChannelDescriptor(0, 13, 'high', 'low')
		self['DigitalChannels']['Cam shutter'] = DigitalChannelDescriptor(0, 14, 'open', 'shut')
		self['DigitalChannels']['AnalogTrigger'] = DigitalChannelDescriptor(0, 15)

		self['rampFunctions'] = dict()
		self['rampFunctions']['ramp'] = RampFunctionDescriptor("int(ramptime*settings['SamplesPerMillisecond']/1000)", '[int(abs_time + t_step*x) for x in xrange(0, samples+1)]', '[last_values[device] - v_step*x for x in xrange(0, samples+1)]')
		self['rampFunctions']['ramp100'] = RampFunctionDescriptor("int(ramptime*settings['SamplesPerMillisecond']/10/1000)", '[int(abs_time + t_step*x) for x in xrange(0, samples+1)]', '[last_values[device] - v_step*x for x in xrange(0, samples+1)]')
		self['rampFunctions']['ramp_square'] = RampFunctionDescriptor("int(ramptime*settings['SamplesPerMillisecond']/1000)", '[int(abs_time + t_step*x) for x in xrange(0, samples+1)]', '[last_values[device] - v_step/samples*x**2 for x in xrange(0, samples+1)]')
		self['rampFunctions']['ramp100_square'] = RampFunctionDescriptor("int(ramptime*settings['SamplesPerMillisecond']/10/1000)", '[int(abs_time + t_step*x) for x in xrange(0, samples+1)]', '[last_values[device] - v_step/samples*x**2 for x in xrange(0, samples+1)]')
#		self['rampFunctions']['ramp_exp'] = RampFunctionDescriptor("int(ramptime*settings['SamplesPerMillisecond']/1000)", '[int(abs_time + t_step*x) for x in xrange(0, samples+1)]', '[numpy.exp(numpy.log(value-last_values[device]+1)/samples*x)+last_values[device]-1 for x in xrange(0, samples+1)]')
#		self['rampFunctions']['ramp100_exp'] = RampFunctionDescriptor("int(ramptime*settings['SamplesPerMillisecond']/10/1000)", '[int(abs_time + t_step*x) for x in xrange(0, samples+1)]', '[numpy.exp(-numpy.log(last_values[device]-1+value)/samples*x)+last_values[device]-1 for x in xrange(0, samples+1)]')


		
		# for plotter
		self['plot.showCursor'] = False
		self['plot.keepAspect'] = True
		self['plot.maxOD'] = 1
		self['plot.negFrac'] = 0.125
		self['plot.cursorPos'] = [500, 400]
		self['plot.ROI'] = None

		self['physics.magnification'] = 2.26
		self['physics.trapfreq'] = 250
		self['physics.timeofflight'] = 3

		
		# other stuff for main window
		self['main.showDataLog'] = True
		self['main.runFit'] = False
		self['main.fitMethod'] = FIT_MOMS2D
		self['main.saveAll'] = False 
		
		# for andor
		self['andor.temp'] = -60
		self['andor.mode'] = ANDOR_KINETIC
		self['andor.pxSize'] = 13*10**(-6)
		
		# for scans
		self['scan.dummies'] = 5
		
		self['scope.use'] = False
		self['scope.channels'] = []
		
		self['fit.gauss'] = 'lambda p, x: p[0]*numpy.exp(-(x - p[1])**2/(2*p[2]**2)) + p[3]'
		self['fit.lorentz'] = 'lambda p, x: p[0]*p[2]**2/((x - p[1])**2 + p[2]**2) + p[3]'
		self['fit.allowOffset'] = False
		

	def saveSettings(self):
		'''save settings to file'''
		versionPath = os.path.join(self.configPath, 'version') 
		settingsPath = os.path.join(self.configPath, 'settings')
		with open(versionPath, 'wb') as f:
			pickle.dump(self.version, f)
		with open(settingsPath, 'wb') as f:
			pickle.dump(self.items(), f)
		
	
	def update(self, *args, **kwds):
		''' interface for dictionary
		
		send changed signal when appropriate '''
		
		# parse args
		new_data = {}
		new_data.update(*args, **kwds)

		changed_keys = []
		for key in new_data.keys():
			if new_data.get(key) != dict.get(self, key):
				changed_keys.append(key)
		dict.update(self, new_data)
		if changed_keys:
			self.emit('changed', tuple(changed_keys))

	def __setitem__(self, key, value):
		''' interface for dictionary		
		send changed signal when appropriate '''
		if value != dict.get(self, key) or value == None:
			dict.__setitem__(self, key, value)
			self.emit('changed', (key,))


#one instance of the settings class to use everywhere:
settings = LabalyzerSettings()

