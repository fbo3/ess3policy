import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: qsTr("Protection settings")
	property string settingsPrefix: "com.victronenergy.settings/Settings/Ess3Policy"
	property VBusItem socEmergencyLow: VBusItem { bind: Utils.path(settingsPrefix,"/SocEmergencyLow") }
	property VBusItem socForceRechargeLowStart: VBusItem { bind: Utils.path(settingsPrefix,"/SocForceRechargeLowStart") }
	summary: [ socEmergencyLow.text,socForceRechargeLowStart.text ]
	model: VisualItemModel {
		MbSpinBox {
			id: idSocEmergencyLow
			description: qsTr("Emergency low shutdown SOC%")
			writeAccessLevel: User.AccessInstaller
			item {
				bind: Utils.path(settingsPrefix,"/SocEmergencyLow")
				decimals: 0
				unit: "%"
				min: 5
				max: 99
            step: 1
			}
		}

		MbSpinBox {
			id: idSocForceRechargeLowStart
			description: qsTr("Force recharge lower SOC% bound")
			writeAccessLevel: User.AccessInstaller
			item {
				bind: Utils.path(settingsPrefix,"/SocForceRechargeLowStart")
				decimals: 0
				unit: "%"
				min: 5
				max: 55
				step: 1
			}
		}
		MbSpinBox {
			id: idSocForceRechargeHighStop
			description: qsTr("Force recharge stop (upper SOC% bound)")
			writeAccessLevel: User.AccessInstaller
			item {
				bind: Utils.path(settingsPrefix,"/SocForceRechargeHighStop")
				decimals: 0
				unit: "%"
				min: 5
				max: 99
				step: 1
			}
		}
		MbSpinBox {
			id: idCurrentForceRecharge
			description: qsTr("Charge current during forced recharge")
			writeAccessLevel: User.AccessInstaller
			item {
				bind: Utils.path(settingsPrefix,"/CurrentForceRecharge")
				decimals: 0
				unit: "A"
				min: 1
				max: 200
				step: 1
			}
		}
		MbSwitchForced {
			id: idEnableHighShutdown
			name: qsTr("Emergency shutdown on SOC[high]")
			item.bind: Utils.path(settingsPrefix, "/EnableHighShutdown")
			writeAccessLevel: User.AccessUser
		}
		MbSpinBox {
			id: idSocEmergencyHigh
			description: qsTr("Emergency high shutdown SOC%")
			writeAccessLevel: User.AccessInstaller
			item {
				bind: Utils.path(settingsPrefix,"/SocEmergencyHigh")
				decimals: 1
				unit: "%"
				min: 30
				max: 100
            step: 0.1
			}
		}
		MbSpinBox {
			id: idSocHigh
			description: qsTr("Upper charge limit")
			writeAccessLevel: User.AccessInstaller
			item {
				bind: Utils.path(settingsPrefix,"/SocHigh")
				decimals: 1
				unit: "%"
				min: 30
				max: 100
				step: 0.1
			}
		}
	}
}
				
	