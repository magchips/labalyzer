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

'''compile timeframe (text) into a set of commands (analog, digital, camera settings, general settings'''

from labalyzer.constants import * # disable unused import, we need almost everything here #pylint: disable=W0401,W0614
import numpy
from labalyzer.LabalyzerSettings import settings

from math import ceil

import logging
logger = logging.getLogger('labalyzer')

import time
from collections import defaultdict

class RecursionError(Exception):
	'''define error class for recursively defined variables'''
	def __init__(self, value, unparsed):
		Exception.__init__(self)
		self.value = value
		self.unparsed = unparsed
	def __str__(self):
		return repr(self.value)

class TimeframeCompiler:
	'''provides everything needed to compile a timeframe'''
	def __init__(self):
		self._vars = dict()
		self.ddsBitMode = None

	def parseVariables(self, timeframe):
		'''traverse timeframe and parse all variable definitions'''
		self._vars.clear()
		unparsed = dict()

		for row in timeframe: # create dictionary of variable names
			if self.getRowType(row) == ROWTYPE_PARAMETER:
				if row[COL_VARNAME] in unparsed:
					row[COL_ERROR] = 'warning: doubly defined variable name for variable: '
					row[COL_COLORHINT] = '#FF0000'
				else:
					unparsed[row[COL_VARNAME]] = row[COL_VALUE]
					row[COL_ERROR] = 'variable definition' # we don't actually know yet that the variable definitions here are ok until we're through evaluating them!
					row[COL_COLORHINT] = '#00FFFF'

		count = 0
		while len(unparsed) > 0: # walk through dict and resolve everything you can. repeat until we reach 64 recursions.
			count += 1
			if count > 64:
				logging.error('maximum recursion depth reached in variable evaluation')
				raise RecursionError('Maximum Recursion Depth Reached! Check Timeframe!', unparsed)
			for key in unparsed.keys():
				v = self.__evaluateCell__(unparsed[key])
				if v is not None:
					self._vars[key] = v
					del unparsed[key]

		return self._vars

	def compileTimeframe(self, timeframe):
		'''traverse timeframe and compile all commands'''
		startTime = time.time()
		self.parseVariables(timeframe) # make sure all variable definitions are ok
		########################################################################
		## what we try to do in this first section:
		## we go through the timeframe and assemble a list of all the absolute times when either the analog data, or the digital data needs to be updated.
		## in fact two lists, one for analog, one for digital signals. this improves processing speed
		## we store these times, together with the data that needs to be updated in a big dictionary
		## for each time and device we store a tuple with three entries: board number, channel number, value
		## for analog devices:	board number is 0 or 1, equivalent to dev1 and dev2
		##											channel number is 0-7, number of the channel that changes
		##											value is the new value it changes to
		## for digital devices: board number: really is port number, 2-5 where 2=portA etc. it starts at 2 because the first 2 entries in the array we later create hold the timestamp
		##											channel number: here abused as the bitmask to be set. for setting to high: only the changing bit is high; for setting to low: only the changing bit is low
		##											value: can be 0 or 1 equivalent to low or high
		## whenever we add an analog entry we also add digital triggers for it, setting the device 'AnalogTrigger' first high and TRIGGER_LENGTH (typically 5µs) later low.
		## all times are internally treated as integer micro seconds
		######################################################################

		abs_time = 0							# keep track of total time up to a given entry
		analogCommands = defaultdict(list)		# store analog commands
		digitalCommands = defaultdict(list)		# store digital commands
		cameraSettings = {"AcquisitionMode" : ANDOR_KINETIC, "X min" : 1, "Y min" : 1, "X max" : 1024, "Y max" : 1024, "Binning" : 1, "Exposure" : 0.2}
		agilentSettings = {"Freq" : 5000, "Amp" : 1, "PulseLength": 0} #goes into pulse mode if PulseLength isn't zero
		agilentSettings2 = {"Freq" : 5000, "Amp" : 1, "PulseLength": 0}
		srsPulseSettings = {"ABPulseLength": 200, "CDPulseLength": 200, "RelativeDelay": 200, "PulseLength":0} #values are in nm. RD can be negative
		rohSchSettings = {"Freq" : 300000000, "Output" : 1.0}
		PWSSettings={"Voltage" : 0}
		errorEncountered = False

		trigBoard = settings['DigitalChannels']['AnalogTrigger'].portNumber							# needed multiple times below
		trigMask = settings['DigitalChannels']['AnalogTrigger'].bitmask									# needed multiple times below
		invertedTrigMask = settings['DigitalChannels']['AnalogTrigger'].invertedBitmask	# needed multiple times below

		last_values = dict()			# these are needed for ramps to know the point of origin of a ramp
		lastDDSFreq = 0							# needed to know starting point of DDS ramps
		for k in settings['AnalogChannels']:
			last_values[k] = float(0.0)

		for row in timeframe:		 # go through the timeframe row by row
			t = self.__evaluateCell__(row[COL_TIME])
			if t is not None:			 # only add new time if it is actually valid
				t = int(1000*t)
				abs_time += t				 # so now abs_time is valid for the current row

			device = row[COL_DEVICE]	# determine which device we're talking about
			rowtype = self.getRowType(row)		# determine if it is analog, digital or something else...

			if rowtype == ROWTYPE_ANALOG:
				rampType = row[COL_RAMPTYPE]
				if rampType != 'free':
					value = self.__evaluateCell__(row[COL_VALUE]) # turn the value into a number, in case it contains a variable
					if value == None:
						row[COL_ERROR] = 'invalid analog value'
						row[COL_COLORHINT] = '#FF0000'
						errorEncountered = True
						continue # ignoring this line
				
					if value > settings['AnalogChannels'][device].maxvalue:				# and also constrain to maximum allowed values
						logger.error('need to constrain value of ' + device + ' which was too large; requested value was ' + str(value))
						value = settings['AnalogChannels'][device].maxvalue
					if value < settings['AnalogChannels'][device].minvalue:
						logger.error('need to constrain value of ' + device + ' which was too small; requested value was ' + str(value))
						value = settings['AnalogChannels'][device].minvalue
					
					
					value = settings['AnalogChannels'][device].scalefactor*value	 # adjust for possible scaling of the value,
					if value > 10: # hard limits to stop NIDAQ from crashing!
						value = 10
					if value < -10:
						value = -10
				
				boardNumber = settings['AnalogChannels'][device].boardNumber
				channelNumber = settings['AnalogChannels'][device].channelNumber
				
				if rampType == 'step':	# so we just add one command
					if not abs_time in analogCommands: # need to add triggers to the digital commands
						digitalCommands[abs_time].append((trigBoard, trigMask, 1))
						digitalCommands[abs_time + TRIGGER_LENGTH].append((trigBoard, invertedTrigMask, 0))
					analogCommands[abs_time].append((boardNumber, channelNumber, value))
					last_values[device] = value
					# and finally the things we always have to do for a step
					row[COL_ERROR] = ' '.join(['ok, new value = ', str(value)])
					row[COL_COLORHINT] = '#00FF00'
				elif rampType in settings['rampFunctions']:
					ramptime = int(10*self.__evaluateCell__(row[COL_RAMPTIME]))*100
					if ramptime is not None:
						samples = eval(settings['rampFunctions'][rampType].sample_definition)		# number of samples, according to function table; used in evaluation!
						t_step = 1.*ramptime/samples																						# length of a timestep; used in evaluation!
						v_step = 1.*(last_values[device] - value)/samples												# height of a voltage step; used in evaluation!
						times = eval(settings['rampFunctions'][rampType].time_calculation)			# allows for nonlinear timeramps
						values = eval(settings['rampFunctions'][rampType].value_calculation)		# or nonlinear voltageramps
						for i, t in enumerate(times):
							if not t in analogCommands: # need to add triggers
								digitalCommands[t].append((trigBoard, trigMask, 1))
								digitalCommands[t + TRIGGER_LENGTH].append((trigBoard, invertedTrigMask, 0))
							analogCommands[t].append((boardNumber, channelNumber, values[i]))
						# and finally the things we always have to do for a ramp
						row[COL_ERROR] = ' '.join(['ok, ramping from ' + str(last_values[device]), 'to', str(value), 'in', str(ramptime/1000.), 'ms'])
						row[COL_COLORHINT] = '#00FF00'
						last_values[device] = value
					else: # ramptime did not evaluate
						row[COL_ERROR] = 'ramptime invalid!'
						row[COL_COLORHINT] = '#FF0000'
						errorEncountered = True 
				elif rampType == 'free':
					ramptime = int(10*self.__evaluateCell__(row[COL_RAMPTIME]))*100
					# free function definition
					# use default ramp times for now
					samples = eval(settings['rampFunctions']['ramp'].sample_definition)
					t_step = 1.*ramptime/samples
					times = eval(settings['rampFunctions']['ramp'].time_calculation)
					x = numpy.linspace(0, 1, samples+1)
					values = eval(row[COL_VALUE])
					if last_values[device] != 0:
						values /= (values[0]/last_values[device])
					else:
						values -= values[0]
					for i, t in enumerate(times):
						if not t in analogCommands: # need to add triggers
							digitalCommands[t].append((trigBoard, trigMask, 1))
							digitalCommands[t + TRIGGER_LENGTH].append((trigBoard, invertedTrigMask, 0))
						analogCommands[t].append((boardNumber, channelNumber, values[i]))
					row[COL_ERROR] = 'free ramp, ending on ' + str(values[-1])
					row[COL_COLORHINT] = '#00FF00'
					
				else: # ramp function not in function dict
						row[COL_ERROR] = 'unknown ramp function!'
						row[COL_COLORHINT] = '#FF0000'
						errorEncountered = True
			elif rowtype == ROWTYPE_DIGITAL: # Device for DIO64 card
				value = row[COL_VALUE] # don't evaluate this as it encodes only open/close/high/low etc.
				if value == settings['DigitalChannels'][device].highname:
					digitalCommands[abs_time].append((settings['DigitalChannels'][device].portNumber, settings['DigitalChannels'][device].bitmask, 1))
					row[COL_ERROR] = 'ok, new value = 1'
					row[COL_COLORHINT] = '#00FF00'
				elif value == settings['DigitalChannels'][device].lowname:
					digitalCommands[abs_time].append((settings['DigitalChannels'][device].portNumber, settings['DigitalChannels'][device].invertedBitmask, 0))
					row[COL_ERROR] = 'ok, new value = 0'
					row[COL_COLORHINT] = '#00FF00'
				else:
					row[COL_ERROR] = 'new state unknown!'
					row[COL_COLORHINT] = '#FF0000'
					errorEncountered = True
			elif rowtype == ROWTYPE_DDS: # create commands for DDS
				instruction = row[COL_DDSINSTRUCTION]
				if instruction == 'reset':
					cmds = self.translateDDSCommand(DDSCMD_RESET, channel=0, enableChannel=True)
				elif instruction == 'step':
					freq = int(self.__evaluateCell__(row[COL_VALUE])*1000) 		# conversion kHz to Hz
					if freq == None:
						row[COL_ERROR] = 'invalid frequency value'
						row[COL_COLORHINT] = '#FF0000'
						errorEncountered = True
						continue
					cmds = self.translateDDSCommand(DDSCMD_FIXED, freq)
					lastDDSFreq = freq
				elif instruction == 'DDSramp' or instruction == 'ramp': # TODO: use single tone sweeps for ramp, and all ramps defined in settings['rampFunctions']
					freq = int(self.__evaluateCell__(row[COL_VALUE])*1000)# conversion kHz to Hz
					ramptime = self.__evaluateCell__(row[COL_RAMPTIME])
					if freq == None:
						row[COL_ERROR] = 'invalid frequency value'
						row[COL_COLORHINT] = '#FF0000'
						errorEncountered = True
						continue
					if ramptime == None:
						row[COL_ERROR] = 'invalid ramp time'
						row[COL_COLORHINT] = '#FF0000'
						errorEncountered = True
						continue
					cmds = self.translateDDSCommand(DDSCMD_RAMP, fstart=lastDDSFreq, fend=freq, rampTime=ramptime)
					lastDDSFreq = freq
				else:
					row[COL_ERROR] = 'unknown DDS command'
					row[COL_COLORHINT] = '#FF0000'
					errorEncountered = True
					continue
				for indx, cmd in enumerate(cmds):
					t = abs_time + 5000.*indx/settings['DigitalSamplesPerMillisecond'] # higher update frequencies than 1/5x the fundamental DIO frequency somehow don't work
					digitalCommands[t].append((1, cmd, 0)) # high or low don't matter here, the value is copied directly; board 1 is B is DDS
				if instruction == 'ramp':
					row[COL_ERROR] = 'processed, but depreceated'
					row[COL_COLORHINT] = '#808080'
				else:
					row[COL_ERROR] = 'ok'
					row[COL_COLORHINT] = '#00FF00'
			elif rowtype == ROWTYPE_COMMENT:
				row[COL_ERROR] = 'Comment, ignoring this line'
				row[COL_COLORHINT] = '#FFFF00'
			elif rowtype == ROWTYPE_PARAMETER or rowtype == ROWTYPE_EMPTY:
				pass # need not be treated here, taken care of in ParseVariables
			elif rowtype == ROWTYPE_CAMERA:
				item = row[COL_CAMITEM]
				if item in cameraSettings: # we only accept the keys defined already above. other keys won't be understood and hence have to be refused here
					cameraSettings[item] = self.__evaluateCell__(row[COL_CAMVALUE])
					row[COL_ERROR] = 'Camera information set'
					row[COL_COLORHINT] = '#00FFFF'
				else:
					row[COL_ERROR] = 'Unknown camera setting'
					row[COL_COLORHINT] = '#FF0000'
					errorEncountered = True
					
			elif rowtype == ROWTYPE_AGILENT:
				item = row[COL_AGILENTITEM]
				if item in agilentSettings: # we only accept the keys defined already above. other keys won't be understood and hence have to be refused here
					agilentSettings[item] = self.__evaluateCell__(row[COL_VALUE])
					row[COL_ERROR] = 'Agilent information set'
					row[COL_COLORHINT] = '#00FFFF'
				else:
					row[COL_ERROR] = 'No valid Agilent setting'
					row[COL_COLORHINT] = '#FF0000'
					errorEncountered = True

			elif rowtype == ROWTYPE_AGILENT2:
				item = row[COL_AGILENTITEM]
				if item in agilentSettings2: # we only accept the keys defined already above. other keys won't be understood and hence have to be refused here
					agilentSettings2[item] = self.__evaluateCell__(row[COL_VALUE])
					row[COL_ERROR] = 'Agilent information set'
					row[COL_COLORHINT] = '#00FFFF'
				else:
					row[COL_ERROR] = 'No valid Agilent setting'
					row[COL_COLORHINT] = '#FF0000'
					errorEncountered = True

			elif rowtype == ROWTYPE_SRSPULSE:
				item = row[COL_SRSPULSEITEM]
				if item in srsPulseSettings: # we only accept the keys defined already above. other keys won't be understood and hence have to be refused here
					srsPulseSettings[item] = self.__evaluateCell__(row[COL_VALUE])
					row[COL_ERROR] = 'SRS pulse information set'
					row[COL_COLORHINT] = '#00FFFF'
				else:
					row[COL_ERROR] = 'No valid SRS Pulse setting'
					row[COL_COLORHINT] = '#FF0000'
					errorEncountered = True

			elif rowtype == ROWTYPE_ROHSCH:
				item = row[COL_ROHSCHITEM]
				if item in rohSchSettings:
					rohSchSettings[item] = self.__evaluateCell__(row[COL_VALUE])
					row[COL_ERROR] = 'RohSch information set'
					row[COL_COLORHINT] = '#00FFFF'
				else:
					row[COL_ERROR] = 'No valid RohSch setting'
					row[COL_COLORHINT] = '#FF0000'
					errorEncountered = True

			elif rowtype == ROWTYPE_PWS:
				print "Voltage Source"
				item = row[COL_PWSITEM]
				if item in PWSSettings:
					PWSSettings[item] = self.__evaluateCell__(row[COL_VALUE])
					row[COL_ERROR] = 'PWS4721 information set'
					row[COL_COLORHINT] = '#00FFFF'
				else:
					row[COL_ERROR] = 'No valid PWS4721 setting'
					row[COL_COLORHINT] = '#FF0000'
					errorEncountered = True
			else:
				row[COL_ERROR] = 'unknown device'
				row[COL_COLORHINT] = '#FF0000'
				errorEncountered = True
			if rowtype is not ROWTYPE_EMPTY: # looks prettier to leave it out on emtpy lines, that's all
				row[COL_ABSTIME] = abs_time/1000.
		# loop through timeframe rows ends here
		#########################################
		
		# we have to add one high-low sequence on the "Analog Trigger" line to finnish the cycle for the NI devices.
		# not sure why this should be necessary, but having the trigger in the end ensures correct timing
		# without this the NI programming crashes at the end of the cycle
		digitalCommands[abs_time+2*TRIGGER_LENGTH] = [(trigBoard, trigMask, 1)]
		digitalCommands[abs_time+3*TRIGGER_LENGTH] = [(trigBoard, invertedTrigMask, 0)]

		totalTime = abs_time+3*TRIGGER_LENGTH


		########################################################################
		## now we know how many commands have to be sent to the different devices from the length of the lists above.
		## so we create buffers for these commands, and then traverse the lists from above to fill those buffers.
		########################################################################
		# to convert the time to the bloody timestamps this DIO64 needs:
		# the lower word (least significant word, first column in the array to be passed):
		#	 lowword = time & 0x0000FFFF
		# the upper word (most significant word, second column in the array to be passed):
		#	 highword = time >> 16
		# the timestamp will be the sample number, so (real time)*(digital samples per unit time)
		# the array is a 1D version of a 2D array which is built rowwise, i.e.
		# lowword, highword, data1, data2, data3, data4, lowword, highword, data1, data2, data3, data4 etc.
		# for the buffer size we only count rows, so the buffer size for the version above would be 2.
		# we can leave out data2-3 if we want, depending on the mask we set before
		# if true, we could set the mask to F00F and pass only data1 (for real data) and data4 (for DDS)
		# this would mean a total of 4 columns, two for time and two for data
		# but that doesn't actually improve calculation speed, so we'll keep all columns for now
		# this lower part is where most of the CPU time of this function is spent

		AOSamples = [numpy.zeros((len(analogCommands)*8, ), dtype=numpy.float64 ), numpy.zeros((len(analogCommands)*8, ), dtype=numpy.float64 )] # *8 for 8 channels, two elements in list for device 1 and 2
		DIOSamples = numpy.zeros((len(digitalCommands)*6, ), dtype=numpy.uint16) # 6 = 2 for the timestamp + 4 (for 16 channels in A through D)

		analogKeys = sorted(analogCommands.iterkeys())
		digitalKeys = sorted(digitalCommands.iterkeys())
		timeOffset = digitalKeys[0] # needed in case the timeframe starts at negative times
		
		for i, k in enumerate(analogKeys):
			if i != 0:
				AOSamples[0][8*i:8*(i+1)] = AOSamples[0][8*(i-1):8*i]
				AOSamples[1][8*i:8*(i+1)] = AOSamples[1][8*(i-1):8*i]
			for entry in analogCommands[k]:
				AOSamples[entry[0]][8*i+entry[1]] = entry[2]

		for i, k in enumerate(digitalKeys):
			if i != 0:
				DIOSamples[6*i+2:6*(i+1)] = DIOSamples[6*(i-1)+2:6*i] # only need to copy last 4 entries, timestamp always is overwritten
			timestamp = int((k - timeOffset)*settings['DigitalSamplesPerMillisecond']/1000) # the timestamp calculation takes ~ 5% total compilation time
			DIOSamples[6*i] = timestamp & 0x0000FFFF
			DIOSamples[6*i + 1] = timestamp >> 16
			for entry in digitalCommands[k]:
				if entry[0] == 0: # entry[0] is the board number
					if entry[2] == 1: # entry[2] is 1 or 0 for high or low
						DIOSamples[6*i+2] |= entry[1]	# entry[1] already holds the bitmask for this channel (set above), not just the real channelnumber7
					else:
						DIOSamples[6*i+2] &= entry[1]	# entry[1] already holds the inverted trigmask as set above
				
				elif entry[0] == 1:								# this is for the DDS programming; they always set the entire bitline, so we don't have to xor anything...
					DIOSamples[6*i+3] = entry[1]
				elif entry[0] == 2: # entry[0] is the board number
					if entry[2] == 1: # entry[2] is 1 or 0 for high or low
						DIOSamples[6*i+4] |= entry[1]	# entry[1] already holds the bitmask for this channel (set above), not just the real channelnumber7
					else:
						DIOSamples[6*i+4] &= entry[1]	# entry[1] already holds the inverted trigmask as set above
				elif entry[0] == 3:								# moving the trigger for the analog channels to a dedicated port (D in this case) speeds compilation up by 30% (maybe not!)
					if entry[2] == 1: # entry[2] is 1 or 0 for high or low
						DIOSamples[6*i+5] |= entry[1]	# entry[1] already holds the bitmask for this channel (set above), not just the real channelnumber7
					else:
						DIOSamples[6*i+5] &= entry[1]	# entry[1] already holds the inverted trigmask as set above

		logger.info("total timeframe time is " + str(totalTime/1000.) + ' ms')
		logger.info("number of analog commands is " + str(len(analogCommands)))
		logger.info("number of digital commands (including analog triggers) is " + str(len(digitalCommands)))
		logger.info("compilation time of timeframe was " + str(round((time.time() - startTime)*1000)) + 'ms')
		
#		import matplotlib.pyplot as plt
#		for k in range(0, 8):
#			plt.plot(numpy.array(sorted(analogKeys))/1.e6, AOSamples[0][k::8])
#			plt.plot(numpy.array(sorted(analogKeys))/1.e6, AOSamples[1][k::8])
#		plt.plot(numpy.array(sorted(digitalCommands.iterkeys()))/1.e6, (DIOSamples[3::6] & 1), 's')
#		plt.show()
		if errorEncountered:
			logger.warn('#################################################')
			logger.warn('error during Timeframe compilation! Check Timeframe!')
			logger.warn('#################################################')
		return (AOSamples, DIOSamples, cameraSettings, agilentSettings, agilentSettings2, srsPulseSettings, rohSchSettings,PWSSettings)

	@staticmethod
	def getRowType(row): 
		'''determine whether a row is a variable definition, digital I/O, analog I/O, DDS, etc...'''
		#pylint: disable=R0911
		if row[COL_TIME] == '':
			return ROWTYPE_EMPTY # we really want to do this?
		if row[COL_TIME][0] == '\\':
			return ROWTYPE_COMMENT
		if row[COL_EXTERNAL] == 'External':
			if row[COL_DEVICE] == 'parameter':
				return ROWTYPE_PARAMETER
			if row[COL_DEVICE] == 'camera':
				return ROWTYPE_CAMERA
			if row[COL_DEVICE] == 'agilent':
				return ROWTYPE_AGILENT
			if row[COL_DEVICE] == 'agilent2' :
				return ROWTYPE_AGILENT2
			if row[COL_DEVICE] == 'srspulse' :
				return ROWTYPE_SRSPULSE
			if row[COL_DEVICE] == 'rohsch' :
				return ROWTYPE_ROHSCH
			if row[COL_DEVICE] == 'PWS4721' :
				return ROWTYPE_PWS
		device = row[COL_DEVICE]
		if device in settings['AnalogChannels']:
			return ROWTYPE_ANALOG
		if device in settings['DigitalChannels']:
			return ROWTYPE_DIGITAL
		if device == 'rf0' or device == 'rf1':
			return ROWTYPE_DDS

		return ROWTYPE_UNKNOWN


	def __evaluateCell__(self, text):
		'''evaluate a given cell, with the right variable definitions'''
		if text == '' or text[0] == '\\': # the last is for a comment. this should be special-cased! we should probably determine the linetype before calling evaluateCell afterall!
			return None
		try:
			return eval(text, None, self._vars)
		except NameError:
			return None
			
	@staticmethod
	def translateDDSCommand(cmd, frequency=None, channel=0, enableChannel=True, fstart=None, fend=None, rampTime=None):
		'''turn a DDS Command in a sequence of commands to send to the DIO64'''
		# since each bit is registered on the rising edge of SCKL, we have 16 commands
		# to send to the DDS for every byte of programming (ignoring dedicated pins)
		# and since we use the viewpoint card, for each bit we actually have to update all 16 channels
		# of the viewpoint port associated with the DDS
		# so in the end we have something 16 bit wide (each channel of the viewpoint card)
		# and 16 entries deep for each byte
		if not channel == 0:
			logger.warn('trying to program DDS channel != 0, which is not implemented')
		
		def dataToCommands(data, length, bitmode=1):
			'''actual translation'''
			if bitmode not in [1, 2, 4]:
				raise RuntimeError("Unsupported Bitmode!")
			xfers = length*8/bitmode
			buff = numpy.zeros(2*xfers, dtype=numpy.uint16)
			for i in range(xfers):
				val = 0
				for j in range(bitmode):
					val |= (data & 1)*PIN_SDIO[j]
					data >>= 1
				buff[-2*i-2] = val
				buff[-2*i-1] = val | PIN_SCLK
			return buff
			

		if cmd == DDSCMD_RESET:
			# first we issue a reset (2 bits, PIN_RST high, all low)
			# then we programme FR1 to set VCO gain and PLL ratio; this takes another 4 bytes including the instruction byte; so 64 commands more
			# then we add an IO update (another 2 commands) 
			# then we set the channel and bitmode which takes another 2 bytes, i.e. 32 commands
			# another I/O Update to activate the new bitmode
			# finally we set the amplitude, which requires 4 bytes, i.e. another 64 commands (in single-bit mode, 16 cmds in 4-bit mode)
			cmds = numpy.zeros(2+64+2+32+2+16, dtype=numpy.uint16)
			
			# issue reset
			cmds[0] = PIN_RST
			cmds[1] = 0
			
			# set PLL ratio and VCC gain
			ins = 0x01 # instruction byte, FR1, 3 bytes payload
			data = ins << 24|0b110100000000000000000000 # hardcoded x20 PLL multiplier
			cmds[2:66] = dataToCommands(data, 4)

			# issue I/O UPDATE
			cmds[66] = PIN_IOUPDATE
			cmds[67] = 0
						
			# programme channel
			ins = 0
			# csr = 2**4 # bitmode = 1
			csr = 2**4 | 6 # bitmode = 4
			if not enableChannel: 
				csr = 0
			data = ins << 8|csr
			cmds[68:100] = dataToCommands(data, 2)
			
			# send another I/O UPDATE to register bitmode!
			cmds[100] = PIN_IOUPDATE
			cmds[101] = 0
				
			# set amplitude:
			ins = 0x06
			data = ins << 24|0b111111110000001000000001 # 0b111111110001001000000001 in labview, but then I can't reset to single tone mode for some reason!
			cmds[102:118] = dataToCommands(data, 4, 4)
			return cmds
		
		if cmd == DDSCMD_FIXED:
			if frequency is None:
				raise RuntimeError("Need to set frequency")
			
			cmds = numpy.zeros(16+2+(10)*2+2, dtype=numpy.uint16)  # 40 bit (8bit instruction, 32bit data), times two for SCLK/4 for 4-bit mode
			
			# programme channel function register CFR to turn off sweeping
			ins = 0x03
			data = ins << 24 | 0b000000000000001100010100
			cmds[0:16] = dataToCommands(data, 4, 4)	
				
			# issue IO/UPDATE
			cmds[16] = PIN_IOUPDATE
			cmds[17] = 0
						
			# programme frequency				
			ins = 0x04 # instruction byte
			data = ins << 32|int(2.**32*frequency/DDS_FREQUENCY)
			cmds[18:38] = dataToCommands(data, 5, 4)

			# issue IO/UPDATE
			cmds[38] = PIN_IOUPDATE
			cmds[39] = 0
			
			return cmds
			
		if cmd == DDSCMD_RAMP:
			#####################################################################
			## ramps always first go from the lower frequency to the upper and then back down to the lower frequency
			## the ramp up is executed when the profile pin PIN_P0 goes high, the downwards ramp when it goes low
			## this means that for a downscan there is always first a (very brief) upscan
			## and for an upscan there is a subsequent (very brief) downscan
			#####################################################################
			
			if fstart is None or fend is None or rampTime is None:
				print fstart, fend, rampTime
				raise RuntimeError("Required parameters not supplied or invalid parameters")
			
			revert = False
			if fend < fstart:
				# we want a downscan
				fend, fstart = fstart, fend
				revert = True
				
			cmds = numpy.zeros(20+20+20+20+12+16+4, dtype=numpy.uint16)
			
			rampTime /= 1000. # convert from ms to seconds
			rampRateRes = 1.*DDS_FREQUENCY**2/2**42 # should be a constant
			desiredRampRate = 1.*abs(fstart - fend)/rampTime
			trueRampRateTicks = int(desiredRampRate/rampRateRes)
			trueRampRateTime = ceil(desiredRampRate/rampRateRes)*rampRateRes			
			freqRange = trueRampRateTime*rampTime
			fend = fstart + freqRange
			
			if revert:
				# scan down
				rdw = 2**32-1							# rising delta word, nothing
				fdw = trueRampRateTicks 	# falling delta word, real value
				lsr	=	0b1111111100000001	# ramp rate
			else:
				# scan up
				rdw = trueRampRateTicks 	# rising delta word, real value
				fdw = 2**32-1							# falling delta word, nothing
				lsr	=	0b0000000111111111	# ramp rate
			
			# set frequency tuning word 0x04 for start frequency
			ins = 0x04
			data = ins << 32 | int(2.**32*fstart/DDS_FREQUENCY)
			cmds[0:20] = dataToCommands(data, 5, 4)
			
			# set frequency tuning word 0x0A for end frequency
			ins = 0x0A
			data = ins << 32 | int(2**32*fend/DDS_FREQUENCY)
			cmds[20:40] = dataToCommands(data, 5, 4)
			
			# programme rising delta word
			ins = 0x08
			data = ins << 32 | rdw
			cmds[40:60] = dataToCommands(data, 5, 4)
			
			# programme falling delta word
			ins = 0x09
			data = ins << 32 | fdw
			cmds[60:80] = dataToCommands(data, 5, 4)
			
			# programme sweep ramp rate
			ins = 0x07
			data = ins << 16 | lsr
			cmds [80:92] = dataToCommands(data, 3, 4)
			
			# programme channel function register CFR
			ins = 0x03
			data = ins << 24 | 0b100000000110001100000000
			cmds[92:108] = dataToCommands(data, 4, 4)
			
			
			if revert:
				# scan down 
				cmds[108] = PIN_IOUPDATE
				cmds[109] = 0
				cmds[110] = PIN_P0
				cmds[111] = 0
			else:
				# scan up
				cmds[108] = PIN_IOUPDATE
				cmds[109] = 0
				cmds[110] = 0
				cmds[111] = PIN_P0

					
			return cmds

	
