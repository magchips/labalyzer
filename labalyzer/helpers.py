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

'''provides a few helper functions'''

import csv
import logging
logger = logging.getLogger('labalyzer')
import gtk

def getText(title, label='', subtitle=''):
	'''create dialog to get a simple text input'''
	def responseToDialog(_entry, dialog, response):
		'''get response function'''
		dialog.response(response)		#base this on a message dialog
	dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK, None)
	dialog.set_markup(title)
	#create the text input field
	entry = gtk.Entry()
	#allow the user to press enter to do ok
	entry.connect("activate", responseToDialog, dialog, gtk.RESPONSE_OK)
	#create a horizontal box to pack the entry and a label
	hbox = gtk.HBox()
	hbox.pack_start(gtk.Label(label), False, 5, 5)
	hbox.pack_end(entry)
	#some secondary text
	dialog.format_secondary_markup(subtitle)
	#add it and show it
	dialog.vbox.pack_end(hbox, True, True, 0) #pylint-bug #pylint: disable=E1101
	dialog.show_all()

	dialog.run()
	text = entry.get_text()
	dialog.destroy()
	return text

def getChoice(title, highButton='Button1', lowButton='Button2', subtitle=''):
	'''create dialog to get a simple two-button yes/no choice'''
	def responseToDialog(_entry, dialog, response):
		'''response function'''
		dialog.result = response
		dialog.response(gtk.RESPONSE_OK)		#base this on a message dialog
	dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_NONE, None)
	dialog.result = None
	dialog.set_markup(title)
	#create the text input field
	btn1 = gtk.Button(highButton)
	btn1.connect("clicked", responseToDialog, dialog, highButton)
	btn2 = gtk.Button(lowButton)
	btn2.connect("clicked", responseToDialog, dialog, lowButton)
	hbox = gtk.HBox()
	hbox.pack_start(btn1)

	hbox.pack_end(btn2)
	#some secondary text
	dialog.format_secondary_markup(subtitle)
	#add it and show it
	dialog.vbox.pack_end(hbox, True, True, 0)  #pylint-bug #pylint: disable=E1101
	dialog.show_all()

	dialog.run()
	result = dialog.result
	dialog.destroy()
	return result
	
	
def savePGM(filename, data):
	'''save image data as 16 bit PGM file'''
	with open(filename, 'wb') as f:
		f.write("%s\n" % ("P5")) 
		f.write("%d %d\n" % (data.shape[1], data.shape[0])) 
		f.write("%d\n" % (65535)) 
		f.write(data.byteswap()) # matlab expects big-endian for 16 bit PGM files??

def openTimeframe(filename, timeframe):
	'''logic to open timeframe files, all versions'''
	if filename is None:
		chooser = gtk.FileChooserDialog(title=None, action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		chooser.set_current_folder('.')
		chooser.set_default_response(gtk.RESPONSE_OK)
		response = chooser.run()
		if response == gtk.RESPONSE_OK:
			filename = chooser.get_filename()
			chooser.destroy()
		elif response == gtk.RESPONSE_CANCEL:
			chooser.destroy()
			return None
			
	timeframe.clear()

	with open(filename, 'rb') as ifile:
		reader = csv.reader(ifile, delimiter='\t')
		tmp = reader.next()
		if len(tmp) in [9, 10, 11]:
			logger.debug('opening old-style timeframe with padding at line ends')
			tmp = tmp[0:9]
			tmp.append('#FFFFFF')
			timeframe.append(tmp)
			for row in reader:
				tmp = row[0:9]
				tmp.append('#FFFFFF')
				timeframe.append(tmp)
		elif len(tmp) == 7:
			logger.debug('opening new-style timeframe without padding')
			tmp.extend(['', '', '#FFFFFF'])
			timeframe.append(tmp)
			for row in reader:
				if len(row) >= 7: # check every row
					tmp = row[0:7]
					tmp.extend(['', '', '#FFFFFF'])
					timeframe.append(tmp)
				else:
					logger.error("row of wrong length detected!")
					print row
		else:
			logger.debug('timeframe style unsupported')
	return filename
			

def saveTimeframe(filename, timeframe):
	'''save timeframe (new style) to file'''
	if filename is None:
		chooser = gtk.FileChooserDialog(title=None, action=gtk.FILE_CHOOSER_ACTION_SAVE, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK))
		chooser.set_current_folder('.')
		chooser.set_default_response(gtk.RESPONSE_OK)
		response = chooser.run()
		if response == gtk.RESPONSE_OK:
			filename = chooser.get_filename()
			chooser.destroy()
		elif response == gtk.RESPONSE_CANCEL:
			chooser.destroy()
			return None

	with open(filename, 'wb') as ifile:
		writer = csv.writer(ifile, delimiter='\t')
		writer.writerows([[x[i] for i in range(7)] for x in timeframe])
	
	return filename	


