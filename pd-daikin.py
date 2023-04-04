from gi.repository import GLib
import dbus
from datetime import datetime
from functools import partial
import logging
import urllib.request

# VE specific stuff
from vedbus import VeDbusService, VeDbusItemImport
from settingsdevice import SettingsDevice 


globalsettingstable={
	'otemp_low':['/Settings/Ess3Policy/PD/Daikin/TempOutsideLowerBound',22,17,25],
	'otemp_high':['/Settings/Ess3Policy/PD/Daikin/TempOutsideHigherBound',27,22,35],
	'priority':['/Settings/Ess3Policy/PD/Daikin/Priority',10,0,100],
	'maxpower':['/Settings/Ess3Policy/PD/Daikin/MaxPower',1000,200,3000],
	'mintime':['/Settings/Ess3Policy/PD/Daikin/MinTime',20*60,1*60,60*60],
	'address':['/Settings/Ess3Policy/PD/Daikin/Address','192.168.1.80','',''],
	'debuglevel':["/Settings/Ess3Policy/DebugLevel",30,0,100],
}

class PowerDumpDaikin(object):
	def __init__(self):
		self.logging=logging.getLogger()
		self.logging.setLevel(30)
		self._initDbus()
		self.logging.setLevel(int(self.settings._values['debuglevel']))
		self.lastaction=None

	def _initDbus(self):
		# This is in a seperate def since we might want to ftest the rest of
		# the class and ignore dbus stuff.
		self._dbusservice = VeDbusService("fbo.Ess3Policy.pd.daikin")

		# Initialize connection to settings dbus variables first since we'll
		# mirror some of them on our dbus service.
		self.settings=SettingsDevice(
			_dbus,
			globalsettingstable,
			# This is mainly used to force an update of the mini-stats on the ess3feed submenu link
			eventCallback=self._handleChangedPreferenceDbusVariable
		)

		# Create the management objects, as specified in the ccgx dbus-api document
		self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
		self._dbusservice.add_path('/Mgmt/ProcessVersion', '0.1')
		self._dbusservice.add_path('/Mgmt/Connection', "none")

		# Create the mandatory objects
		self._dbusservice.add_path('/DeviceInstance', 0)
		self._dbusservice.add_path('/ProductId', 145)
		self._dbusservice.add_path('/ProductName', "Ess3Policy.PowerDump.Daikin")
		self._dbusservice.add_path('/FirmwareVersion', 0)
		self._dbusservice.add_path('/HardwareVersion', 0)
		self._dbusservice.add_path('/Connected', 0)

		self._dbusservice.add_path('/PowerDump/MaxPower',0)
		self._dbusservice.add_path('/PowerDump/CurrentPower',0)
		self._dbusservice.add_path('/PowerDump/Priority',self.settings['priority'])
		self._dbusservice.add_path('/PowerDump/MinTime',self.settings['mintime'])
		self._dbusservice.add_path('/PowerDump/Enabled',0,writable=True,onchangecallback=self._handleChangedLocalDbusVariable)

		# Run the service's loop
		GLib.timeout_add(60000, self.run)
		
	def _updateInterestingVariable(self,var,servicename,path,changes):
		self.remotevariables_values[var] = changes['Value']

	def _handleChangedLocalDbusVariable(self, path, value):
		# Something is being updated in our state
		self.logging.info("A foreign process updated '%s' to '%s'" % (path, value))
		if path == "/PowerDump/Enabled":
			return self.switch(bool(value))
		return True # accept the change
	
	def _handleChangedPreferenceDbusVariable(self,key,oldvalue,newvalue):
		# One of the preference variables, we registered for, was updated.
		self.logging.info("Preference variable '%s' was changed: '%s'->'%s'" % (key,str(oldvalue),str(newvalue)))
		if key == 'debuglevel':
			self.logging.setLevel(int(newvalue))
		return True

	def daikinBaseUrl(self):
		url="http://" + self.settings._values['address']
		return url

	def updateDaikinStatus(self):
		with urllib.request.urlopen(self.daikinBaseUrl() + "/aircon/get_sensor_info") as response:
			result = response.read()
			

	def run(self):
		c=self.settings._values # C as in 'constant defined by user, not automatically changing'
		l=self._dbusservice # local variables
		self._dbusservice['/TimeTillCharged']=ttc
		self._dbusservice['/TimeTillDischargedRegular']=ttd
		self._dbusservice['/TimeTillDischargedReserve']=ttdr
		self._dbusservice['/ChargeLeftRegular']=int(cl*10)/10
		self._dbusservice['/ChargeLeftReserve']=int(clr*10)/10
		self._dbusservice['/ChargeMissing']=int(cm*10)/10
		self._dbusservice['/EnoughPv']=int(enough_solar)
		return True
