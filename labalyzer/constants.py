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


'''definition of constants for everything'''

COL_COMMENT = 0
COL_EXTERNAL = 1
COL_TIME = 1
COL_DEVICE = 2
COL_CAMITEM = 2
COL_CAMVALUE = 3
COL_VALUE = 3
COL_UNIT = 4
COL_RAMPTYPE = 5
COL_DDSINSTRUCTION = 5
COL_RAMPTIME = 6
COL_VARNAME = 6
COL_ABSTIME = 7
COL_ERROR = 8
COL_COLORHINT = 9


ROWTYPE_UNKNOWN = 0
ROWTYPE_ANALOG = 1
ROWTYPE_DIGITAL = 2
ROWTYPE_DDS = 3
ROWTYPE_PARAMETER = 4
ROWTYPE_CAMERA = 5
ROWTYPE_COMMENT = 6
ROWTYPE_EMPTY = 7

TF_COLNAMES = {0: 'Comment', 1: 'Time', 2: 'Device', 3: 'Value', 4: 'Unit', 5: 'Function', 6: 'Variable', 7: 'Abs. Time', 8: 'Error Code', 9: '', 10: ''}

MODE_DIRECT = 2
MODE_STOPPED = 3
MODE_RUN = 4
MODE_SCAN = 5
MODE_CONTINUOUS = 6

TRIGGER_LENGTH = 5 # 5 mus trigger length for triggering the NI6713 from the DIO64

OS_WINDOWS = 0
OS_LINUX = 1

# DDS Programming
##########################################
DDSCMD_RESET = 0 # reset devices
DDSCMD_FIXED = 2 # fixed frequency
DDSCMD_RAMP = 1 # DDS internal ramp

# define which viewpoint ports belong to which DDS pin
PIN_RST = 2**7
PIN_SCLK = 2**8
PIN_SDIO = [2**15, 2**3, 2**4, 2**5]
PIN_P0 = 2**14
PIN_IOUPDATE = 2**10
PIN_CSB = 2**9

DDS_FREQUENCY = 200*10**6 # 200 MHz, PLL ratio is 20

# end DDS things
#######################################

# camera acquisition modes
ANDOR_KINETIC = 0
ANDOR_FASTKINETIC = 1

# fitting methods
FIT_1DONCE = 0
FIT_1DTWICE = 1
FIT_MOMS2D = 2
FIT_FULL2D = 3

