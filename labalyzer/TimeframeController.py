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


'''control everything'''

from labalyzer.TimeframeCompiler import TimeframeCompiler
import logging
logger = logging.getLogger('labalyzer')
import csv
import time
from constants import (MODE_CONTINUOUS, MODE_DIRECT, MODE_RUN, MODE_SCAN, MODE_STOPPED, MODE_EXTERNAL, DDSCMD_RESET, DDSCMD_FIXED)

 # for timer
import gobject

# for image mangling
import numpy

import os # for saving data
from datetime import datetime # creating data dir
from labalyzer.helpers import savePGM, openTimeframe, saveTimeframe
import sys
# hardware control
from labcontrol.NIDAQOutputController import NIDAQOutputController
from labcontrol.ViewpointController import ViewpointController
from labcontrol.AndorController import AndorController
from labcontrol.ScopeController import ScopeController
from labcontrol.AgilentController import AgilentController
from labcontrol.AgilentController2 import AgilentController2
from labcontrol.SRSPulseController import SRSPulseController
from labcontrol.RohSchController import RohSchController
from labcontrol.PWS4721Controller import PWS4721Controller

# settings
from labalyzer.LabalyzerSettings import settings


try:
	import psyco #pylint: disable=F0401
	psyco.bind(TimeframeCompiler.compileTimeframe)
except ImportError:
	logger.warn("psyco not available: Timeframe compilation might be slower than expected")


class ScanParameters:
	'''used to store and pass parameters for a Scan'''
	def __init__(self):
		tmp = {'colname': 'Scan', 'rowname': 'Scan', 'start': 0, 'end': 0, 'steps': 0, 'row': None, 'column': None, 'original': ''}
		self.data = [tmp, tmp, tmp]
		self.depth = 0
		self.folder = None
		self.run = 0
		self.dummies = 0
		self.name = 'unnamed' # should be a human-readable name for this scan
		self.totalRuns = 0
		self.timestamp = None
		self.firstTimestamp = None
		self.scanID = None

class TimeframeController:
	'''controls many logic, keeps track of current state, makes sure timeframes are
	started and stopped as appropriate, scans, fitting, everything, really'''
	def __init__(self, timeframe, ui):
		self.timeframe = timeframe # liststore of the timeframe, needs to be passed from the main programme. could also be a simlpe array though.
		self.__data = None # store compiled data for timeframe
		self.compiler = TimeframeCompiler()
		self.timeframeIsLoaded = False
		self.timeframeIsCompiled = False
		self.filename = None
		self.mode = MODE_STOPPED
		self.modeNext = MODE_STOPPED
		self.ui = ui

		self.ui.dlgDataLog.addScan(0, 'global', ['fitX', 'fitY', 'roi'], None)
		self.ui.dlgDataLog.setActiveScan(0)

		self.scanParameters = ScanParameters()
		self.scanInfo = None
		self.nextScanInfo = None

		self.cycleCount = 0

		# create hardware interfaces
		self.__nc = NIDAQOutputController()
		self.__nc.initialize()
		self.__nc.setMode(MODE_STOPPED)
		self.__vpc = ViewpointController()
		self.__vpc.initialize()
		self.__andor = AndorController()
		self.__andor.initialize()
		self.__agilent = AgilentController('labalyzer')
		self.__agilent2 = AgilentController2('labalyzer')
		self.__agilent.initialize()
		self.__agilent2.initialize()
		self.__pulse = SRSPulseController('labalyzer')
		self.__pulse.initialize()
		self.__rohSch = RohSchController('labalyzer')
		self.__rohSch.initialize()
		self.__PWS4721 = PWS4721Controller()
		self.__PWS4721.initialize()

		try:
			self.__scope = ScopeController()
		except: # probably the scope is not connected
			logger.warn('scope initialization failed, disabling scope!')
			settings['scope.use'] = False
		if settings['scope.use']:
			self.__scope.initialize()

		# to regularly check timeframe progress
		# this needs to be polled, no notification possible
		# also needed to check camera for new pictures
		self.timer_id = gobject.timeout_add(100, self.clock_tick)

		# for direct control we need to save current state of all outputs
		self.directDigitalState = [0, 0, 0, 0]
		self.directAnalogState = [numpy.zeros((8, ), dtype=numpy.float64 ), numpy.zeros((8, ), dtype=numpy.float64 )]

		# set the proper default directory for data:
		try:
			os.chdir("E:\Data")
		except OSError:
			try:
				os.chdir("/tmp/")
			except OSError:
				logger.error("Could not set data directory")

		try:
			today = datetime.now().strftime('%Y-%m-%d %a')
			if not os.path.exists(today):
				os.mkdir(today)
			if not os.path.exists(os.path.join(today, 'continuous')):
				os.mkdir(os.path.join(today, 'continuous'))

			if not os.path.exists(os.path.join(today, 'External')):
				os.mkdir(os.path.join(today, 'External'))
			os.chdir(today)
		except OSError:
			logger.error("Could not create data directory")
		self.datadir = os.getcwd()


	def setFilename(self, filename):
		'''set filename of current timeframe'''
		filename = openTimeframe(filename, self.timeframe)
		if filename is not None:
			self.filename = filename
			self.timeframeIsCompiled = False
			self.timeframeIsLoaded = True
			self.prepareTimeframe()
			return filename
		else:
			logger.error('problem loading Timeframe (or cancelled)')


	def prepareTimeframe(self):
		'''prepare next timeframe for execution (potentially while current one is still running'''
		if self.modeNext == MODE_SCAN:
			logger.debug('preparing timeframe for SCAN')
			# we need to prepare a new timeframe, according to the scan parameters
			# otherwise we just recompile the current one if necessary
			self.scanParameters.run += 1
			if self.scanParameters.run <= self.scanParameters.dummies:
				self.nextScanInfo = [['Dummies', '--', str(self.scanParameters.run) + '/' + str(self.scanParameters.dummies)]]
				logger.debug('setting next scan info for dummies')
			else:
				self.timeframeIsCompiled = False
				run = self.scanParameters.run - self.scanParameters.dummies - 1
				if run >= self.scanParameters.totalRuns:
					# reset to original values.
					# also reset mode to regular.
					for i in range(self.scanParameters.depth):
						self.timeframe[self.scanParameters.data[i]['row']][self.scanParameters.data[i]['column']] = self.scanParameters.data[i]['original']
					self.nextScanInfo = None
					self.attemptStateChange(MODE_STOPPED)
					self.attemptStateChange(MODE_CONTINUOUS)
					logger.info('ending scan')
				else:
					# we actually have to change the timeframe according to the scan
					roundcount = [[], [], []]
					roundcount[0] = run % self.scanParameters.data[0]['steps']
					if self.scanParameters.depth > 1:
						roundcount[1] = (run//self.scanParameters.data[0]['steps']) % self.scanParameters.data[1]['steps']
					if self.scanParameters.depth > 2:
						roundcount[2] = (run//self.scanParameters.data[0]['steps']//self.scanParameters.data[1]['steps']) % self.scanParameters.data[2]['steps']

					for i in range(self.scanParameters.depth):
						newpar = self.scanParameters.data[i]['start'] + self.scanParameters.data[i]['stepsize']*roundcount[i]
						self.timeframe[self.scanParameters.data[i]['row']][self.scanParameters.data[i]['column']] = newpar
						self.scanParameters.data[i]['info'] = [self.scanParameters.data[i]['rowname'], str(newpar), str(int(roundcount[i])+1) + '/' + str(int(self.scanParameters.data[i]['steps']))]
					self.nextScanInfo = [self.scanParameters.data[i]['info'] for i in range(self.scanParameters.depth)]
					logger.debug('setting next scan info for SCAN')

		if self.modeNext == MODE_EXTERNAL:
                        logger.debug('loading timeframe for remote control. recompile this timeframe')
                        #enforce that timeframe-file is loaded again; this should cover any external changes made to the timeframe
                        if self.filename is not None: #check first if timeframe has been loaded before
                                openTimeframe(self.filename, self.timeframe) #overwrite the current timeframe
                                self.timeframeIsCompiled = False #forces recompilation
                                self.timeframeIsLoaded = True
                                logger.debug('timeframe overwritten and asked to recompile')
                        else:
                                logger.error('no timeframe for remote control. cannot update any external changes')


		# now we actually have to compile the timeframe. but only if it isn't compiled yet.
		if self.timeframeIsLoaded:
			if len(self.timeframe) == 0:
				logger.warning("tried to compile empty timeframe")
				self.timeframeIsCompiled = False
				return False
			if self.timeframeIsCompiled:
				return True
			self.__data = self.compiler.compileTimeframe(self.timeframe)
			self.timeframeIsCompiled = True
			return True


	def attemptStateChange(self, new_state):
		'''control logic to go from one state to another.
		returns FALSE if state change failed for some reason'''
		recompile = False
		startNew = False
		if new_state == MODE_DIRECT:
			logger.debug('state change to DIRECT')
			if self.mode != MODE_STOPPED:
				return False
			# reset digital outputs to correct value
			self.__vpc.directOutput(self.directDigitalState[0], 0)
			self.__vpc.directOutput(self.directDigitalState[1], 1)
			self.__vpc.directOutput(self.directDigitalState[2], 2)
			self.__vpc.directOutput(self.directDigitalState[3], 3)
			self.__nc.setMode(MODE_DIRECT)
			self.__nc.directOutput(self.directAnalogState)
			self.mode = MODE_DIRECT
			logger.debug('state change completed')
		elif new_state == MODE_STOPPED:
			if self.mode == MODE_DIRECT:
				# stop NIDAQ direct output to avoid error messages
				self.__nc.setMode(MODE_STOPPED)
			if self.modeNext == MODE_STOPPED:
				# already stopping, need to do a hard STOP
				logger.debug('state change to hard STOPPED')
				self.mode = MODE_STOPPED # this stops acquisition and status bar updates, but not actual output from hardware
				self.__nc.stopTask() # this stops actual hardware output, not sure if we want that, though...
				self.__vpc.stop()
			else:
				# soft STOP (stop at end of TF)
				logger.debug('state change to soft STOPPED (run ends with end of current TF)')
				self.modeNext = MODE_STOPPED
			logger.debug('state change completed')
		elif new_state == MODE_RUN:
			logger.debug('state change to RUN')
			if not self.mode == MODE_STOPPED:
				return False # only start a single run if we are stopped, every other case takes precedence
			recompile = True
			startNew = True
			self.modeNext = MODE_RUN
			logger.debug('state change completed')
		elif new_state == MODE_CONTINUOUS:
			logger.debug('state change to CONTINUOUS')
			if self.mode == MODE_SCAN and not self.modeNext == MODE_STOPPED: # Scan takes precedence!
				logger.debug('tried to change from SCAN to CONTINUOUS which is not allowed')
				return False
			if self.mode == MODE_CONTINUOUS:
				logger.debug('state change from CONTINOUS to STOPPED')
				self.modeNext = MODE_STOPPED
			else:
				if self.mode == MODE_STOPPED:
					# only if there is no TF running do we have to start a new one.
					# if there is one running it is sufficient to simply set the right mode.
					recompile = True
					startNew = True
				self.modeNext = MODE_CONTINUOUS
			logger.debug('state change completed')
		elif new_state == MODE_SCAN:
			if self.mode == MODE_SCAN:
				logger.debug('state change from SCAN to STOPPED')
				self.modeNext = MODE_STOPPED
			else:
				logger.debug('state change to SCAN')
				if not self.prepareScan():
					return False
				recompile = True
				if self.mode == MODE_STOPPED:
					startNew = True
				self.modeNext = MODE_SCAN
				logger.debug('state change completed')

		elif new_state == MODE_EXTERNAL:
                        logger.debug('state change to EXTERNAL')
                        if self.mode == MODE_SCAN and not self.modeNext == MODE_STOPPED: # Scan takes precedence!
                                logger.debug('tried to change from SCAN to EXTERNAL which is not allowed')
                                return False
                        if self.mode == MODE_EXTERNAL:
                                logger.debug('state change from EXTERNAL to STOPPED')
                                self.modeNext = MODE_STOPPED
                        else:
                                recompile = True # always enforce recompilation in external mode; main difference compared to CONTINUOUS mode here
                                if self.mode == MODE_STOPPED:
                                        startNew = True
                                self.modeNext = MODE_EXTERNAL
                        logger.debug('state change completed')

		if recompile:
			logger.debug('recompilation requested')
			if not self.prepareTimeframe():
				logger.error('could not compile timeframe!')
				return False
		if startNew:
			self.mode = new_state
			self.startTimeframe()
		self.ui.updateModeInfo(self.mode, self.modeNext)
		return True

	def prepareScan(self):
		'''prepare scan info for scan'''
		if self.scanParameters.depth < 1:
			logger.warn('tried to start SCAN, but no parameters were configured')
			return False
		logger.debug('scan preparation during state change in progress')
		# prepare parameters
		self.scanParameters.dummies = settings['scan.dummies']
		self.scanParameters.run = 0
		self.scanParameters.totalRuns = 1
		scanPoints = []
		for i in range(self.scanParameters.depth):
			self.scanParameters.data[i]['stepsize'] = (self.scanParameters.data[i]['end'] - self.scanParameters.data[i]['start'])/(self.scanParameters.data[i]['steps'] - 1)
			self.scanParameters.totalRuns *= self.scanParameters.data[i]['steps']
			scanPoints.extend([self.scanParameters.data[i]['start'] + self.scanParameters.data[i]['stepsize']*j for j in range(int(self.scanParameters.data[i]['steps']))]) # probably doesn't work for >1D scans
		# prepare scan things

		self.scanParameters.scanID = self.ui.dlgDataLog.getNewScanID()

		timestamp = time.strftime('%H%M%S')
		self.scanParameters.firstTimestamp = timestamp
		self.ui.dlgDataLog.addScan(self.scanParameters.scanID, timestamp + '-' + self.scanParameters.name, ['fit x', 'fit y', 'roi'], scanPoints)
		self.scanParameters.folder = self.datadir + '/' + timestamp + '-' + self.scanParameters.name
		os.makedirs(self.scanParameters.folder)
		with open(self.scanParameters.folder + '/' + self.scanParameters.firstTimestamp + '-' + self.scanParameters.name + '_fitResults.csv', 'a+b') as ifile:
			writer = csv.writer(ifile, delimiter='\t')
			head = []
			for i in range(self.scanParameters.depth):
				head.extend(['parameter name ' + str(i), 'scan value ' + str(i), 'iteration'])
			head.extend(['x-amplitude', 'x-position', 'x-width', 'x-offset', 'y-amplitude', 'y-position', 'y-width', 'y-offset', 'mean', 'NSum', 'NInt', 'Temp', 'n0', 'Phi0'])
			writer.writerow(head)
		logger.info('total runs for scan (without dummies): ' + str(self.scanParameters.totalRuns))
		return True

	def directControlChangeDigital(self, channel, new_state):
		'''send new values to viewpoint card, if in direct control mode'''
		if not self.mode == MODE_DIRECT:
			return
		port = channel.portNumber
		if new_state:
			self.directDigitalState[port] |= channel.bitmask
		else:
			self.directDigitalState[port] &= channel.invertedBitmask
		self.__vpc.directOutput(self.directDigitalState[port], port)

	def directControlChangeAnalog(self, channel, value):
		'''send new values to NIDAQ cards, if in direct control mode'''
		if not self.mode == MODE_DIRECT:
			return
		self.directAnalogState[channel.boardNumber][channel.channelNumber] = value*channel.scalefactor
		# the gtk.Adjustments are set to only allow the correct maximum/minimu values, so we don't have to worry about that here.
		self.__nc.directOutput(self.directAnalogState)

	def directControlChangeDDS(self, frequency, enable):
		'''send new valued to DDS (via viewpoint card) if in direct control mode'''
		def executeDDSCommand(cmd):
			'''actually execute the DDS command'''
			logger.info("executing " + str(len(cmd)) + " DDS commands")
			for c in cmd:
				self.__vpc.directOutput(c, 1)

		if not self.mode == MODE_DIRECT:
			return

		cmd = TimeframeCompiler.translateDDSCommand(DDSCMD_RESET, channel=0, enableChannel=enable)
		executeDDSCommand(cmd)
		cmd = TimeframeCompiler.translateDDSCommand(DDSCMD_FIXED, frequency = int(frequency*1000)) # from kHz to Hz
		executeDDSCommand(cmd)

	def directControlAgilent(self, frequency,amplitude,enable):
		'''send new value to Agilent Function Generator'''
		if enable is True:
			self.__agilent.setFrequency(frequency)
			self.__agilent.setAmplitude(amplitude)
			self.__agilent.setOffset(0)
			logger.info("sending " + str(frequency)+ " Hz to Agilent")

	def directControlAgilent2(self, frequency,amplitude,enable):
		'''send new value to Agilent Function Generator'''
		if enable is True:
			self.__agilent2.setFrequency(frequency)
			self.__agilent2.setAmplitude(amplitude)
			self.__agilent2.setOffset(0)
			logger.info("sending " + str(frequency)+ " Hz to Agilent")

	def directControlAgilentPulse(self, pulse_length, mode):
		self.__agilent.setPulse(pulse_length)
		self.__agilent.setBurstMode()
		self.__agilent.updateBurstMode(mode)

	def directControlAgilent2Pulse(self, pulse_length, mode):
		self.__agilent2.setPulse(pulse_length)
		self.__agilent2.setBurstMode()
		self.__agilent2.updateBurstMode(mode)

	def directControlSRSPulse(self, channel_offsets, mode):
		'''send the command to start the pulse. Can be expanded to include other adjustable features'''
		self.__pulse.preparePulse(channel_offsets, mode)

	def sendSRSPulse(self):
		self.__pulse.sendPulse()

	def iniSine(self):
		self.__agilent.setSine()

	def iniBurst(self):
		self.__agilent.setBurstMode()

	def iniSine2(self):
		self.__agilent2.setSine()

	def iniBurst2(self):
		self.__agilent2.setBurstMode()

	def startRohSchOutput(file_name):
		self.__rohSch.stableOutput(file_name)

	def startVoltageOutput(self,voltage):
		self.__PWS4721.setVoltage(voltage)
		logger.info("sending " + str(voltage)+ " Volt to PWS4721")

	def startTimeframe(self):
		'''start new timeframe'''
		logger.debug("attempting to start timeframe")
		if self.__data is None:
			logger.warn("Tried to start uncompiled Timeframe, or Timeframe is empty")
			if not self.attemptStateChange(MODE_STOPPED):
				logger.error('attempt to stop timeframe failed, but no TF compiled. forcing MODE to STOP')
			return False
		self.__agilent.startOutput(self.__data[3])
		self.__agilent2.startOutput(self.__data[4])
		logger.debug('Agilent waveform generator initialized')
		self.__pulse.startOutput(self.__data[5])
		logger.debug('Pulse generator initialized')
		self.__rohSch.startOutput(self.__data[6])
		logger.debug('Rohde Schwarz generator initialized')
		self.__PWS4721.startOutput(self.__data[7])
		logger.debug('Voltage supply initialized')
		self.__nc.programmeChannels(self.__data[0])
		self.__nc.startTask()
		self.__vpc.programmeChannels(self.__data[1])
		self.__vpc.start()
		logger.debug('viewpoint has started, preparing camera')
		self.__andor.startAcquisition(self.__data[2])
		logger.debug('Camera initialized')
		logger.debug('timeframe has started')

		if self.mode == MODE_SCAN:
			# unfortunately, here, too we have to do a few things about scanning
			self.scanInfo = self.nextScanInfo
			if self.scanInfo == None:
				pass
			else:
				# we have to save the timeframe now, rather than in acquireData, as
				# there it will already be changed for the next run
				self.scanParameters.timestamp = datetime.now().strftime('/%Y%m%d-%H%M%S-')
				baseName = self.scanParameters.folder + self.scanParameters.timestamp
				saveTimeframe(baseName + 'timeframe.csv', self.timeframe)

		if self.mode == MODE_EXTERNAL:
                        # save the timeframe for remote control as for the scan mode
                        baseName = './External/'
                        saveTimeframe(baseName + 'timeframe.csv', self.timeframe) #this will overwrite the file in each run

		# update scan info displayed in UI (if scanInfo is None -> no scan running)
		self.ui.updateScanInfo(self.scanInfo)
		self.ui.updateModeInfo(self.mode, self.modeNext)
		self.cycleCount += 1

		self.prepareTimeframe()
		return True

	def clock_tick(self):
		'''regularly check timeframe progress, poll camera, process results, react if timeframe has finnished'''
		if self.mode == MODE_STOPPED or self.mode == MODE_DIRECT:
			return True # do nothing, but keep timer running
		# no matter what mode it is if it's not MODE_STOPPED, we need to
		# update the progress bar and check the camera for new images.
		# only what is done at the end of a cycle differs from mode to mode

		progress = self.__vpc.getPercentageComplete()
		if progress < 1: # cycle is not finnished yet
			self.ui.pbTimeframeProgress.set_fraction(progress)
			if self.__andor.getNumberAvailableImages() == 3:
				self.acquireData()
		else: # cycle is now finnished. what do we do next?
			logger.debug('cycle has stopped')
			self.__nc.stopTask()
			self.__vpc.stop()
			if self.mode == MODE_RUN:
				self.modeNext = MODE_STOPPED
			if self.modeNext == MODE_STOPPED:
				logger.debug('timeframe finnished, setting mode to STOPPED')
				self.ui.pbTimeframeProgress.set_fraction(0)
				self.mode = MODE_STOPPED
			elif self.modeNext == MODE_CONTINUOUS:
				if self.mode == MODE_SCAN: # we are changing from SCAN to CONTINUOUS, so we have to update the ui one last time
					logger.debug('final ui update to end SCAN')
				self.mode = MODE_CONTINUOUS
				self.startTimeframe()

			elif self.modeNext == MODE_EXTERNAL:
				if self.mode == MODE_SCAN: # we are changing from SCAN to EXTERNAL, so we have to update the ui one last time
					logger.debug('final ui update to end SCAN')
				self.mode = MODE_EXTERNAL
				self.startTimeframe()

			elif self.modeNext == MODE_SCAN:
				self.mode = MODE_SCAN
				self.startTimeframe()
		return True # keep timer running


	def acquireData(self):
		'''called when data is available (near the end of the timeframe
		gets all data from camera (and potentially other devices), and processes/saves it'''
		logger.debug('images are available, attempting to retrieve them')
		absorption = self.__andor.getImage()
		light = self.__andor.getImage()
		dark = self.__andor.getImage()
		upper = 1.*(absorption - dark)
		lower = 1.*(light - dark)
		prod = upper*lower
		upper = numpy.where(prod > 0, upper, 1)
		lower = numpy.where(prod > 0, lower, 1)
		od = -numpy.log(upper/lower)

		self.ui.plotter.setImages((dark, light, absorption, od))

		logger.info('camera temperature is: ' + str(self.__andor.getTemperature()))

		if settings['main.runFit']:# or self.mode == MODE_SCAN:
			fitResult = self.ui.plotter.getImageInfo()
			self.ui.setFitResults(*fitResult)

			if self.mode == MODE_SCAN:
				line = []
				map(line.extend, self.scanInfo) #pylint: disable=W0141
				map(line.extend, fitResult)     #pylint: disable=W0141
				with open(self.scanParameters.folder + '/' + self.scanParameters.firstTimestamp + '-' + self.scanParameters.name + '_fitResults.csv', 'a+b') as ifile:
					writer = csv.writer(ifile, delimiter='\t')
					writer.writerow(line)

				# also update liveview
				if self.scanInfo[0][1] != '--': # the last means we're not in dummies anymore
					self.ui.dlgDataLog.addDataPoint(self.scanParameters.scanID, float(self.scanInfo[0][1]), fitResult)
			self.ui.dlgDataLog.addDataPoint(0, self.cycleCount, fitResult)

		if self.mode == MODE_SCAN or settings['main.saveAll']:
			print 'saving data!'
			try:
				baseName = self.scanParameters.folder + self.scanParameters.timestamp
			except TypeError: # thrown if main.saveAll = True and MODE_SCAN = False, as scanParameter values are then None
				baseName = './continuous/' + datetime.now().strftime('/%Y%m%d-%H%M%S-')
			savePGM(baseName + 'absorption.pgm', absorption)
			savePGM(baseName + 'light.pgm', light)
			savePGM(baseName + 'dark.pgm', dark)

			# also get new scope data (?)
			if settings['scope.use']:
				data = []
				save_x = True
				for c in settings['scope.channels']:
					print 'acquiring scope channel', c
					dx, dy = self.__scope.getTrace(c)
					if save_x and dx is not None:
						data.append(dx)
						save_x = False
					if dy is not None:
						data.append(dy)
				with open(baseName + 'scope.csv', 'wb') as ifile:
					writer = csv.writer(ifile, delimiter='\t')
					writer.writerows(zip(*data))

		if self.mode == MODE_EXTERNAL:
                        logger.info('save the data into folder External for remote use')
                        baseName = './External/'
                        savePGM(baseName + 'absorption.pgm', absorption) #the pictures will be overwritten in every acquireData
                        savePGM(baseName + 'light.pgm', light)
                        savePGM(baseName + 'dark.pgm', dark)

		logger.debug('finished retrieving images')

	def shutdown(self):
		'''cleanup'''
		gobject.source_remove(self.timer_id)
		self.__vpc.shutdown()


		
