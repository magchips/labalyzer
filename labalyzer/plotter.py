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

'''cairo interface for plotting things'''

#from matplotlib.figure import Figure
#from matplotlib.axes import Subplot
#from matplotlib.backends.backend_gtk import FigureCanvasGTK

import cairo
import numpy
from math import pi

import gtk

from labalyzer.LabalyzerSettings import settings
from labalyzer.constants import (FIT_1DONCE, FIT_1DTWICE, FIT_FULL2D, FIT_MOMS2D)

from labalyzer_lib.plotter import plotter, fitter

import logging
logger = logging.getLogger('labalyzer')

import Image

cmap_jet = numpy.zeros(shape=(256, 4), dtype=numpy.uint8)
cmap_jet[0:32, 0] = numpy.linspace(128, 255, 32)
cmap_jet[32:96, 0] = 255
cmap_jet[96:160, 0] = numpy.linspace(255, 0, 64)
cmap_jet[32:96, 1] = numpy.linspace(0, 255, 64)
cmap_jet[96:160, 1] = 255
cmap_jet[160:224, 1] = numpy.linspace(255, 0, 64)
cmap_jet[96:160, 2] = numpy.linspace(0, 255, 64)
cmap_jet[160:224, 2] = 255
cmap_jet[224:256, 2] = numpy.linspace(255, 128, 32)

cmap_lv = numpy.zeros(shape=(256, 4), dtype=numpy.uint8)
cmap_lv[0:32, 0] = numpy.linspace(192, 0, 32)
cmap_lv[128:160, 0] = numpy.linspace(0, 255, 32)
cmap_lv[160:256, 0] = 255
cmap_lv[64:96, 1] = numpy.linspace(0, 192, 32)
cmap_lv[96:128, 1] = 192
cmap_lv[128:160, 1] = numpy.linspace(192, 255, 32)
cmap_lv[160:192, 1] = numpy.linspace(255, 128, 32)
cmap_lv[192:224, 1] = numpy.linspace(127, 64, 32)
cmap_lv[224:256, 1] = numpy.linspace(64, 255, 32)
cmap_lv[0:32, 2] = numpy.linspace(192, 0, 32)
cmap_lv[32:64, 2] = numpy.linspace(0, 192, 32)
cmap_lv[64:96, 2] = 192
cmap_lv[96:128, 2] = numpy.linspace(192, 0, 32)
cmap_lv[192:224, 2] = numpy.linspace(0, 64, 32)
cmap_lv[224:256, 2] = numpy.linspace(64, 255, 32)

cmap = cmap_lv

class mainPlotter(plotter):
	'''plotter for main window'''
	def __init__(self, hostWidget):
		plotter.__init__(self, hostWidget)
		
		self.imageSurfaces = [None, None, None, None]
		self.scaledImageSurfaces = [None, None, None, None]
		self.imagePIL = [None, None, None, None]
		self.meanX = None
		self.meanY = None
		self.cutX = None
		self.cutY = None
		self.fitX = None
		self.fitY = None
		self.showFit = False
		self.images = None
		self.selectedSurface = None
		
		self.xscale = 1 # needed to translate button presses back into proper coordinates
		self.yscale = 1
		self.lastButtonPress = None
		self.xoff = 100
		self.yoff = 100
		self.showText = False
		
		self.peakpos = [None, None]
		
		settings.connect('changed', self.settingsChanged)
		self.currentImage = 3

	def draw(self, cr, width, height):
		# pylint: disable=R0914, R0915
		# disable too many local variables, too many statements
		self.xoff = 0.1*width
		self.yoff = 0.1*height

		if self.selectedSurface is not None and self.imageSurfaces[self.selectedSurface] is not None:
			# so there is a picture we want to paint
			childWidth = self.imageSurfaces[self.selectedSurface].get_width()
			childHeight = self.imageSurfaces[self.selectedSurface].get_height()

			xscale = 0.9*width/childWidth
			yscale = 0.9*height/childHeight

			if settings['plot.keepAspect']:
				xscale = min(xscale, yscale)
				yscale = xscale

			if self.xscale != xscale or self.yscale != yscale:
				# scaling changed, so we have to clear all scaled surfaces
				self.scaledImageSurfaces = [None, None, None, None]
				self.xscale = xscale
				self.yscale = yscale

			if self.selectedSurface is not None and self.scaledImageSurfaces[self.selectedSurface] is None:
				# scaled surface doesn't exist yet, so we should create it for the new size and rescale
				self.scaledImageSurfaces[self.selectedSurface] = cairo.ImageSurface(cairo.FORMAT_RGB24, int(childWidth*xscale), int(childHeight*yscale))
				cr2 = cairo.Context(self.scaledImageSurfaces[self.selectedSurface])
				cr2.save()
				cr2.scale(self.xscale, self.yscale)
				cr2.set_source_surface(self.imageSurfaces[self.selectedSurface])
				cr2.paint()
				cr2.restore()

			cr.set_source_surface(self.scaledImageSurfaces[self.selectedSurface], self.xoff, self.yoff)
			cr.rectangle(self.xoff, self.yoff, int(childWidth*xscale), int(childHeight*yscale))
			cr.fill()
			
			
			# calculate axis scales
			if self.showFit:
				yMin = min([min(self.meanY), min(self.fitY), min(self.cutY)])
				yMax = max([max(self.meanY), max(self.fitY), max(self.cutY)])
			else:
				yMin = min([min(self.meanY), min(self.cutY)])
				yMax = max([max(self.meanY), max(self.cutY)])
			# mean parallel to x axis
			cr.set_source_rgb(0, 0, 0)
			cr.rectangle(self.xoff, 0, int(childWidth*xscale), self.yoff)
			cr.fill()
			self.plotGraph(None, self.meanX, cr, [self.xoff, 0, childWidth*xscale, self.yoff], (1, 0, 0), yscale=[yMin, yMax])
			self.plotGraph(None, self.cutX, cr, [self.xoff, 0, childWidth*xscale, self.yoff], (0, 0, 1), yscale=[yMin, yMax])
			if self.showFit:
				self.plotGraph(None, self.fitX, cr, [self.xoff, 0, childWidth*xscale, self.yoff], (1, 1, 1), yscale=[yMin, yMax])
			# add labels
			cr.set_source_rgb(0.8, 0.8, 0.8)
			cr.select_font_face("Ubuntu", cairo.FONT_SLANT_NORMAL)
			cr.set_font_size(10)
			cr.move_to(self.xoff + 10, 20)
			cr.show_text(str(round(yMax, 1)))
			cr.move_to(self.xoff + 10, self.yoff - 10)
			cr.show_text(str(round(yMin, 1)))
			
			
			# mean parallel to y axis
			cr.set_source_rgb(0, 0, 0)
			cr.rectangle(0, self.yoff, self.xoff, int(childHeight*yscale))
			cr.fill()
			self.plotGraph(self.meanY, -numpy.arange(len(self.meanY)), cr, [0, self.yoff, self.xoff, childHeight*yscale], (1, 0, 0), xscale=[yMax, yMin])
			self.plotGraph(self.cutY, -numpy.arange(len(self.cutY)), cr, [0, self.yoff, self.xoff, childHeight*yscale], (0, 0, 1), xscale=[yMax, yMin])
			if self.showFit:
				self.plotGraph(self.fitY, -numpy.arange(len(self.fitY)), cr, [0, self.yoff, self.xoff, childHeight*yscale], (1, 1, 1), xscale=[yMax, yMin])
			# add labels
			cr.set_source_rgb(0.8, 0.8, 0.8)
			cr.select_font_face("Ubuntu", cairo.FONT_SLANT_NORMAL)
			cr.set_font_size(10)
			cr.move_to(10, self.yoff + 20)
			cr.show_text(str(round(yMax, 1)))
			cr.move_to(self.xoff - 10 - cr.text_extents(str(round(yMin, 1)))[2], self.yoff + 20)
			cr.show_text(str(round(yMin, 1)))
			
			
		if settings['plot.showCursor']:
			xpos = settings['plot.cursorPos'][0]*self.xscale + self.xoff
			ypos = settings['plot.cursorPos'][1]*self.yscale + self.yoff
			cr.set_source_rgb(1, 0, 0)
			cr.move_to(xpos - 20, ypos) # show cursor position
			cr.line_to(xpos + 20, ypos)
			cr.move_to(xpos, ypos - 20)
			cr.line_to(xpos, ypos + 20)
			if self.peakpos[0] is not None: # show position of fitted peak
				cr.new_sub_path()
				cr.arc(self.peakpos[0]*self.xscale + self.xoff, self.peakpos[1]*self.yscale + self.yoff, 5, 0.0, 2*pi)
			cr.stroke()
			if settings['plot.ROI'] is not None:
				x0 = settings['plot.ROI'][0]*self.xscale + self.xoff
				x1 = settings['plot.ROI'][2]*self.xscale + self.xoff
				y0 = settings['plot.ROI'][1]*self.yscale + self.yoff
				y1 = settings['plot.ROI'][3]*self.yscale + self.yoff
				cr.set_source_rgb(0, 1, 0)
				cr.move_to(x0, y0)
				cr.line_to(x0, y1)
				cr.line_to(x1, y1)
				cr.line_to(x1, y0)
				cr.line_to(x0, y0)
				cr.stroke()
				

		if self.showText:
			# also show cursor position only when cursor is visible
			cr.move_to(width-170, height-20)
			cr.set_source_rgb(0, 0, 0)
			cr.select_font_face("Ubuntu", cairo.FONT_SLANT_NORMAL)
			cr.set_font_size(16)
			cr.show_text("cursor=(" + str(round(settings['plot.cursorPos'][0], 1)) + ", " + str(round(settings['plot.cursorPos'][1], 1)) + ')')
			


	def setImages(self, images):
		'''takes an array of 4 images, dark, light, absorption and OD
		and just saves them for us;
		 also invalidates all the cairo surfaces created before'''
		self.images = images
		for i in range(4):
			if self.imageSurfaces[i] is not None:
				self.imageSurfaces[i].finish()
#				self.imageSurfaces[i].destroy() # no need/not possible to call destroy in python?
			if self.scaledImageSurfaces[i] is not None:
				self.scaledImageSurfaces[i].finish()
#				self.scaledImageSurfaces[i].destroy()
		self.imageSurfaces = [None, None, None, None] # basically invalidates the old surfaces 
		self.scaledImageSurfaces = [None, None, None, None]
		self.fitX = None # also invalidate old fits, etc.
		self.fitY = None
		self.cutX = None
		self.cutY = None
		self.meanX = None
		self.meanY = None
		
		self.showImage(self.currentImage)

	def getImageAsPIL(self):
		return self.imagePIL[self.currentImage]
		
	def invalidateImage(self, imageNumber):
		'''invalidate a given image'''
		if self.imageSurfaces[imageNumber] is not None:
			self.imageSurfaces[imageNumber].finish()
			self.imageSurfaces[imageNumber] = None
		if self.scaledImageSurfaces[imageNumber] is not None:
			self.scaledImageSurfaces[imageNumber].finish()
			self.scaledImageSurfaces[imageNumber] = None

	def showImage(self, imageNumber):
		'''creates a new surface for the image in question, if necessary.
		updates which image to show and forces a redraw.'''
		if self.images is not None: # so images have been set!
			if self.imageSurfaces[imageNumber] is None: # need to recreate it, changed since last time it was shown
				# main abs image
				image = self.images[imageNumber]
				maxval = image.max()
				minval = image.min()
				width, height = image.shape
				if imageNumber == 3: # OD image, special case
					minval = -settings['plot.negFrac']*settings['plot.maxOD']
					image = numpy.where(image>settings['plot.maxOD'] + minval, settings['plot.maxOD'] + minval, image)
					image = numpy.where(image<minval, minval, image)
					image = numpy.rint((image-minval)*255./settings['plot.maxOD']).astype(numpy.uint8) # rint = round to nearest integer
				else:
					image = numpy.rint((image-minval)*255./maxval).astype(numpy.uint8)
				self.imagePIL[imageNumber] = Image.fromarray(cmap[image])
				self.imageSurfaces[imageNumber] = cairo.ImageSurface.create_for_data(cmap[image], cairo.FORMAT_RGB24, height, width)
			self.meanX = numpy.mean(self.images[imageNumber], 0)
			self.meanY = numpy.mean(self.images[imageNumber], 1)
			self.cutX = numpy.mean(self.images[imageNumber][settings['plot.cursorPos'][1] - 5:settings['plot.cursorPos'][1] + 5, :], 0)
			self.cutY = numpy.mean(self.images[imageNumber][:, settings['plot.cursorPos'][0] - 5:settings['plot.cursorPos'][0] + 5], 1)
			self.selectedSurface = imageNumber
			if imageNumber == 3 and self.fitX is not None and self.fitY is not None:
				self.showFit = True
			else:
				self.showFit = False
		self.currentImage = imageNumber
		self.redraw()

	
	def button_press(self, _widget, event):
		'''mouse handling'''
		# no redraw necessary, as we change settings, which calls a redraw automatically
		if event.type == gtk.gdk._2BUTTON_PRESS:
			settings['plot.cursorPos'] = [(event.x - self.xoff)/self.xscale, (event.y - self.yoff)/self.yscale]
		elif event.type == gtk.gdk.BUTTON_PRESS:
			self.lastButtonPress = [(event.x - self.xoff)/self.xscale, (event.y - self.yoff)/self.yscale]
		elif event.type == gtk.gdk.BUTTON_RELEASE:
			xpos = (event.x - self.xoff)/self.xscale
			ypos = (event.y - self.yoff)/self.yscale
			if abs(xpos - self.lastButtonPress[0]) > 5 or abs(ypos - self.lastButtonPress[1]) > 5:
				settings['plot.ROI'] = [self.lastButtonPress[0], self.lastButtonPress[1], xpos, ypos]

	def pointer_enter(self, _widget, _event, enter):
		'''mouse handling'''
		self.showText = enter
		self.redraw()

	def getImageInfo(self, _offset=True):
		'''fitting'''
		def cutAndFit(self, cutPosition, cutWidth):
			''' helper function for 1D fits'''
			if len(image) < cutWidth or len(image[0]) < cutWidth:
				raise RuntimeError("Image Size too small for fitting")
			if cutPosition[1]-cutWidth < 0:
				cutPosition[1] = cutWidth
			if cutPosition[1]+cutWidth > len(image):
				cutPosition[1] = len(image) - cutWidth
			if cutPosition[0]-cutWidth < 0:
				cutPosition[0] = cutWidth + 1
			if cutPosition[0]+cutWidth > len(image[0]):
				cutPosition[0] = len(image[0]) - cutWidth
			
			if allowOffset:
				bounds = [[0, 100], [-10000, 10000], [0, 10000], [-1, 1]]
			else:
				bounds = [[0, 100], [-10000, 10000], [0, 10000], [0, 0]]
			
			cutX = numpy.mean(image[cutPosition[1] - cutWidth:cutPosition[1] + cutWidth, :], 0)
			cutY = numpy.mean(image[:, cutPosition[0] - cutWidth:cutPosition[0] + cutWidth], 1)
			momsX = ft.moments1D(cutX)
			parmsX = ft.fit1D(range(len(cutX)), cutX, [abs(momsX[0]), cutPosition[0], momsX[2], 0], eval(settings['fit.gauss']), bounds)
			self.fitX = eval(settings['fit.gauss'])(parmsX, numpy.arange(cutX.size))
			momsY = ft.moments1D(cutY)
			parmsY = ft.fit1D(range(len(cutY)), cutY, [abs(momsY[0]), cutPosition[1], momsY[2], 0], eval(settings['fit.gauss']), bounds)
			self.fitY = eval(settings['fit.gauss'])(parmsY, numpy.arange(cutY.size))
			return parmsX, parmsY
		
		# we only fit the ND images
		# TODO: fit or don't fit offset
		if self.images[3] is None:
			return [[0], [0]]
		ft = fitter()
		image = self.images[3]
		
		fitMethod = settings['main.fitMethod']
		allowOffset = settings['fit.allowOffset']
		
		if fitMethod == FIT_1DONCE or fitMethod == FIT_1DTWICE:
			parmsX, parmsY = cutAndFit(self, settings['plot.cursorPos'], 5)
			if fitMethod == FIT_1DTWICE:
				parmsX, parmsY = cutAndFit(self, [parmsX[1], parmsY[1]], 5)
		elif fitMethod == FIT_FULL2D:
			logger.warn('Fitting method FULL2D not yet implemented!')
			return None
		elif fitMethod == FIT_MOMS2D:
			## fit method using 2D moments but 1D fits
			# this method ignores the cursor position completely!
			# 2D moments are only used to determine peak position, not 
			# widths or anything else
			moms2D = ft.moments2D(image)
			xpos = moms2D[2]
			ypos = moms2D[1]
			parmsX, parmsY = cutAndFit(self, [xpos, ypos], 5)
		
		roi = settings['plot.ROI']
		if roi is not None:
			for i in [0, 1]: # lots of stupid checks to make sure we're in the current FOV
				if roi[i] < 0:
					roi[i] = 0
			for i in [2, 3]:
				if roi[i] < 1:
					roi[i] = 1
			if roi[1] > len(image)-1:
				roi[1] = len(image)-1
			if roi[3] > len(image):
				roi[3] = len(image)
			if roi[0] > len(image[0])-1:
				roi[0] = len(image[0])-1
			if roi[2] > len(image[0]):
				roi[2] = len(image[0])					
			settings['plot.ROI'] = roi		
			mean = numpy.mean(image[settings['plot.ROI'][1]:settings['plot.ROI'][3], settings['plot.ROI'][0]:settings['plot.ROI'][2]])
			NSum = numpy.sum(image[settings['plot.ROI'][1]:settings['plot.ROI'][3], settings['plot.ROI'][0]:settings['plot.ROI'][2]])*(settings['andor.pxSize']/settings['physics.magnification'])**2/(2.9*10**(-13.))
		else: 
			mean = 0
			NSum = 0
		NInt = parmsX[2]*parmsY[2]*(2*3.1415)**(2./2)*(settings['andor.pxSize']/settings['physics.magnification'])**2/(2.9*10**(-13.))*(parmsX[0]+parmsY[0])/2
		Temp = (parmsX[2]*parmsY[2]*(settings['andor.pxSize']/settings['physics.magnification'])**2*(1-1/((settings['physics.trapfreq']*2*3.14*settings['physics.timeofflight']*10**(-3))**2))*(87*1.66*10**(-27.)))/(2*(1.38*10**(-23.))*(settings['physics.timeofflight']*10**(-3))**2)
		#n0 = NInt/((2*3.14)**(3./2)*parmsX[2]*parmsY[2]**2*(settings['andor.pxSize']/settings['physics.magnification'])**3)
		n0 = NInt*((87*1.66*10**(-27.))/(2*3.14*(1.38*10**(-23.))*Temp))**(3./2)*(settings['physics.trapfreq']*2*3.14)**3
		Phi0 = NInt*((1.0546*10**(-34.))*settings['physics.trapfreq']*2*3.14/((1.38*10**(-23.))*Temp))**3
		Temp *= 10**6
		self.peakpos = [parmsX[1], parmsY[1]]
		
		self.showImage(self.currentImage) # needed to update plot to show fit
		return parmsX, parmsY, [mean, NSum, NInt, Temp, n0, Phi0]

	def settingsChanged(self, _widget, keys):
		'''listener for settings change events'''
		if 'plot.maxOD' in keys:
			self.invalidateImage(3)
			self.showImage(self.selectedSurface)
		for k in keys:
			if k.startswith('plot.'):
				self.redraw()
				return

from types import ListType
		
class functionPlotter(plotter):
	'''plotter for a single or multiple 1D functions, for data logger'''
	# Draw in response to an expose-event
	__gsignals__ = { "expose-event": "override" }
	def __init__(self, host):
		plotter.__init__(self, host)
		self.x = None
		self.xDark = None
		self.ys = None
		self.leftMargin = 0.1
		self.bottomMargin = 0.1
		self.maxLabelsX = 10
		self.maxLabelsY = 10
		
		
	def draw(self, cr, width, height):
		# calculate graph area (excluding axis labels etc)
		xoff = width*self.leftMargin
		yoff = height*self.bottomMargin
		gWidth = width - xoff
		gHeight = height - yoff
		
		# Fill the background with white
		cr.set_source_rgb(1, 1, 1)
		cr.rectangle(0, 0, width, height)
		cr.fill()
		
		# Fill the graph background with gray
		cr.set_source_rgb(0.5, 0.5, 0.5)
		cr.rectangle(xoff, 0, gWidth, gHeight)
		cr.fill()
		
		if self.ys == None or len(self.ys[0]) < 2:
			return
		
		if self.xDark is not None:
			x = self.xDark
		else:
			x = self.x
		
		yMin = 0.95*min(min(self.ys))
		yMax = 1.05*max(max(self.ys)) # add some borders
		xMin = min(x)
		xMax = max(x)
		
		if self.ys is not None:
			for i, y in enumerate(self.ys):
				col = [1.*i/len(self.ys), 1.*(len(self.ys) - i)/len(self.ys), 1]
				self.plotGraph(x, y, cr, [xoff, 0, gWidth, gHeight], col, xscale=[xMin, xMax], yscale = [yMin, yMax])
		
		cr.set_source_rgb(0, 0, 0)
		cr.select_font_face("Ubuntu", cairo.FONT_SLANT_NORMAL)
		cr.set_font_size(16)
		
		
		# add labels
		for i in range(self.maxLabelsY):
			text = str(round(yMin + 1.*(yMax - yMin)/(self.maxLabelsY - 1)*i, 2))
			width, height = cr.text_extents(text)[2:4]
			cr.move_to(xoff - width - 5, gHeight - gHeight/(self.maxLabelsY - 1)*i + height/2)
			cr.show_text(text)
		
		nLabels = min(self.maxLabelsX, len(x)) - 1
		dx = 1.*(xMax - xMin)/nLabels
		lastPoint = xMin - dx
		for xPoint in x:
			if xPoint - lastPoint >= dx:
				text = str(round(xPoint, 2))
				width, height = cr.text_extents(text)[2:4]
				cr.move_to(xoff + (xPoint - xMin)*gWidth/(xMax - xMin) - width/2, gHeight + height + 5)
				cr.show_text(text)
				lastPoint = xPoint

	def setData(self, x, ys, xDark=None):
		'''set data to be shown'''
		self.x = x
		self.xDark = xDark
		if type(ys[0]) is not ListType:
			self.ys = [ys]
		else:
			self.ys = ys
		self.redraw()
		
	def button_press(self, _widget, event):
		'''mouse handling'''
		pass
		
		
	def pointer_enter(self, _widget, _event, enter):
		'''mouse handling'''
		pass

