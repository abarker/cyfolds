'''
Yahoo-Groups-Archiver Copyright 2015, 2017, 2018 Andrew Ferguson and others

YahooGroups-Archiver, a simple python script that allows for all
messages in a public Yahoo Group to be archived.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

cookie_T = 'COOKIE_T_DATA_GOES_HERE'
cookie_Y = 'COOKIE_Y_DATA_GOES_HERE'

import json #required for reading various JSON attributes from the content

# BUG FROM USING TABS MIXED WITH SPACE, but tabs would also cause bug...

def archive_group(groupName, mode="update"):
	if mode == "retry":
		min = 1
	elif mode == "update":
        pass


