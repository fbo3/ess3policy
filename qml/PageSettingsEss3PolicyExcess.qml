import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: qsTr("Power excess settings")
	property string settingsPrefix: "com.victronenergy.settings/Settings/Ess3Policy"
	property VBusItem controllerPolicy: VBusItem { bind: Utils.path(settingsPrefix,"/Policy") }
	model: VisualItemModel {
		MbSwitchForced {
			id: idEnableFeed
			name: qsTr("Enable feeding into the grid")
			item.bind: Utils.path(settingsPrefix, "/EnableFeed")
			writeAccessLevel: User.AccessUser
		}
		MbSpinBox {
			id: idSocFeedLowStart
			description: qsTr("Start SOC for grid feedin and power dumping")
			writeAccessLevel: User.AccessUser
			item {
				bind: Utils.path(settingsPrefix,"/SocFeedLowStart")
				decimals: 0
				unit: "%"
				min: 10
				max: 99
				step: 1
			}
		}
		MbSpinBox {
			id: idInverterMax
			description: qsTr("Maximum feedin power")
			writeAccessLevel: User.AccessUser
			item {
				bind: Utils.path(cgwacsPath,"/MaxFeedInPower")
				decimals: 0
				unit: "W"
				min: 0
				max: 30000
				step: 100
			}
		}
		MbSwitchForced {
			id: idEnablePowerDump
			name: qsTr("Enable power dumping")
			item.bind: Utils.path(settingsPrefix, "/EnablePowerDump")
			writeAccessLevel: User.AccessUser
		}
		MbSpinBox {
			id: idPowerPowerDump
			description: qsTr("Minimum excess PV for power dumping")
			writeAccessLevel: User.AccessUser
			item {
				bind: Utils.path(settingsPrefix,"/PowerPowerDump")
				decimals: 0
				unit: "W"
				min: 100
				max: 3000
            step: 100
			}
		}
	}
}
	