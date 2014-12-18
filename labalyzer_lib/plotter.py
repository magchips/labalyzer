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

"""Helpers for plotting."""

import gtk
from scipy import optimize
import numpy


class fitter:
	'''fit data'''
	def __init__(self):
		pass
	
	@staticmethod
	def gaussian2D(height, center_x, center_y, width_x, width_y):
		'''Returns a gaussian function with the given parameters'''
		width_x = float(width_x)
		width_y = float(width_y)
		return lambda x, y: height*numpy.exp(-(((center_x-x)/width_x)**2+((center_y-y)/width_y)**2)/2)

	@staticmethod
	def moments2D(data):
		'''Returns (height, x, y, width_x, width_y)
		the gaussian parameters of a 2D distribution by calculating its
		moments'''
		total = data.sum()
		X, Y = numpy.indices(data.shape)
		x = (X*data).sum()/total
		y = (Y*data).sum()/total
		if x < 0: x = 0
		if y < 0: y = 0
		if x >= data.shape[0]: x = data.shape[0] - 1
		if y >= data.shape[1]: y = data.shape[1] - 1
		col = data[:, int(y)]
		width_x = numpy.sqrt(abs((numpy.arange(col.size)-y)**2*col).sum()/col.sum())
		row = data[int(x), :]
		width_y = numpy.sqrt(abs((numpy.arange(row.size)-x)**2*row).sum()/row.sum())
		height = data.max()
		return height, x, y, width_x, width_y

	@staticmethod
	def fitGauss2D(data):
		'''Returns (height, x, y, width_x, width_y)
		the gaussian parameters of a 2D distribution found by a fit'''
		params = fitter.moments2D(data)
		errorfunction = lambda p: numpy.ravel(fitter.gaussian2D(*p)(*numpy.indices(data.shape)) - data)
		p, _ = optimize.leastsq(errorfunction, params)
		return p

#	@staticmethod
#	def gaussian1D(data, parms):
#		'''returns 1D gaussian evaluated at data for parms'''
#		return parms[0]*numpy.exp(-(data-parms[1])**2/(2*parms[2]**2)) + parms[3]

	@staticmethod
	def moments1D(data):
		'''calculate moments of 1D gaussian'''
		X = numpy.arange(data.size)
		x = sum(X*data)/sum(data)
		width = numpy.sqrt(abs(sum((X-x)**2*data)/sum(data)))
		mx = data.max()
		return [mx, x, width]

#	@staticmethod
#	def fitGauss1D(data, parms):
#		'''fit 1D gaussian to data, using initial values parms'''
#		ffunc = lambda p, x: p[0]*numpy.exp(-(x-p[1])**2/(2*p[2]**2)) + p[3]
#		errfunc = lambda p, x, y: sum((ffunc(p, x) - y)**2)
#		return optimize.fmin_slsqp(errfunc, parms, args=(numpy.arange(data.size), data), bounds = [(min(data) - max(data), max(data) - min(data)), (parms[1]*0.5, parms[1]*1.5), (0, 1000), (-1, 1)])
		
	@staticmethod
	def fit1D(x, y, parms, function, bounds=None):
		errfunc = lambda p, x, y: sum((function(p, x) - y)**2)
		if bounds == None:
			bounds = [(min(y) - max(y), max(y) - min(y)), (parms[1]*0.5, parms[1]*1.5), (0, 1000), (-1, 1)]
		return optimize.fmin_slsqp(errfunc, parms, args=(x, y), bounds=bounds, iprint=0)

class plotter(gtk.DrawingArea):
	'''plotter base class'''
	# Draw in response to an expose-event
	__gsignals__ = { "expose-event": "override" }
	def __init__(self, hostWidget):
		gtk.DrawingArea.__init__(self)
		self.hostWidget = hostWidget
		self.show()
		self.hostWidget.pack_start(self)
		
		self.add_events(gtk.gdk.BUTTON_PRESS_MASK  | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.ENTER_NOTIFY_MASK | gtk.gdk.LEAVE_NOTIFY_MASK)
		self.connect("button-press-event", self.button_press)
		self.connect("button-release-event", self.button_press)
		self.connect("leave-notify-event", self.pointer_enter, False)
		self.connect("enter-notify-event", self.pointer_enter, True)
		
	# Handle the expose-event by drawing
	def do_expose_event(self, event):
		'''redraw canvas'''
		# Create the cairo context
		# TODO: maybe this should not be done every time?!
		cr = self.window.cairo_create()

		# Restrict Cairo to the exposed area; avoid extra work
		cr.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
		cr.clip()
		self.draw(cr, *self.window.get_size())
		
	def draw(self, cr, width, height):
		'''draw background'''
		# Fill the background with gray
		cr.set_source_rgb(0.5, 0.5, 0.5)
		cr.rectangle(0, 0, width, height)
		cr.fill()
		
	def redraw(self, region=None):
		'''force redraw'''
		if region is None:
			self.alloc = self.get_allocation()
			region = gtk.gdk.Rectangle(0, 0, int(self.alloc.width), int(self.alloc.height))
		if self.window:
			self.window.invalidate_rect(region, True)
	
#	def button_press(self, _widget, event):
#		pass
#	
#	def pointer_enter(self, _widget, _event, _enter=None):
#		pass
		
	def plotGraph(self, xdata, ydata, cr, area, color=None, xscale=None, yscale=None):
		'''plot graph'''
		
		startPoint = area[0:2]
		size = area[2:4]
				
		if xdata == None:
			xdata = range(len(ydata))
		
		if color == None:
			color = [1, 1, 1]
		
		if yscale is None:
			yMax = max(ydata)
			yMin = min(ydata)
		else:
			yMin, yMax = yscale
		if yMin == yMax:
			return # should throw warning
		dy = 1.*size[1]/(yMax - yMin)
		
		if xscale is None:
			xMax = max(xdata)
			xMin = min(xdata)
		else:
			xMin, xMax = xscale
		if xMin == xMax:
			return #should throw warning
		dx = 1.*size[0]/(xMax - xMin)
		
		cr.set_source_rgb(*color)
		
		cr.move_to(startPoint[0], startPoint[1] + size[1] - dy*(ydata[0] - yMin))
		for i, y in enumerate(ydata):
			cr.line_to(startPoint[0] + dx*(xdata[i] - xMin), startPoint[1] + size[1] - dy*(y - yMin))
		cr.stroke()

