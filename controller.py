from gi.repository import GLib
import argparse
import dbus
from datetime import datetime
from functools import partial
import logging

# VE specific stuff
from vedbus import VeDbusService, VeDbusItemImport
from settingsdevice import SettingsDevice 

id2state={
	0:'init',
	1:'ess2_backoff',
	2:'ess3_backoff',
	3:'low_shutdown',
	4:'force_recharge',
	5:'bulk_recharge',
	6:'discharge',
	7:'keep',
	8:'charge',
	9:'feedin',
	10:'dump',
	11:'high_shutdown',
	12:'unknown',
	13:'scope_backoff',
}
state2id={v: k for k, v in id2state.items()}

id2policy={
	0:'ess3_backoff',
	1:'solar_ups',
	2:'self_consumption',
	3:'bulk_recharge', # Charge batteries at all cost until soc_high
}
policy2id={v: k for k, v in id2policy.items()}

# remove via: dbus -y com.victronenergy.settings /Settings RemoveSettings '%["Ess3Feed/..."]'
globalsettingstable={
	'soc_em_low':['/Settings/Ess3Policy/SocEmergencyLow',12,5,99],
	'soc_frs_lowstart':['/Settings/Ess3Policy/SocForceRechargeLowStart',15,5,55],
	'soc_frs_highstop':['/Settings/Ess3Policy/SocForceRechargeHighStop',18,5,55],
	'soc_dis_lowstart':['/Settings/Ess3Policy/SocDischargeLowStart',30,10,99],
	'soc_feed_lowstart':['/Settings/Ess3Policy/SocFeedLowStart',55,10,99],
	'enable_pd':['/Settings/Ess3Policy/EnablePowerDump',0,0,1],
	'enable_feedin':['/Settings/Ess3Policy/EnableFeed',1,0,1],
	'soc_high':['/Settings/Ess3Policy/SocHigh',92.1,30.0,100.0],
	'soc_em_high':['/Settings/Ess3Policy/SocEmergencyHigh',99.0,30.0,100.0],
	'enable_high_shutdown':['/Settings/Ess3Policy/EnableHighShutdown',0,0,1], #
	'charge_full_bat':['/Settings/Ess3Policy/BatteryAmpereHours',200,1,10000],
	'current_frs_charge':["/Settings/Ess3Policy/CurrentForceRecharge",2,1,200],
	'current_bat_limit':["/Settings/Ess3Policy/CurrentBatteryBulkRecharge",50,1,200],
	'power_feedin_max':['/Settings/CGwacs/MaxFeedInPower',4800,0,300000], # Stolen from Hub4 settings
	'current_acin_max_bulk_recharge':["/Settings/Ess3Policy/CurrentAcINMaxBulkRecharge",1,1,32],
	'power_pd':['/Settings/Ess3Policy/PowerPowerDump',1000,100,3000],
	'ess_mode':['/Settings/CGwacs/Hub4Mode',3,1,3],
	'policy':['/Settings/Ess3Policy/Policy',1,0,3],
	'dvcc':['/Settings/Services/Bol',1,0,1],
	'debuglevel':["/Settings/Ess3Policy/DebugLevel",30,0,100],
}
vebus="com.victronenergy.vebus"
battery="com.victronenergy.battery"
remotevariables={
	'grid/voltage/l1':[vebus,'/Ac/ActiveIn/L1/V',3,'int16',0.1],
	'grid/voltage/l2':[vebus,'/Ac/ActiveIn/L2/V',4,'int16',0.1],
	'grid/voltage/l3':[vebus,'/Ac/ActiveIn/L3/V',5,'int16',0.1],
	'grid/current/l1':[vebus,'/Ac/ActiveIn/L1/I',6,'int16',0.1],
	'grid/current/l2':[vebus,'/Ac/ActiveIn/L2/I',7,'int16',0.1],
	'grid/current/l3':[vebus,'/Ac/ActiveIn/L3/I',8,'int16',0.1],
	'grid/power/l1':[vebus,'/Ac/ActiveIn/L1/P',12,'int16',0.1],
	'grid/power/l2':[vebus,'/Ac/ActiveIn/L2/P',13,'int16',0.1],
	'grid/power/l3':[vebus,'/Ac/ActiveIn/L3/P',14,'int16',0.1],
	'grid/current/max':[vebus,'/Ac/ActiveIn/CurrentLimit',22,'int16',0.1],
	'acout/power/l1':[vebus,'/Ac/Out/L1/P',23,'int16',10],
	'acout/power/l2':[vebus,'/Ac/Out/L2/P',24,'int16',10],
	'acout/power/l3':[vebus,'/Ac/Out/L3/P',25,'int16',10],
	'soc':[battery,'/Soc',266,'uint16',0.1],
	'solar/power':['com.victronenergy.system','/Dc/Pv/Power',850,'uint16',1],
	'3grid/setpoint/l1':[vebus,'/Hub4/L1/AcPowerSetpoint',37,'int16',1],
	'3grid/setpoint/l2':[vebus,'/Hub4/L2/AcPowerSetpoint',40,'int16',1],
	'3grid/setpoint/l3':[vebus,'/Hub4/L3/AcPowerSetpoint',41,'int16',1],
	'3charger/disabled':[vebus,'/Hub4/DisableCharge',38,'uint16',1], # 0 or 1
	'3inverter/disabled':[vebus,'/Hub4/DisableFeedIn',39,'uint16',1], # 0 or 1
	'3grid/feedin/excess':[vebus,'/Hub4/DoNotFeedInOvervoltage',65,'uint16',1], # 0 or 1
	'battery/voltage':[battery,'/Dc/0/Voltage',259,'int16',0.01],
	'battery/current':[battery,'/Dc/0/Current',261,'int16',0.1],
}

def trueOrText(condition,text):
	if condition:
		return True
	else:
		return text

def checkMdiff(mdiff,minimum):
	return trueOrText(mdiff > minimum,"mdiff<" + str(minimum))

def secondsToHHMM(seconds):
	hours=seconds // 3600
	minutes=(seconds-(hours*3600)) // 60
	return str(hours).zfill(2) + ":" + str(minutes).zfill(2)

class PowerDumpClient(object):
	def __init__(self,id):
		self.id=id
		

class Controller(object):
	def __init__(self):
		self.logging=logging.getLogger()
		self.logging.setLevel(30)
		# STDOUT-output of the internal state
		self._statwaitmax=10
		self._statwait=0

		## Helper attributes for testStateTransitionConstraints()
		# They'll usually hint that a state transition is to be done
		# faster since the user might have adjusted some detail
		# or even the policy.
		self.preferenceUpdateSinceLastState=True
		self.policyUpdateSinceLastState=True
		self.state_mtime=datetime.now()

		self.state='init'
		self.policy='ess3_backoff'
		self._initDbus()
		self.logging.setLevel(int(self.settings._values['debuglevel']))
		self.powerdumps=dict()
		self.lasttransitionstring=None

	def updatePowerDumps(self):
		powerdumps=[pd for pd in _dbus.list_names() if bus.startswith('fbo.Ess3Policy.pd')]
		for pd in powerdumps:
			if not (pd in self.powerdumps):
				self.powerdumps[pd]=PowerDumpClient(pd)
		for pd in self.powerdumps:
			if not pd in powerdumps:
				del self.powerdumps[pd]

	def _initDbus(self):
		# This is in a seperate def since we might want to ftest the rest of
		# the class and ignore dbus stuff.
		self._dbusservice = VeDbusService("fbo.Ess3Policy.Controller")
		_dbus=dbus.SystemBus()
		vebusses=[bus for bus in _dbus.list_names() if bus.startswith('com.victronenergy.vebus')]
		if len(vebusses) != 1:
			self.logging.error("Not exactly one vebus dbus service found")
			raise Exception("Not exactly one vebus dbus service found")
		self.logging.info("Using vebus dbus service '%s'" % vebusses[0])
		batteries=[bus for bus in _dbus.list_names() if bus.startswith('com.victronenergy.battery')]
		if len(batteries) != 1:
			self.logging.error("Not exactly one battery dbus service found")
			raise Exception("Not exactly one battery dbus service found")
		self.logging.info("Using bms dbus service '%s'" % batteries[0])
		for k,v in remotevariables.items():
			if v[0] == "com.victronenergy.vebus":
				v[0]=vebusses[0]
			elif v[0] == "com.victronenergy.battery":
				v[0]=batteries[0]

		# Create the management objects, as specified in the ccgx dbus-api document
		self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
		self._dbusservice.add_path('/Mgmt/ProcessVersion', '0.1')
		self._dbusservice.add_path('/Mgmt/Connection', "none")

		# Create the mandatory objects
		self._dbusservice.add_path('/DeviceInstance', 0)
		self._dbusservice.add_path('/ProductId', 144)
		self._dbusservice.add_path('/ProductName', "Ess3Policy.Controller")
		self._dbusservice.add_path('/FirmwareVersion', 0)
		self._dbusservice.add_path('/HardwareVersion', 0)
		self._dbusservice.add_path('/Connected', 1)

		self._dbusservice.add_path('/State',0,
			gettextcallback=lambda p,v: id2state[v]
		)
		self._dbusservice.add_path('/ChargeLeftReserve',0,
			gettextcallback=lambda p,v: str(int(v*10)/10) + "kWh"
		)
		self._dbusservice.add_path('/ChargeLeftRegular',0,
			gettextcallback=lambda p,v: (str(int(v*10)/10) + "kWh") if (self.policy in ['self_consumption','bulk_recharge']) else '-'
		)
		self._dbusservice.add_path('/ChargeMissing',0,
			gettextcallback=lambda p,v: str(int(v*10)/10) + "kWh"
		)
		self._dbusservice.add_path('/TimeTillDischargedReserve',0,
			gettextcallback=lambda p,v: secondsToHHMM(v)
		)
		self._dbusservice.add_path('/TimeTillDischargedRegular',0,
			gettextcallback=lambda p,v: secondsToHHMM(v) if (self.policy in ['self_consumption','bulk_recharge']) else '-'
		)
		self._dbusservice.add_path('/TimeTillCharged',0,
			gettextcallback=lambda p,v: secondsToHHMM(v) if (self.state in ['charge','bulk_recharge']) else '-'
		)
		self._dbusservice.add_path('/EnoughPv',0)

		# Initialize connection to settings dbus variables
		self.settings=SettingsDevice(
			_dbus,
			globalsettingstable,
			# This is mainly used to force an update of the mini-stats on the ess3feed submenu link
			eventCallback=self._handleChangedPreferenceDbusVariable
		)
		self.policy=id2policy[self.settings._values['policy']]

		# Local dbus variables
		self.remotevariables_busitems={}
		self.remotevariables_values={}
		for var in remotevariables.keys():
			busitem = VeDbusItemImport(
				_dbus,
				remotevariables[var][0],
				remotevariables[var][1],
				eventCallback=partial(self._updateInterestingVariable,var),
				createsignal=True
			)
			self.remotevariables_busitems[var]=busitem
			self.remotevariables_values[var]=busitem.get_value()

		# Run the ESS 3 loop
		GLib.timeout_add(2000, self.run)
		
	def _updateInterestingVariable(self,var,servicename,path,changes):
		self.remotevariables_values[var] = changes['Value']

	def _handleChangedLocalDbusVariable(self, path, value):
		# Something is being updated in our state
		self.logging.info("A foreign process updated '%s' to '%s'" % (path, value))
		return True # accept the change
	
	def _handleChangedPreferenceDbusVariable(self,key,oldvalue,newvalue):
		# One of the preference variables, we registered for, was updated.
		self.logging.info("Preference variable '%s' was changed: '%s'->'%s'" % (key,str(oldvalue),str(newvalue)))
		self._statwait=0
		self.preferenceUpdateSinceLastState=True
		if key == 'policy':
			self.policyUpdateSinceLastState=True
		if key == 'debuglevel':
			self.logging.setLevel(int(newvalue))
		return True

	def _transitionerror(self,newstate):
		text="State transition from '" + self.state + "' to '" + newstate + "' should not happen."
		self.logging.error(text)
		return True		

	def testStateTransitionConstraints(self,c,d,e,newstate):
		state=self.state
		if newstate == state:
			return True
		timedelta=datetime.now()-self.state_mtime
		mdiff=timedelta.total_seconds()

		if newstate in ['scope_backoff']:
			return True
		if newstate in ['high_shutdown','unknown']:
			return checkMdiff(mdiff,30)

		if state in ['init','ess2_backoff','ess3_backoff']:
			if newstate == 'shutdown':
				return checkMdiff(mdiff,120)
			else:
				return True
		elif state == 'discharge':
			if newstate == 'shutdown':
				return self._transitionerror(newstate)
			else:
				return True
		elif state == 'charge':
			if newstate == 'shutdown':
				return self._transitionerror(newstate)
			elif newstate == 'feedin':
				return checkMdiff(mdiff,10)
			elif newstate in ['discharge','keep','feedin']:
				return checkMdiff(mdiff,10)
			elif newstate in ['force_recharge','bulk_recharge']:
				return True
			elif newstate == 'dump':
				return checkMdiff(mdiff,120)
		elif state == 'keep':
			return checkMdiff(mdiff,10)
		elif state == 'force_recharge':
			if newstate in ['discharge','feedin','dump']:
				return self._transitionerror(newstate)
			elif newstate in ['charge','keep']:
				return trueOrText(d['soc'] > c['soc_frc_highstop'],"Sticking with force_recharge until soc_frc_highstop")
			elif newstate == 'bulk_recharge':
				return True
			elif newstate == 'shutdown':
				return trueOrText(d['soc'] < c['soc_frc_lowstart'] or (mdiff > 60),"Waiting for 60s or until SOC drops below soc_frc_lowstart")
			return self._transitionerror(newstate)
		elif state == 'bulk_recharge':
			if newstate == 'keep':
				return checkMdiff(mdiff,120)
			else:
				return True
		elif state == 'feedin':
			if newstate in ['force_recharge','shutdown']:
				return self._transitionerror(newstate)
			elif newstate in ['discharge','charge','keep']:
				return checkMdiff(mdiff,10)
			elif newstate == 'dump':
				return checkMdiff(mdiff,120)
			elif newstate == 'bulk_recharge':
				return True
			else:
				return self._transitionerror(newstate)
		elif state == 'dump':
			if newstate in ['feedin','charge','discharge','keep']:
				if blackout:
					return checkMdiff(mdiff,30*60)
				else:
					return checkMdiff(mdiff,60*60)
			elif newstate in ['force_recharge','dump']:
				return self._transitionerror(newstate)
		else:
			return self._transitionerror(newstate)


	def setState(self,c,d,e,newstate):
		if newstate == self.state:
			return True
		if not (newstate in state2id):
			self.logging.error("setState(): Invalid target state '%s'" % newstate)
			return False
		transitionstring=self.testStateTransitionConstraints(c,d,e,newstate)
		if not isinstance(transitionstring,bool):
			if (self.lasttransitionstring is None) or (transitionstring != self.lasttransitionstring):
				self.logging.info("setState(): '%s'->'%s' blocked: %s" % (self.state,newstate,transitionstring));
				self.lasttransitionstring=transitionstring
			return False
		if not transitionstring:
			self.logging.debug("setState(): '%s'->'%s' failed, error: no transision string!")
			return False
		self.logging.debug("setState(): '%s'->'%s'" % (self.state,newstate))
		if self.state == "init":
			self._statwait=0
		self.preferenceUpdateSinceLastState=False
		self.policyUpdateSinceLastState=False
		self.state=newstate
		self.state_mtime=datetime.now()
		self._dbusservice['/State']=state2id[newstate]
		return True

	def determineState(self,c,d,e,policy):
		blackout=e['blackout']

		if not (d['grid/voltage/l2'] is None) or not (d['grid/voltage/l3'] is None):
			self.logging.error("Voltage detected on L2(%f)|L3(%f). Scope violation." % (d['grid/voltage/l2'],d['grid/voltage/l3']))
			return 'scope_backoff'
		if e['acout/powerin']:
			self.logging.error("Energy flow from AC-OUT1 into the Multi detected. Scope violation.")
			return 'scope_backoff'
		if not bool(c['dvcc']):
			self.logging.error("DVCC disabled. Scope violation.")
			return 'scope_backoff'

		solar_excess=d['solar/power'] - e['acout/power']

		# 0div-protection
		acout_power=e['acout/power']
		if acout_power == 0:
			acout_power=1

		enough_solar=bool(d['solar/power']/acout_power >= 1.1) # Needs to be finetuned
		feedstart_epsilon=0.2
		above_feed_lowstart=(d['soc']-c['soc_feed_lowstart']) >= 0.2
		below_feed_lowstart=(c['soc_feed_lowstart']-d['soc']) >= 0.2
		dump_possible=(
			bool(c['enable_pd']) and
			bool(solar_excess >= (c['power_pd']+200))  # Needs to be finetuned
		)
		
		feedin_possible=(
			not blackout and
			bool(c['enable_feedin'])
		)
		decisionbase="trans: p=%s bo=%i soc=%f sol=%i acout=%i es=%i afls=%i dp=%i fp=%i" % (policy,int(blackout),d['soc'],d['solar/power'],acout_power,int(enough_solar),int(above_feed_lowstart),int(dump_possible),int(feedin_possible))
		self.logging.info(decisionbase)

		# Determine the state
		# Emergency and protective measures first
		if not enough_solar and d['soc'] < c['soc_em_low']:
			return 'low_shutdown'
		elif blackout and d['soc'] < c['soc_frs_lowstart']:
			return 'low_shutdown'
		elif not blackout and d['soc'] < c['soc_frs_lowstart']:
			return 'force_recharge'
		elif enough_solar and (d['soc'] >= c['soc_high']) and c['enable_high_shutdown']:
			return 'high_shutdown'
		
		# Here it's getting policy-specific...
		if policy == 'solar_ups':
			# Keep battery charged, charge with solar only
			if blackout and not enough_solar:
				# We discharge until the emergency states are triggered (see above)
				return 'discharge'
			elif not blackout and enough_solar and below_feed_lowstart:
				# SOC is below ups target, try to charge
				return 'charge'
			elif enough_solar and dump_possible and above_feed_lowstart:
				return 'dump'
			elif enough_solar and not dump_possible and feedin_possible and above_feed_lowstart:
				return 'feedin'
			elif not enough_solar and not dump_possible and feedin_possible and above_feed_lowstart:
				return 'discharge'
			elif not enough_solar:
				return 'keep'
			else:
				self.logging.warning("Excessive energy, unable to route, trusting the MPPTs, continuing charging...")
				return 'charge'
		elif policy == 'self_consumption':
			# Self consumption
			if not blackout and not enough_solar and (d['soc'] >= c['soc_dis_lowstart']):
				# Use the energy we have in the battery during dark times
				return 'discharge'
			elif blackout and not enough_solar:
				# ... same during blackout but we tap into the reserve
				return 'discharge'
			elif not blackout and not enough_solar and (d['soc'] < c['soc_dis_lowstart']):
				# Use the grid, if the battery is below our reserve limit
				return 'keep'
			elif enough_solar and dump_possible and above_feed_lowstart:
				return 'dump'
			elif enough_solar and not dump_possible and feedin_possible and above_feed_lowstart:
				return 'feedin'
			elif enough_solar and not above_feed_lowstart:
				return 'charge'
			else:
				self.logging.warning("Excessive energy, unable to route, trusting the MPPTs, continuing charging...")
				return 'charge'
			# Generic feedin/dump behaviour from here on
		elif policy == 'bulk_recharge':
			# Force recharge hard
			if d['soc'] < c['soc_high']:
				return 'bulk_recharge'
			else:
				return 'keep'
		else:
			self.logging.error("Invalid policy id '%s'" % policy)
			return 'unknown'
				
		self.logging.error("Unable to determine state in policy '%s'" % policy)
		self.logging.error(decisionbase)
		return "unknown"


	def run(self):
		c=self.settings._values # C as in 'constant defined by user, not automatically changing'
		d=self.remotevariables_values # D as in 'data received from somewhere'
		u=dict() # U as in 'updated data to be sent somewhere'
		if c['policy'] != policy2id[self.policy]:
			self._statwait=0
			self.policy=id2policy[c['policy']]
		policy=self.policy

		if policy == 'ess3_backoff':
			# We're ordered by the user to stand down in favor of another ESS3 controller
			self.setState(c,d,e,'ess3_backoff')
			return True

		if c['ess_mode'] != 3:
			# hub4control not in mode 3, we'll backoff
			self.setState(c,d,e,'ess2_backoff')
			return True
#		e={
#			'blackout':bool((d['grid/voltage/l1'] + d['grid/voltage/l2'] +d['grid/voltage/l3']) == 0),
#			'phasedown':bool(d['grid/voltage/l1']*d['grid/voltage/l2']*d['grid/voltage/l3'] == 0),
#			'power/acout1':d['grid/power/l1']+d['grid/power/l2']+d['grid/power/l3'],
#			'power/acin':d['grid/power/l1']+d['grid/power/l2']+d['grid/power/l3'],
#			'acout/powerin':(d['acout/power/l1'] < 0) or (d['acout/power/l2'] < 0) or (d['acout/power/l3'] < 0),
#		}
		e={
			'blackout':(d['grid/voltage/l1'] == 0),
			'phasedown':(d['grid/voltage/l1'] == 0),
			'acin/power':d['grid/power/l1'],
			'acout/power':d['acout/power/l1'],
			'acout/powerin':bool(d['acout/power/l1'] < 0)
		}
		
		# Determine new state from (c)onstants, sensor (d)ata and the (policy).
		newstate=self.determineState(c,d,e,policy)
		self.setState(c,d,e,newstate)

		if not self.calcVebusVariables(c,d,e,u):
			self.logging.error("Calculating ve.bus variables failed, internal error, backing off");
			return True
		if not ('3grid/setpoint/l1' in u):
			self.logging.error("setpoint L1 not calculated in policy '%i', mode '%s', backing off" % (policy,state))
			return True

		self.updateVebusVariables(c,d,e,u)
		self.updateLocalVariables(c,d,e)
		return True

	def calcVebusVariables(self,c,d,e,u):
		inverter=None
		charger=None
		correctionfactor=0.5

		state=self.state
		if state == 'scope_backoff':
			inverter=False
			charger=False
		elif state == 'low_shutdown':
			# Shutdown - maybe via virtual power switch on the Multiplus
			inverter=False
			charger=True
			# value doesn't matter. We just want to signal that we know, what
			# we're doing to the Multi(s).
			u['3grid/setpoint/l1']=0
		elif state == 'high_shutdown':
			inverter=True
			charger=False
			# We want the grid not to be used to force the inverter to drain
			# the batteries.
			u['3grid/setpoint/l1']=0
		elif state == 'init':
			# Wait until we know, what to do. The Multi(s) might be in passthrough
			# mode due to not receiving regular setpoint updates.
			inverter=True
			charger=True
			u['3grid/setpoint/l1']=0
		elif state == 'discharge':
			inverter=True
			# There might be some PV coming in which would not be used if the charger is off.
			# Unfortunately, there's no way to disable the Multi(s)' charger and keep the MPPTs
			# active.
			charger=True
			u['3grid/setpoint/l1']=0
		elif state == 'force_recharge':
			# This is our version of hub4control's (low_soc..(low_soc+3%)) slow recharge.
			# The advantage is that our interval can be configured and is not necessarily 
			# directly below the self_consumption low SOC limit.
			inverter=False
			charger=True
			batterypower=int(d['battery/voltage']*d['battery/current'])
			targetpower=int(d['battery/voltage']*c['current_frs_charge'])
			u['3grid/setpoint/l1']=d['grid/power/l1'] - (batterypower - targetpower)
			if u['3grid/setpoint/l1'] < 0:
				if ((0-u['3grid/setpoint/l1'])/d['battery/voltage'] + c['current_frs_charge']) < c['current_bat_limit']:
					# If there's power from AC-OUT1 or from PV left that we could use for getting
					# the battery out of misery, we'll take it - up to the battery's charge limit
					# and to a setpoint of 0
					targetcurrent=min((0-d['3grid/setpoint/l1'])/d['battery/voltage'] + c['current_frs_charge'],c['current_bat_limit'])
					
					setpoint_offset=int((targetcurrent-c['current_frs_charge'])*d['battery/voltage'] * correctionfactor)
					# Only use solar power to boost the force_recharge process
					u['3grid/setpoint/l1']=min(['3grid/setpoint/l1']+setpoint_offset,0)
		elif state == 'charge':
			inverter=True
			# We'd rather disable the Multi's charger but this is not possible without
			# disabling the MPPTs
			charger=True
			u['3grid/setpoint/l1']=0
		elif state == 'keep':
			# Keep means "keep battery charge at current level while there's not enough PV".
			# Grid setpoint will be >= 0 .
			inverter=True
			charger=True
			batterypower=int(d['battery/voltage']*d['battery/current'])
			#newsetpoint=d['3grid/setpoint/l1'] - batterypower * correctionfactor
			newsetpoint=d['3grid/setpoint/l1'] - batterypower * correctionfactor
			if newsetpoint < -300:
				newnewsetpoint=d['acout/power/l1']-d['solar/power']
				self.logging.warning("Implausibly low setpoint '%i' (%i-%i) in mode 'keep', setting '%i'" % (newsetpoint,d['3grid/setpoint/l1'],batterypower,newnewsetpoint))
				u['3grid/setpoint/l1']=newnewsetpoint
			else:
				u['3grid/setpoint/l1']=newsetpoint
		elif state == 'feedin' or state == 'dump':
			inverter=True
			charger=True
			batterypower=int(d['battery/voltage']*d['battery/current'])
			newsetpoint=d['3grid/setpoint/l1'] - batterypower * correctionfactor
			if newsetpoint > 0:
				self.logging.debug("Implausibly high setpoint '%i' in mode 'feedin', setting '0'" % newsetpoint)
				u['3grid/setpoint/l1']=0
			elif newsetpoint < (- c['power_feedin_max'] ):
				self.logging.debug("Hit feedin limit of '%i'" % c['power_feedin_max'])
				u['3grid/setpoint/l1']=-c['power_feedin_max']
			else:
				u['3grid/setpoint/l1']=newsetpoint
		elif state == 'bulk_recharge':
			inverter=False
			charger=True
			# We do not look at the setpoint since there might be loads on AC-OUT1
			gridcurrentdiff=d['grid/current/l1']-c['current_acin_max_bulk_recharge'] # neg means: more is possible, pos means: reduction needed!
			batterycurrentdiff=d['battery/current']-c['current_bat_limit'] # same
			if (gridcurrentdiff > 0) or (batterycurrentdiff > 0):
				# Charging current is too high for the circuit breaker/generator or
				# the battery or both.
				u['3grid/setpoint/l1']=d['grid/power/l1']-max(
					max(gridcurrentdiff*d['grid/voltage/l1'],0),
					max(batterycurrentdiff*d['battery/voltage'],0)
				)
			elif (gridcurrentdiff < 0) and (batterycurrentdiff < 0):
				# Increase the charging current since battery and
				# AC-IN circuit breaker can take more.
				u['3grid/setpoint/l1']=d['grid/power/l1']+min(
					0-gridcurrentdiff*d['grid/voltage/l1'],
					0-batterycurrentdiff*d['battery/voltage'],
				)
			else:
				# Unlikely - there's no equal sign in physical measurements...
				u['3grid/setpoint/l1']=d['3grid/setpoint/l1']
			if (u['3grid/setpoint/l1']/d['grid/voltage/l1']) > d['grid/current/max']:
				self.logging.error("'bulk_recharge': grid max exceeded ('%i'), formula seems wrong." % u['3grid/setpoint/l1'])
				u['3grid/setpoint/l1']=d['grid/current/max']
		u['3inverter/disabled']=int(not inverter)
		u['3charger/disabled']=int(not charger)
		return True

	def updateVebusVariables(self,c,d,e,u):
		changes=(d['3grid/setpoint/l1'] != u['3grid/setpoint/l1'])
		if d['3inverter/disabled'] != u['3inverter/disabled']:
			changes=True
			self.remotevariables_busitems['3inverter/disabled'].set_value(u['3inverter/disabled'])
		if d['3charger/disabled'] != u['3charger/disabled']:
			changes=True
			self.remotevariables_busitems['3charger/disabled'].set_value(u['3charger/disabled'])
		self.remotevariables_busitems['3grid/setpoint/l1'].set_value(u['3grid/setpoint/l1'])

		print("ESS mode 3 update: policy=%s state=%s l1=%i inv=%i" % (self.policy,self.state,d['3grid/setpoint/l1'],1-int(u['3inverter/disabled'])) )
		return changes

	def updateLocalVariables(self,c,d,e):
		blackout=(d['grid/voltage/l1'] == 0)
		enough_solar=bool(d['solar/power']/d['acout/power/l1'] >= 1.1) # Needs to be finetuned
		if self._statwait > 0:
			self._statwait -= 1
			return False
			
		self._statwait=self._statwaitmax
		
		# Calculate charge left in kWh
		chargepersoc=c['charge_full_bat']*d['battery/voltage']/100/1000 # kwH per SOC%
		wattsecondspersoc=c['charge_full_bat']*d['battery/voltage']*3600/100 # s * W per SOC%
		if self.policy in ['solar_ups','bulk_recharge']:
			cl=0
			clr=max(0,(d['soc']-c['soc_frs_lowstart'])*chargepersoc)
		elif self.policy == 'self_consumption':
			cl=max(0,(d['soc']-c['soc_dis_lowstart'])*chargepersoc)
			clr=max(0,(c['soc_dis_lowstart']-c['soc_frs_lowstart'])*chargepersoc)
		else:
			cl=0
			clr=0
			
		ttd=0
		ttdr=0
		# Calculate time-till-discharged
		if d['acout/power/l1'] <= 0:
			# PV on acout is out of our scope
			ttd=0
			ttdr=0
		else:
			if self.policy in ['solar_ups','bulk_recharge']:
				ttdr=max(int((d['soc']-c['soc_frs_lowstart'])*wattsecondspersoc/d['acout/power/l1']),0)
			elif self.policy == 'self_consumption':
				if blackout:
					ttdr=max(int((d['soc']-c['soc_frs_lowstart'])*wattsecondspersoc/d['acout/power/l1']),0)
				else:
					ttd=max(int((d['soc']-c['soc_dis_lowstart'])*wattsecondspersoc/d['acout/power/l1']),0)
					ttdr=max(int((c['soc_dis_lowstart']-c['soc_frs_lowstart'])*wattsecondspersoc/d['acout/power/l1']),0)
				
		# Calculate time-till-charged and potential additional charge (cm)
		batterypower=int(d['battery/voltage']*d['battery/current'])
		ttc=0
		cm=0
		if self.policy == 'self_consumption':
			high=c['soc_high']
		elif self.policy in ['solar_ups','bulk_recharge']:
			if bool(c['enable_feedin']) or bool(c['enable_pd']):
				high=c['soc_feed_lowstart']
			else:
				high=c['soc_high']
		cm=max(0,(high-d['soc'])*chargepersoc)
		if (batterypower <= 0) or not (self.state in ['charge','bulk_charge']):
			# Unable to calculate charge time, if the battery is not being charged
			ttc=0
		else:
			ttc=max(int(max(float(high)-d['soc'],0)*wattsecondspersoc/batterypower),0)
				
		self._dbusservice['/TimeTillCharged']=ttc
		self._dbusservice['/TimeTillDischargedRegular']=ttd
		self._dbusservice['/TimeTillDischargedReserve']=ttdr
		self._dbusservice['/ChargeLeftRegular']=int(cl*10)/10
		self._dbusservice['/ChargeLeftReserve']=int(clr*10)/10
		self._dbusservice['/ChargeMissing']=int(cm*10)/10
		self._dbusservice['/EnoughPv']=int(enough_solar)
		return True
